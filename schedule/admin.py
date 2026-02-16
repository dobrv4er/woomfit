from django import forms
from django.contrib import admin

from .models import Trainer, Session, Booking, Workout


class SessionAdminForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind", "group")
        client = cleaned.get("client")

        if kind in ("personal", "rent") and not client:
            raise forms.ValidationError("Для персональной тренировки/аренды нужно указать клиента")

        if kind == "group":
            cleaned["client"] = None

        return cleaned


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "level", "default_duration_min", "default_capacity")
    search_fields = ("name", "level")
    ordering = ("name",)


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("id", "name")


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    autocomplete_fields = ("user", "membership")
    readonly_fields = ("created_at", "marked_at", "canceled_at")
    fields = ("user", "membership", "booking_status", "attendance_status", "created_at", "marked_at", "canceled_at")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    form = SessionAdminForm
    list_display = ("id", "start_at", "title", "kind", "workout", "client", "trainer", "location", "capacity", "duration_min")
    list_filter = ("location", "trainer", "kind")
    search_fields = ("title", "location", "trainer__name", "workout__name")
    autocomplete_fields = ("trainer", "client", "workout")
    ordering = ("start_at",)
    inlines = (BookingInline,)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)

        day = request.GET.get("day") or request.GET.get("date") or request.GET.get("start_at_0")
        start = request.GET.get("start") or request.GET.get("time") or request.GET.get("start_at_1")
        loc = request.GET.get("loc") or request.GET.get("location")
        kind = (request.GET.get("kind") or "").strip()

        if day and start:
            try:
                from datetime import datetime
                from django.utils import timezone
                naive = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
                tz = timezone.get_current_timezone()
                initial["start_at"] = timezone.make_aware(naive, tz)
            except Exception:
                pass

        if loc:
            initial["location"] = loc

        if kind == "rent":
            initial.setdefault("kind", "rent")
            initial.setdefault("title", "Аренда")
            initial.setdefault("duration_min", 120)
            initial.setdefault("capacity", 1)
        elif kind == "personal":
            initial.setdefault("kind", "personal")
            initial.setdefault("title", "Персональное занятие")
            initial.setdefault("duration_min", 60)
            initial.setdefault("capacity", 1)
        elif kind == "group":
            initial.setdefault("kind", "group")
            initial.setdefault("title", "Групповое занятие")
            initial.setdefault("duration_min", 50)
            initial.setdefault("capacity", 20)

        return initial

    def save_model(self, request, obj, form, change):
        # ✅ если выбран workout — подтягиваем значения (но не ломаем, если админ явно поменял)
        if obj.workout:
            if not obj.title or obj.title.strip() == "Групповое занятие":
                obj.title = obj.workout.name
            if not obj.duration_min:
                obj.duration_min = obj.workout.default_duration_min
            if not obj.capacity:
                obj.capacity = obj.workout.default_capacity
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        Booking.objects.filter(session=obj).delete()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        Booking.objects.filter(session__in=queryset).delete()
        super().delete_queryset(request, queryset)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "membership", "session", "booking_status", "attendance_status", "created_at")
    list_filter = ("booking_status", "attendance_status", "session__location")
    search_fields = ("user__username", "user__first_name", "user__last_name", "session__title", "session__location")
    autocomplete_fields = ("user", "session", "membership")
    readonly_fields = ("created_at", "marked_at", "canceled_at")
