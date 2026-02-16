from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from schedule.models import Trainer, Session
from shop.models import Category, Product

class Command(BaseCommand):
    help = "Seed demo data (safe to re-run)"

    def handle(self, *args, **options):
        t1, _ = Trainer.objects.get_or_create(name="Совина Елена")
        t2, _ = Trainer.objects.get_or_create(name="Карамита Дарья")

        now = timezone.localtime()
        start1 = now.replace(hour=11, minute=0, second=0, microsecond=0)
        start2 = now.replace(hour=12, minute=0, second=0, microsecond=0)

        Session.objects.get_or_create(
            title="Плоский живот",
            start_at=start1,
            trainer=t1,
            defaults={"duration_min": 50, "location": "Сакко и Ванцетти, 93а", "capacity": 18},
        )
        Session.objects.get_or_create(
            title="Здоровая спина",
            start_at=start2,
            trainer=t2,
            defaults={"duration_min": 50, "location": "Аркадия Гайдара, 86", "capacity": 16},
        )

        c1, _ = Category.objects.get_or_create(name="Абонементы", defaults={"sort": 10})
        c2, _ = Category.objects.get_or_create(name="Групповые", defaults={"sort": 20})
        c3, _ = Category.objects.get_or_create(name="Персональные", defaults={"sort": 30})
        c4, _ = Category.objects.get_or_create(name="Прочее", defaults={"sort": 40})

        Product.objects.get_or_create(category=c4, name="Вода", defaults={"price_rub": 50})
        Product.objects.get_or_create(category=c2, name="Пробное занятие", defaults={"price_rub": 450})

        self.stdout.write(self.style.SUCCESS("Demo data ensured"))
