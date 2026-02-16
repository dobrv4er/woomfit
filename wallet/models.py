from django.db import models
from django.conf import settings
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet({self.user}) = {self.balance}"


class WalletTx(models.Model):
    class Kind(models.TextChoices):
        TOPUP = "topup", "Пополнение"
        DEBIT = "debit", "Списание"
        REFUND = "refund", "Возврат"
        ADJUST = "adjust", "Корректировка"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="txs")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # всегда положительное число
    reason = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} {self.amount} ({self.wallet.user})"
