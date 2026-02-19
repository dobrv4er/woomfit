from django.contrib import admin
from .models import CashbackBonus, CashbackBonusSpend


@admin.register(CashbackBonus)
class CashbackBonusAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "remaining_amount",
        "expires_at",
        "source_type",
        "source_id",
        "created_at",
    )
    list_filter = ("source_type",)
    search_fields = ("user__full_name", "user__phone", "reason")
    ordering = ("expires_at", "-created_at")


@admin.register(CashbackBonusSpend)
class CashbackBonusSpendAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "source_type",
        "source_id",
        "created_at",
    )
    list_filter = ("source_type",)
    search_fields = ("user__full_name", "user__phone", "reason")
    ordering = ("-created_at",)
