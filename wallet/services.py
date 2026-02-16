from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from core.telegram_notify import tg_send
from .models import Wallet, WalletTx


def get_wallet(user, *, for_update: bool = False) -> Wallet:
    qs = Wallet.objects
    if for_update:
        qs = qs.select_for_update()
    w = qs.filter(user=user).first()
    if w:
        return w
    # create outside select_for_update path
    w, _ = Wallet.objects.get_or_create(user=user)
    if for_update:
        # lock freshly created row
        return Wallet.objects.select_for_update().get(pk=w.pk)
    return w


@transaction.atomic
def topup(user, amount: Decimal, reason: str = "") -> WalletTx:
    if amount <= 0:
        raise ValidationError("Amount must be positive")

    # Lock wallet row to keep balance consistent under concurrency.
    w = get_wallet(user, for_update=True)

    # IMPORTANT: do not change balance here.
    # WalletTx post_save signal applies the delta to wallet.balance.
    tx = WalletTx.objects.create(
        wallet=w,
        kind=WalletTx.Kind.TOPUP,
        amount=amount,
        reason=reason,
    )
    w.refresh_from_db(fields=["balance"])

    who = (user.get_full_name() or user.username or str(user)).strip()
    tg_send(
        "➕ <b>Кошелёк: пополнение</b>\n"
        f"Клиент: <b>{who}</b>\n"
        f"Сумма: <b>{amount}</b>\n"
        f"Баланс: <b>{w.balance}</b>\n"
        f"Причина: {reason or '—'}"
    )
    return tx


@transaction.atomic
def debit(user, amount: Decimal, reason: str = "") -> WalletTx:
    if amount <= 0:
        raise ValidationError("Amount must be positive")

    w = get_wallet(user, for_update=True)
    if (w.balance or 0) < amount:
        raise ValidationError("Not enough balance")

    tx = WalletTx.objects.create(
        wallet=w,
        kind=WalletTx.Kind.DEBIT,
        amount=amount,
        reason=reason,
    )
    w.refresh_from_db(fields=["balance"])

    who = (user.get_full_name() or user.username or str(user)).strip()
    tg_send(
        "➖ <b>Кошелёк: списание</b>\n"
        f"Клиент: <b>{who}</b>\n"
        f"Сумма: <b>{amount}</b>\n"
        f"Баланс: <b>{w.balance}</b>\n"
        f"Причина: {reason or '—'}"
    )
    return tx


@transaction.atomic
def refund(user, amount: Decimal, reason: str = "") -> WalletTx:
    if amount <= 0:
        raise ValidationError("Amount must be positive")

    w = get_wallet(user, for_update=True)

    tx = WalletTx.objects.create(
        wallet=w,
        kind=WalletTx.Kind.REFUND,
        amount=amount,
        reason=reason,
    )
    w.refresh_from_db(fields=["balance"])

    who = (user.get_full_name() or user.username or str(user)).strip()
    tg_send(
        "↩️ <b>Кошелёк: возврат</b>\n"
        f"Клиент: <b>{who}</b>\n"
        f"Сумма: <b>{amount}</b>\n"
        f"Баланс: <b>{w.balance}</b>\n"
        f"Причина: {reason or '—'}"
    )
    return tx
