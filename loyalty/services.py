from __future__ import annotations

from calendar import monthrange
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from wallet.services import debit

from .models import CashbackBonus, CashbackBonusSpend


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

CASHBACK_PERCENT = Decimal("0.05")
MAX_BONUS_PAYMENT_PERCENT = Decimal("0.30")
BONUS_TTL_MONTHS = 4


def _money(value, *, rounding=ROUND_HALF_UP) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(MONEY, rounding=rounding)


def _positive_money(value) -> Decimal:
    amount = _money(value)
    if amount <= ZERO:
        return ZERO
    return amount


def _add_months(dt, months: int):
    idx = (dt.month - 1) + months
    year = dt.year + (idx // 12)
    month = (idx % 12) + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def get_bonus_balance(user) -> Decimal:
    if not user or not getattr(user, "pk", None):
        return ZERO

    total = (
        CashbackBonus.objects
        .filter(user=user, remaining_amount__gt=0, expires_at__gt=timezone.now())
        .aggregate(total=Sum("remaining_amount"))
        .get("total")
    )
    return _money(total)


def get_bonus_payment_cap(total_amount) -> Decimal:
    amount = _positive_money(total_amount)
    if amount <= ZERO:
        return ZERO
    return (amount * MAX_BONUS_PAYMENT_PERCENT).quantize(MONEY, rounding=ROUND_DOWN)


def build_bonus_payment_plan(*, user, total_amount, bonus_eligible_amount=None) -> dict:
    total = _positive_money(total_amount)
    if bonus_eligible_amount is None:
        eligible = total
    else:
        eligible = _positive_money(bonus_eligible_amount)
    eligible = min(total, eligible)

    bonus_available = get_bonus_balance(user)
    bonus_cap = get_bonus_payment_cap(eligible)
    bonus_used = min(total, bonus_available, bonus_cap).quantize(MONEY, rounding=ROUND_DOWN)
    cash_needed = (total - bonus_used).quantize(MONEY, rounding=ROUND_HALF_UP)

    return {
        "total": total,
        "eligible_total": eligible,
        "bonus_available": bonus_available,
        "bonus_cap": bonus_cap,
        "bonus_used": bonus_used,
        "cash_needed": cash_needed,
    }


@transaction.atomic
def pay_with_wallet_bonus(
    *,
    user,
    total_amount,
    bonus_eligible_amount,
    reason: str,
    source_type: str,
    source_id: int,
) -> dict:
    total = _positive_money(total_amount)
    if total <= ZERO:
        raise ValidationError("Amount must be positive")

    eligible = min(total, _positive_money(bonus_eligible_amount))
    now = timezone.now()
    bonuses = list(
        CashbackBonus.objects
        .select_for_update()
        .filter(user=user, remaining_amount__gt=0, expires_at__gt=now)
        .order_by("expires_at", "id")
    )

    bonus_available = sum((_money(b.remaining_amount) for b in bonuses), ZERO)
    bonus_cap = get_bonus_payment_cap(eligible)
    bonus_used = min(total, bonus_available, bonus_cap).quantize(MONEY, rounding=ROUND_DOWN)
    cash_needed = (total - bonus_used).quantize(MONEY, rounding=ROUND_HALF_UP)

    wallet_tx = None
    if cash_needed > ZERO:
        wallet_tx = debit(user, cash_needed, reason=reason)

    left = bonus_used
    for bonus in bonuses:
        if left <= ZERO:
            break
        remaining = _money(bonus.remaining_amount)
        if remaining <= ZERO:
            continue

        part = min(remaining, left).quantize(MONEY, rounding=ROUND_DOWN)
        if part <= ZERO:
            continue

        bonus.remaining_amount = (remaining - part).quantize(MONEY, rounding=ROUND_HALF_UP)
        bonus.save(update_fields=["remaining_amount"])

        CashbackBonusSpend.objects.create(
            user=user,
            bonus=bonus,
            source_type=source_type,
            source_id=int(source_id),
            amount=part,
            reason=reason or "",
        )
        left = (left - part).quantize(MONEY, rounding=ROUND_HALF_UP)

    return {
        "total": total,
        "eligible_total": eligible,
        "bonus_available": bonus_available,
        "bonus_cap": bonus_cap,
        "bonus_used": bonus_used,
        "cash_needed": cash_needed,
        "wallet_tx": wallet_tx,
    }


@transaction.atomic
def grant_cashback(*, user, base_amount, source_type: str, source_id: int, reason: str = ""):
    if not user or not getattr(user, "pk", None):
        return None

    base = _positive_money(base_amount)
    if base <= ZERO:
        return None

    amount = (base * CASHBACK_PERCENT).quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount <= ZERO:
        return None

    now = timezone.now()
    defaults = {
        "base_amount": base,
        "amount": amount,
        "remaining_amount": amount,
        "reason": reason or "",
        "expires_at": _add_months(now, BONUS_TTL_MONTHS),
    }
    bonus, _ = CashbackBonus.objects.get_or_create(
        user=user,
        source_type=source_type,
        source_id=int(source_id),
        defaults=defaults,
    )
    return bonus
