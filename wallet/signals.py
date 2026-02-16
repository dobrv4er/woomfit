from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Wallet, WalletTx


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_wallet_for_user(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=WalletTx)
def apply_wallet_tx(sender, instance: WalletTx, created, **kwargs):
    """Автоматически применяем WalletTx к балансу.

    Важно: применяем только при created=True, чтобы обновления записи
    не меняли баланс повторно.
    """
    if not created:
        return

    wallet = instance.wallet
    if not wallet:
        return

    amount = instance.amount
    if instance.kind in (WalletTx.Kind.TOPUP, WalletTx.Kind.REFUND, WalletTx.Kind.ADJUST):
        wallet.balance = (wallet.balance or 0) + amount
    elif instance.kind == WalletTx.Kind.DEBIT:
        wallet.balance = (wallet.balance or 0) - amount
    else:
        return

    wallet.save(update_fields=["balance", "updated_at"])
