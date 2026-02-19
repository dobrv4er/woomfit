from django.apps import AppConfig


class CashbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "loyalty"
    verbose_name = "Cashback"

    def ready(self):
        from . import signals  # noqa
