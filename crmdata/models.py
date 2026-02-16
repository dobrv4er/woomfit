from django.conf import settings
from django.db import models

class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_memberships")
    title = models.CharField(max_length=255)

    membership_status = models.CharField(max_length=64, blank=True)  # Активно/Блокировано/...
    payment_status = models.CharField(max_length=64, blank=True)     # Оплачено/Не оплачено/...

    composition_raw = models.CharField(max_length=255, blank=True)   # "8 занятий 7/8"
    total_visits = models.PositiveIntegerField(null=True, blank=True)
    left_visits = models.PositiveIntegerField(null=True, blank=True)
    used_visits = models.PositiveIntegerField(null=True, blank=True)

    valid_to = models.DateField(null=True, blank=True)               # "Действителен до"
    purchased_at = models.DateTimeField(null=True, blank=True)       # "Оформлен"

    source = models.CharField(max_length=32, default="appevent")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} — {self.user}"
