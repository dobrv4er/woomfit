from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from schedule.models import Trainer, Session
from shop.models import Category, Product

class Command(BaseCommand):
    help = "Seed demo data (safe to re-run)"

    def handle(self, *args, **options):
        trainer, _ = Trainer.objects.get_or_create(name="Совина Елена")

        now = timezone.localtime()
        start_at = now.replace(hour=11, minute=0, second=0, microsecond=0)
        locations = [x.strip() for x in getattr(settings, "WOOMFIT_LOCATIONS", []) if str(x).strip()]
        default_location = locations[0] if locations else "Сакко и Ванцетти, 93а"

        Session.objects.get_or_create(
            title="Плоский живот",
            start_at=start_at,
            trainer=trainer,
            defaults={"duration_min": 50, "location": default_location, "capacity": 18},
        )

        c1, _ = Category.objects.get_or_create(name="Абонементы", defaults={"sort": 10})
        c2, _ = Category.objects.get_or_create(name="Групповые", defaults={"sort": 20})
        c3, _ = Category.objects.get_or_create(name="Персональные", defaults={"sort": 30})
        c4, _ = Category.objects.get_or_create(name="Прочее", defaults={"sort": 40})

        Product.objects.get_or_create(category=c4, name="Вода", defaults={"price_rub": 50})
        Product.objects.get_or_create(category=c2, name="Пробное занятие", defaults={"price_rub": 450})

        self.stdout.write(self.style.SUCCESS("Demo data ensured"))
