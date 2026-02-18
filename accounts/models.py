from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    full_name = models.CharField("ФИО", max_length=255, blank=True)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    club = models.CharField("Клуб", max_length=120, default="WOOM FIT")
    club_card = models.CharField("Карта", max_length=64, blank=True)
    personal_data_consent_at = models.DateTimeField("Согласие ПДн: дата", null=True, blank=True)
    personal_data_consent_ip = models.GenericIPAddressField("Согласие ПДн: IP", null=True, blank=True)
    offer_consent_at = models.DateTimeField("Согласие с офертой: дата", null=True, blank=True)
    offer_consent_ip = models.GenericIPAddressField("Согласие с офертой: IP", null=True, blank=True)

    def get_full_name(self):
        full_name = (self.full_name or "").strip()
        if full_name:
            return full_name

        legacy_full_name = " ".join(
            part.strip() for part in [self.first_name, self.last_name] if part and part.strip()
        ).strip()
        return legacy_full_name

    def get_short_name(self):
        full_name = self.get_full_name()
        if not full_name:
            return ""
        return full_name.split()[0]

    def __str__(self):
        return self.get_full_name() or self.phone or f"Клиент #{self.pk}"
