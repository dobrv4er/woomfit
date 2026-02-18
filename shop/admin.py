from django.contrib import admin
from .models import Category, Product, TrialUse


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "sort")
    list_filter = ("section",)
    ordering = ("section", "sort", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price_rub",
        "grant_kind",
        "is_trial",
        "trial_scope",
        "is_active",
        "sort",
    )
    list_filter = (
        "category__section",
        "category",
        "grant_kind",
        "is_trial",
        "trial_scope",
        "is_active",
    )
    search_fields = ("name", "subtitle", "badge")
    ordering = ("category__section", "category__sort", "sort", "name")

    fieldsets = (
        ("Основное", {
            "fields": (
                "category",
                "name",
                "subtitle",
                "badge",
                "image",
                "price_rub",
                "is_active",
                "sort",
            )
        }),
        ("Пробное", {
            "fields": ("is_trial", "trial_scope"),
        }),
        ("Выдача после оплаты", {
            "fields": (
                "grant_kind",
                "membership_scope",
                "membership_kind",
                "membership_visits",
                "membership_days",
                "wallet_topup_rub",
            )
        }),
    )


@admin.register(TrialUse)
class TrialUseAdmin(admin.ModelAdmin):
    list_display = ("user", "scope", "used_at")
    list_filter = ("scope",)
    search_fields = ("user__full_name", "user__phone")
    ordering = ("-used_at",)
