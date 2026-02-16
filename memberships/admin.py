from django.contrib import admin
from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "title",
        "kind",
        "scope",
        "left_visits",
        "start_date",
        "end_date",
        "is_active",
        "created_at",
    )
    list_filter = ("kind", "scope", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "title")
    ordering = ("-created_at",)
