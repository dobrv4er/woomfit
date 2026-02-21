from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from .models import LoyaltyProfile


def get_discount_percent(user) -> int:
    lp = getattr(user, "loyalty", None)
    if not lp:
        return 0
    return int(lp.discount_percent or 0)


def apply_discount(amount: Decimal, percent: int) -> Decimal:
    """
    amount - исходная цена
    percent - скидка (0..100)
    Возвращает цену после скидки, округляя до 2 знаков.
    """
    if percent <= 0:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    k = Decimal(100 - percent) / Decimal(100)
    return (amount * k).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def add_spent(user, amount: Decimal) -> LoyaltyProfile:
    """Add `amount` to user's lifetime spend and recalc discount.

    Call this only at the moment when money is actually paid (e.g. order paid,
    session paid, wallet payment completed). Keep it idempotent at call site
    (don't call twice for the same payment).
    """
    if amount is None:
        return LoyaltyProfile.objects.get_or_create(user=user)[0]

    amt = Decimal(str(amount))
    if amt <= 0:
        return LoyaltyProfile.objects.get_or_create(user=user)[0]

    lp, _ = LoyaltyProfile.objects.select_for_update().get_or_create(user=user)
    lp.spent_total = (lp.spent_total or 0) + amt
    lp.recalc_discount()
    lp.save(update_fields=["spent_total", "discount_percent", "updated_at"])
    return lp
