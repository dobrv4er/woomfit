import re

from django.conf import settings


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = f"7{digits}"
    if len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"
    return ""


def customer_contact_fields(user) -> dict:
    email = (getattr(user, "email", "") or "").strip()
    phone = _normalize_phone((getattr(user, "phone", "") or "").strip())

    fields = {}
    if email:
        fields["Email"] = email
    if phone:
        fields["Phone"] = phone
    if not fields:
        fields["Email"] = (getattr(settings, "LEGAL_OPERATOR_EMAIL", "") or "support@example.com").strip()
    return fields


def receipt_item(name: str, price_kopeks: int, quantity: int, amount_kopeks: int | None = None) -> dict:
    qty = int(quantity)
    price = int(price_kopeks)
    amount = int(amount_kopeks) if amount_kopeks is not None else price * qty
    return {
        "Name": str(name)[:128],
        "Price": price,
        "Quantity": qty,
        "Amount": amount,
        "Tax": settings.TBANK_ITEM_TAX,
        "PaymentMethod": settings.TBANK_ITEM_PAYMENT_METHOD,
        "PaymentObject": settings.TBANK_ITEM_PAYMENT_OBJECT,
    }


def build_receipt(user, items: list[dict]) -> dict:
    receipt = {
        "Taxation": settings.TBANK_TAXATION,
        "Items": items,
    }
    ffd_version = (getattr(settings, "TBANK_FFD_VERSION", "") or "").strip()
    if ffd_version:
        receipt["FfdVersion"] = ffd_version
    receipt.update(customer_contact_fields(user))
    return receipt
