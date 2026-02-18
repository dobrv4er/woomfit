from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Профиль", {"fields": ("full_name",)}),
        ("WOOM FIT", {"fields": ("phone", "birth_date", "club", "club_card")}),
    )
    list_display = ("id", "full_name", "phone", "email", "is_staff")
    search_fields = ("full_name", "phone", "email")
