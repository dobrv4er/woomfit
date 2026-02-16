from django.contrib import admin
from .models import Order, OrderItem
from .services import fulfill_order

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display=("id","created_at","user","status","total_rub","tb_payment_id","tb_status","fulfilled_at")
    list_filter=("status",)
    inlines=[OrderItemInline]

    actions = ["action_fulfill"]

    @admin.action(description="Выдать покупки (абонемент/кошелёк) и отметить fulfilled")
    def action_fulfill(self, request, queryset):
        ok = 0
        for o in queryset:
            if fulfill_order(o):
                ok += 1
        self.message_user(request, f"Готово. Выдано для {ok} заказ(ов).")
