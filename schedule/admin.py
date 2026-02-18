from django import forms
from django.contrib import admin

from .models import Trainer, Session, Booking, Workout, RentRequest, RentPaymentIntent


class SessionAdminForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind", "group")
        client = cleaned.get("client")

        if kind == "personal" and not client:
            raise forms.ValidationError("Для персональной тренировки нужно указать клиента")

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
    ordering = ("name", "id")


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    autocomplete_fields = ("user", "membership")
    readonly_fields = ("created_at", "marked_at", "canceled_at")
    fields = ("user", "membership", "booking_status", "attendance_status", "created_at", "marked_at", "canceled_at")


class RentRequestInline(admin.StackedInline):
    model = RentRequest
    extra = 0
    can_delete = False
    readonly_fields = ("created_at",)
    fields = ("full_name", "email", "phone", "social_handle", "promo_code", "comment", "price_rub", "created_at", "user")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    form = SessionAdminForm
    list_display = (
        "id",
        "start_at",
        "title",
        "kind",
        "rent_payment_state",
        "workout",
        "client",
        "trainer",
        "location",
        "capacity",
        "duration_min",
    )
    list_filter = ("location", "trainer", "kind")
    search_fields = ("title", "location", "trainer__name", "workout__name")
    autocomplete_fields = ("trainer", "client", "workout")
    ordering = ("start_at",)
    inlines = (BookingInline, RentRequestInline)

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

    @admin.display(description="Статус аренды")
    def rent_payment_state(self, obj: Session):
        if obj.kind != Session.Kind.RENT:
            return ""
        try:
            obj.rent_request
        except RentRequest.DoesNotExist:
            return "Без заявки"
        return "Оплачено"

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
    search_fields = ("user__full_name", "user__phone", "session__title", "session__location")
    autocomplete_fields = ("user", "session", "membership")
    readonly_fields = ("created_at", "marked_at", "canceled_at")


@admin.register(RentRequest)
class RentRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "price_rub", "created_at", "session", "user")
    list_filter = ("created_at", "price_rub")
    search_fields = ("full_name", "phone", "email", "session__location")
    autocomplete_fields = ("session", "user")
    readonly_fields = ("created_at",)


@admin.register(RentPaymentIntent)
class RentPaymentIntentAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "status", "amount_rub", "slot_start", "expires_at", "session")
    list_filter = ("status", "created_at", "expires_at")
    search_fields = ("full_name", "phone", "email", "location", "tb_payment_id")
    autocomplete_fields = ("session", "user")
    readonly_fields = ("created_at", "paid_at")
