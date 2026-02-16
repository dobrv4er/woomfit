from django.db import models
class PaymentWebhookLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
