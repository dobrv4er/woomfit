from django.contrib import admin

from .models import Wallet, WalletTx


class WalletTxInline(admin.TabularInline):
    model = WalletTx
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "updated_at")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    inlines = [WalletTxInline]


@admin.register(WalletTx)
class WalletTxAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "kind", "amount", "reason", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("wallet__user__username", "reason")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
