from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from memberships.models import Membership
from wallet.models import WalletTx
from wallet.services import get_wallet
from wallet.services import topup


def _grant_membership(*, user, product, qty: int) -> None:
    if not user or qty <= 0:
        return

    title = product.name
    kind = product.membership_kind or Membership.Kind.VISITS
    scope = product.membership_scope or ""

    visits = product.membership_visits
    days = product.membership_days

    validity_days = int(days or 0) or None

    for _ in range(qty):
        Membership.objects.create(
            user=user,
            title=title,
            kind=kind,
            scope=scope,
            total_visits=visits if kind == Membership.Kind.VISITS else None,
            left_visits=visits if kind == Membership.Kind.VISITS else None,
            validity_days=validity_days,
            is_active=True,
        )


def _wallet_topup(*, user, amount_rub: int, reason: str) -> None:
    if not user or not amount_rub:
        return

    topup(user, Decimal(str(amount_rub)), reason=reason)


def _revoke_memberships_for_item(*, order, product, qty: int) -> None:
    if not order.user_id or qty <= 0:
        return

    title = (getattr(product, "name", "") or "").strip()
    if not title:
        return

    # We do not have a direct link "order -> granted membership" in legacy data.
    # As a pragmatic rollback, deactivate newest memberships with the same title
    # created around this order lifetime.
    created_from = order.created_at - timedelta(minutes=5)
    memberships = list(
        Membership.objects
        .select_for_update()
        .filter(user=order.user, title=title, created_at__gte=created_from)
        .order_by("-created_at", "-id")[:qty]
    )
    for m in memberships:
        update_fields = []
        if m.kind == Membership.Kind.VISITS and m.left_visits is not None and m.left_visits != 0:
            m.left_visits = 0
            update_fields.append("left_visits")
        if m.is_active:
            m.is_active = False
            update_fields.append("is_active")
        if update_fields:
            m.save(update_fields=update_fields)


def _revoke_wallet_topup_for_item(*, order, product, qty: int) -> None:
    if not order.user_id or qty <= 0:
        return
    amount_rub = int(getattr(product, "wallet_topup_rub", 0) or 0) * qty
    if amount_rub <= 0:
        return

    wallet = get_wallet(order.user, for_update=True)
    WalletTx.objects.create(
        wallet=wallet,
        kind=WalletTx.Kind.ADJUST,
        amount=Decimal(str(-amount_rub)),
        reason=f"Сторно пополнения по возврату заказа #{order.id}: {product.name}",
    )


@transaction.atomic
def fulfill_order(order) -> bool:
    """Выдать всё, что куплено в заказе.

    Идемпотентно: если fulfilled_at уже стоит — ничего не делаем.
    Возвращает True если реально выдавали (первый раз).
    """
    if order.fulfilled_at:
        return False

    # выдаём только если заказ оплачен
    if getattr(order, "status", "") != "paid":
        return False

    for it in order.items.select_related("product").all():
        p = it.product
        if not p:
            continue

        qty = int(it.qty or 0)
        if qty <= 0:
            continue

        if p.grant_kind == "membership":
            _grant_membership(user=order.user, product=p, qty=qty)

        elif p.grant_kind == "wallet_topup":
            _wallet_topup(
                user=order.user,
                amount_rub=int(p.wallet_topup_rub or 0) * qty,
                reason=f"Пополнение по заказу #{order.id}: {p.name}",
            )

        # p.grant_kind == none → ничего

    order.fulfilled_at = timezone.now()
    order.save(update_fields=["fulfilled_at"])
    return True


@transaction.atomic
def revoke_order(order) -> bool:
    """Откат выданного по заказу (для REFUNDED).

    Идемпотентно: если fulfilled_at пустой, считаем, что откат уже сделан
    либо выдача не выполнялась.
    """
    if not order.fulfilled_at:
        return False

    for it in order.items.select_related("product").all():
        p = it.product
        if not p:
            continue

        qty = int(it.qty or 0)
        if qty <= 0:
            continue

        if p.grant_kind == "membership":
            _revoke_memberships_for_item(order=order, product=p, qty=qty)
        elif p.grant_kind == "wallet_topup":
            _revoke_wallet_topup_for_item(order=order, product=p, qty=qty)

    # Marker for idempotency: rollback already applied.
    order.fulfilled_at = None
    order.save(update_fields=["fulfilled_at"])
    return True
