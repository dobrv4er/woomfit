from decimal import Decimal
from loyalty.services import get_discount_percent, apply_discount
from loyalty.services import add_spent
from wallet.services import debit


def pay_with_wallet(user, base_amount: Decimal, reason: str):
    """
    Возвращает dict:
    {
      "base": Decimal,
      "discount_percent": int,
      "final": Decimal,
      "tx": WalletTx
    }
    """
    disc = get_discount_percent(user)
    final_amount = apply_discount(base_amount, disc)

    tx = debit(user, final_amount, reason=reason)

    # Increase lifetime spend after successful payment.
    add_spent(user, final_amount)

    return {
        "base": base_amount,
        "discount_percent": disc,
        "final": final_amount,
        "tx": tx,
    }
