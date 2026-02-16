from django.conf import settings
from django.db import models


class Category(models.Model):
    class Section(models.TextChoices):
        MEMBERSHIPS = "memberships", "Абонементы"
        PERSONAL = "personal", "Персональные"
        GROUP = "group", "Групповые"
        OTHER = "other", "Прочее"

    name = models.CharField(max_length=80)
    section = models.CharField(max_length=16, choices=Section.choices, default=Section.GROUP, db_index=True)
    sort = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ("section", "sort", "name")

    def __str__(self):
        return self.name


class Product(models.Model):
    class GrantKind(models.TextChoices):
        NONE = "none", "Не выдаёт ничего"
        MEMBERSHIP = "membership", "Выдаёт абонемент"
        WALLET_TOPUP = "wallet_topup", "Пополняет кошелёк"

    class MembershipScope(models.TextChoices):
        GROUP = "group", "Групповые"
        PERSONAL = "personal", "Персональные"

    class TrialScope(models.TextChoices):
        GROUP = "group", "Пробное (групповое)"
        PERSONAL = "personal", "Пробное (персональное)"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=140)

    subtitle = models.CharField(max_length=160, blank=True, default="")
    badge = models.CharField(max_length=60, blank=True, default="")  # типа "1 месяц"
    image = models.ImageField(upload_to="shop/", blank=True, null=True)

    price_rub = models.PositiveIntegerField(default=0)
    sort = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    # ✅ пробное
    is_trial = models.BooleanField(default=False)
    trial_scope = models.CharField(max_length=16, choices=TrialScope.choices, blank=True, default="")

    # ✅ что выдаём после оплаты (настраивается в админке)
    grant_kind = models.CharField(
        max_length=16,
        choices=GrantKind.choices,
        default=GrantKind.NONE,
        db_index=True,
    )

    # --- выдача абонемента ---
    membership_scope = models.CharField(
        max_length=16,
        choices=MembershipScope.choices,
        blank=True,
        default="",
        help_text="Для каких тренировок работает абонемент (group/personal).",
    )
    membership_kind = models.CharField(
        max_length=16,
        choices=(
            ("visits", "По посещениям"),
            ("time", "По времени"),
            ("unlimited", "Безлимит"),
        ),
        blank=True,
        default="",
    )
    membership_visits = models.PositiveIntegerField(null=True, blank=True, help_text="Сколько посещений выдаём (если VISITS).")
    membership_days = models.PositiveIntegerField(null=True, blank=True, help_text="Срок действия в днях (если TIME/UNLIMITED).")

    # --- пополнение кошелька ---
    wallet_topup_rub = models.PositiveIntegerField(null=True, blank=True, help_text="Сколько рублей начислить в кошелёк.")

    class Meta:
        ordering = ("sort", "name")

    def __str__(self):
        return self.name


class TrialUse(models.Model):
    """Фиксируем факт использования пробного для пользователя и типа (group/personal)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trial_uses")
    scope = models.CharField(max_length=16, choices=Product.TrialScope.choices)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "scope")

    def __str__(self):
        return f"{self.user_id} used {self.scope}"
