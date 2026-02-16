from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.urls import reverse

from payments.tbank import TBankClient
from shop.cart import Cart
from shop.models import Product

from wallet.services import debit, get_wallet

from .models import Order, OrderItem
from .services import fulfill_order


def _build_tbank_receipt_for_order(request, order: Order, cart_items: list, total_kopeks: int) -> dict:
    """Minimal Receipt for T-Bank Init.

    Receipt is required if online-cashbox is enabled on the terminal.
    Amount must equal sum(Items.Amount).
    """
    email = (getattr(order.user, "email", "") or "").strip() or "client@example.com"

    receipt_items = []
    sum_items = 0
    for it in cart_items:
        # Cart item fields: name, qty, price_rub, total_price_rub
        qty = int(it.qty)
        price_kopeks = int(it.price_rub) * 100
        amount = price_kopeks * qty
        sum_items += amount
        receipt_items.append(
            {
                "Name": str(it.name)[:128],
                "Price": price_kopeks,
                "Quantity": qty,
                "Amount": amount,
                "Tax": settings.TBANK_ITEM_TAX,
            }
        )

    # Safety: if rounding/discounts appear later, keep Receipt consistent with Amount.
    if sum_items != int(total_kopeks):
        receipt_items = [
            {
                "Name": f"Заказ №{order.id}",
                "Price": int(total_kopeks),
                "Quantity": 1,
                "Amount": int(total_kopeks),
                "Tax": settings.TBANK_ITEM_TAX,
            }
        ]

    return {
        "Email": email,
        "Taxation": settings.TBANK_TAXATION,
        "Items": receipt_items,
    }


@login_required
def checkout(request):
    cart = Cart(request)
    items = list(cart)
    if not items:
        return redirect("shop:cart")

    product_ids = [int(it.product_id) for it in items]
    products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    total = sum(int(it.total_price_rub) for it in items)

    order = Order.objects.create(user=request.user, total_rub=total, status="new")
    for it in items:
        prod = products_by_id.get(int(it.product_id))
        OrderItem.objects.create(
            order=order,
            product=prod,
            product_name=it.name,
            unit_price_rub=it.price_rub,
            qty=it.qty,
        )

    # ✅ Бесплатный заказ (пробное)
    if total <= 0:
        order.status = "paid"
        order.tb_status = "CONFIRMED"
        order.save(update_fields=["status", "tb_status"])
        fulfill_order(order)
        cart.clear()
        return redirect("payments:success")

    client = TBankClient(settings.TBANK_TERMINAL_KEY, settings.TBANK_PASSWORD, settings.TBANK_IS_TEST)

    notification_url = request.build_absolute_uri(reverse("payments:tbank_webhook"))
    success_url = request.build_absolute_uri(reverse("payments:success"))
    fail_url = request.build_absolute_uri(reverse("payments:fail"))

    total_kopeks = int(total) * 100
    receipt = _build_tbank_receipt_for_order(request, order, items, total_kopeks)

    pay = client.init_payment(
        order_id=str(order.id),
        amount_kopeks=total_kopeks,  # ✅ копейки
        description=f"WOOM FIT order #{order.id}",
        notification_url=notification_url,
        success_url=success_url,
        fail_url=fail_url,
        receipt=receipt,
    )

    if pay.get("Success"):
        order.tb_payment_id = str(pay.get("PaymentId") or "")
        order.tb_status = str(pay.get("Status") or "")
        order.status = "payment_pending"
        order.save(update_fields=["tb_payment_id", "tb_status", "status"])
        cart.clear()
        return redirect(pay["PaymentURL"])

    order.status = "canceled"
    order.tb_status = str(pay.get("Status") or "")
    order.save(update_fields=["status", "tb_status"])
    return render(request, "payments/fail.html", {"error": pay})


@login_required
def checkout_wallet(request):
    """Оплата корзины с баланса кошелька.

    Логика:
    - создаём Order + OrderItems так же, как в checkout()
    - если total == 0 → сразу paid
    - иначе пытаемся списать из wallet
    """
    if request.method != "POST":
        return redirect("shop:cart")

    cart = Cart(request)
    items = list(cart)
    if not items:
        return redirect("shop:cart")

    product_ids = [int(it.product_id) for it in items]
    products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    total = sum(int(it.total_price_rub) for it in items)

    # Проверяем баланс до создания заказа (UX), но окончательная проверка будет внутри debit() под транзакцией.
    wallet = get_wallet(request.user)
    if total > 0 and (wallet.balance or 0) < Decimal(str(total)):
        messages.error(request, "Недостаточно средств в кошельке.")
        return redirect("shop:cart")

    # Создаём заказ
    order = Order.objects.create(user=request.user, total_rub=total, status="new")
    for it in items:
        prod = products_by_id.get(int(it.product_id))
        OrderItem.objects.create(
            order=order,
            product=prod,
            product_name=it.name,
            unit_price_rub=it.price_rub,
            qty=it.qty,
        )

    # Бесплатный заказ
    if total <= 0:
        order.status = "paid"
        order.tb_status = "WALLET_FREE"
        order.save(update_fields=["status", "tb_status"])
        fulfill_order(order)
        cart.clear()
        return redirect("payments:success")

    try:
        debit(request.user, Decimal(str(total)), reason=f"Оплата заказа #{order.id} (магазин)")
    except ValidationError as e:
        # Если дебет не прошёл — отменяем заказ и возвращаем корзину
        order.status = "canceled"
        order.tb_status = "WALLET_DECLINED"
        order.save(update_fields=["status", "tb_status"])
        messages.error(request, str(e) or "Не удалось оплатить кошельком.")
        return redirect("shop:cart")

    order.status = "paid"
    order.tb_status = "WALLET_PAID"
    order.save(update_fields=["status", "tb_status"])
    fulfill_order(order)
    cart.clear()
    return redirect("payments:success")
