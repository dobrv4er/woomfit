from decimal import Decimal
from loyalty.services import pay_with_wallet_bonus


def pay_with_wallet(
    user,
    base_amount: Decimal,
    reason: str,
    *,
    source_type: str,
    source_id: int,
    bonus_eligible_amount: Decimal | None = None,
):
    eligible_amount = base_amount if bonus_eligible_amount is None else bonus_eligible_amount

    return pay_with_wallet_bonus(
        user=user,
        total_amount=base_amount,
        bonus_eligible_amount=eligible_amount,
        reason=reason,
        source_type=source_type,
        source_id=source_id,
    )
