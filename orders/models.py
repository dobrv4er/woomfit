from django.conf import settings
from django.db import models


class Order(models.Model):
    STATUS = [
        ("new", "Новый"),
        ("payment_pending", "Ожидает оплату"),
        ("paid", "Оплачен"),
        ("canceled", "Отменен"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, choices=STATUS, default="new")
    total_rub = models.PositiveIntegerField(default=0)

    tb_payment_id = models.CharField(max_length=64, blank=True)
    tb_status = models.CharField(max_length=64, blank=True)

    fulfilled_at = models.DateTimeField(null=True, blank=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "shop.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=140)
    unit_price_rub = models.PositiveIntegerField(default=0)
    qty = models.PositiveIntegerField(default=1)
