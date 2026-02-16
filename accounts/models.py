from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    phone = models.CharField("Телефон", max_length=32, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    club = models.CharField("Клуб", max_length=120, default="WOOM FIT")
    club_card = models.CharField("Карта", max_length=64, blank=True)

    def __str__(self):
        return self.get_full_name() or self.username
