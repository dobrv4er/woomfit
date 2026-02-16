from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("WOOM FIT", {"fields": ("phone", "birth_date", "club", "club_card")}),
    )
    list_display = ("username","email","first_name","last_name","phone","is_staff")
