from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from memberships.models import Membership
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
