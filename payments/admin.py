from django.contrib import admin
from .models import PaymentWebhookLog

@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display=("id","created_at")
