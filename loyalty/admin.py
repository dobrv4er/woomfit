from django.contrib import admin
from .models import LoyaltyProfile


@admin.register(LoyaltyProfile)
class LoyaltyProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "spent_total", "discount_percent", "updated_at")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    ordering = ("-updated_at",)
