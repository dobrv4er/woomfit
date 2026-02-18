from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0010_paymentintent_legal_acceptance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RentRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=255, verbose_name="ФИО")),
                ("email", models.EmailField(blank=True, default="", max_length=254, verbose_name="E-mail")),
                ("phone", models.CharField(max_length=32, verbose_name="Телефон")),
                ("social_handle", models.CharField(blank=True, default="", max_length=120, verbose_name="Соцсети")),
                ("comment", models.TextField(blank=True, default="", verbose_name="Комментарий")),
                ("promo_code", models.CharField(blank=True, default="", max_length=64, verbose_name="Промокод")),
                ("price_rub", models.PositiveIntegerField(default=650, verbose_name="Стоимость, руб")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                (
                    "session",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rent_request",
                        to="schedule.session",
                        verbose_name="Слот аренды",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rent_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заявка на аренду",
                "verbose_name_plural": "Заявки на аренду",
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["created_at"], name="rentreq_created_idx")],
            },
        ),
    ]
