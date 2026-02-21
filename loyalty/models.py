from django.db import models
from django.conf import settings


class LoyaltyProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty")

    # сколько всего потратил (накопительно)
    spent_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # текущая скидка в %
    discount_percent = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loyalty({self.user}) {self.discount_percent}% spent={self.spent_total}"

    def recalc_discount(self):
        """
        Правила скидок (можешь менять цифры как угодно):
        0%  — до 10 000
        3%  — 10 000+
        5%  — 25 000+
        7%  — 50 000+
        10% — 100 000+
        """
        s = self.spent_total or 0
        if s >= 100000:
            self.discount_percent = 10
        elif s >= 50000:
            self.discount_percent = 7
        elif s >= 25000:
            self.discount_percent = 5
        elif s >= 10000:
            self.discount_percent = 3
        else:
            self.discount_percent = 0

    @property
    def tier(self):
        d = self.discount_percent or 0
        if d >= 10:
            return "VIP"
        if d >= 7:
            return "Gold"
        if d >= 5:
            return "Silver"
        if d >= 3:
            return "Bronze"
        return "Base"
