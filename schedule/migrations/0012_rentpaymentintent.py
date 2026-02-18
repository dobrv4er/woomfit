from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0011_rentrequest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RentPaymentIntent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("location", models.CharField(db_index=True, max_length=160, verbose_name="Адрес")),
                ("slot_start", models.DateTimeField(db_index=True, verbose_name="Начало слота")),
                ("duration_min", models.PositiveIntegerField(default=60, verbose_name="Длительность, мин")),
                ("full_name", models.CharField(max_length=255, verbose_name="ФИО")),
                ("email", models.EmailField(blank=True, default="", max_length=254, verbose_name="E-mail")),
                ("phone", models.CharField(max_length=32, verbose_name="Телефон")),
                ("social_handle", models.CharField(blank=True, default="", max_length=120, verbose_name="Соцсети")),
                ("comment", models.TextField(blank=True, default="", verbose_name="Комментарий")),
                ("promo_code", models.CharField(blank=True, default="", max_length=64, verbose_name="Промокод")),
                ("amount_rub", models.PositiveIntegerField(default=650, verbose_name="Сумма, руб")),
                (
                    "status",
                    models.CharField(
                        choices=[("new", "Новый"), ("pending", "Ожидает оплату"), ("paid", "Оплачен"), ("canceled", "Отменён")],
                        db_index=True,
                        default="new",
                        max_length=12,
                    ),
                ),
                ("tb_payment_id", models.CharField(blank=True, default="", max_length=64, verbose_name="TBank payment id")),
                ("tb_status", models.CharField(blank=True, default="", max_length=32, verbose_name="TBank status")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("expires_at", models.DateTimeField(db_index=True, verbose_name="Оплатить до")),
                ("paid_at", models.DateTimeField(blank=True, null=True, verbose_name="Оплачено")),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rent_payment_intents",
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
                        related_name="rent_payment_intents",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Намерение оплаты аренды",
                "verbose_name_plural": "Намерения оплаты аренды",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "expires_at"], name="rentpi_status_exp_idx"),
                    models.Index(fields=["location", "slot_start"], name="rentpi_loc_slot_idx"),
                ],
            },
        ),
    ]
