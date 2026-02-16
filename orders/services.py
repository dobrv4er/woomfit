from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from memberships.models import Membership
from wallet.models import Wallet, WalletTx


def _grant_membership(*, user, product, qty: int) -> None:
    if not user or qty <= 0:
        return

    title = product.name
    kind = product.membership_kind or Membership.Kind.VISITS
    scope = product.membership_scope or ""

    visits = product.membership_visits
    days = product.membership_days

    today = timezone.localdate()

    for _ in range(qty):
        m = Membership.objects.create(
            user=user,
            title=title,
            kind=kind,
            scope=scope,
            total_visits=visits if kind == Membership.Kind.VISITS else None,
            left_visits=visits if kind == Membership.Kind.VISITS else None,
            is_active=True,
        )

        # срок по дням (для time/unlimited)
        if days and kind in (Membership.Kind.TIME, Membership.Kind.UNLIMITED):
            m.start_date = today
            m.end_date = today + timedelta(days=int(days) - 1)
            m.save(update_fields=["start_date", "end_date"])


def _wallet_topup(*, user, amount_rub: int, reason: str) -> None:
    if not user or not amount_rub:
        return

    wallet, _ = Wallet.objects.get_or_create(user=user)
    WalletTx.objects.create(
        wallet=wallet,
        kind=WalletTx.Kind.TOPUP,
        amount=Decimal(str(amount_rub)),
        reason=reason,
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
