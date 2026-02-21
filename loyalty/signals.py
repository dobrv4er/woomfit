from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import LoyaltyProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_loyalty_for_user(sender, instance, created, **kwargs):
    if created:
        LoyaltyProfile.objects.get_or_create(user=instance)
