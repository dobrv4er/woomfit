from django.contrib import admin
from .models import Membership

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "membership_status", "payment_status", "valid_to", "purchased_at")
    search_fields = ("user__full_name", "user__phone", "title")
    list_filter = ("membership_status", "payment_status", "source")
