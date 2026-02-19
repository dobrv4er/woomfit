from django.conf import settings
from django.db import models


class CashbackBonus(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cashback_bonuses",
    )
    source_type = models.CharField(max_length=32, db_index=True, default="")
    source_id = models.PositiveBigIntegerField(db_index=True)

    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, default="")

    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Кэшбек-бонус"
        verbose_name_plural = "Кэшбек-бонусы"
        ordering = ("expires_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_type", "source_id"],
                name="uniq_cashback_bonus_source",
            )
        ]
        indexes = [
            models.Index(fields=["user", "expires_at"], name="cashback_user_exp_idx"),
        ]

    def __str__(self):
        return (
            f"CashbackBonus({self.user_id}) +{self.amount} "
            f"remain={self.remaining_amount} exp={self.expires_at:%Y-%m-%d}"
        )


class CashbackBonusSpend(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cashback_bonus_spends",
    )
    bonus = models.ForeignKey(
        CashbackBonus,
        on_delete=models.SET_NULL,
        related_name="spends",
        null=True,
        blank=True,
    )
    source_type = models.CharField(max_length=32, db_index=True, default="")
    source_id = models.PositiveBigIntegerField(db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Списание кэшбек-бонусов"
        verbose_name_plural = "Списания кэшбек-бонусов"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["user", "source_type", "source_id"],
                name="cashback_spend_src_idx",
            ),
        ]

    def __str__(self):
        return f"CashbackSpend({self.user_id}) -{self.amount} src={self.source_type}:{self.source_id}"
