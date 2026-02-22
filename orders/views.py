from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from core.legal import client_ip, is_checked
from payments.integrationjs import build_widget_init_data, is_widget_request
from payments.receipt import build_receipt, receipt_item
from payments.tbank import TBankClient
from payments.tbank_urls import fail_url, notification_url, success_url
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
    receipt_items = []
    sum_items = 0
    for it in cart_items:
        # Cart item fields: name, qty, price_rub, total_price_rub
        qty = int(it.qty)
        price_kopeks = int(it.price_rub) * 100
        amount = price_kopeks * qty
        sum_items += amount
        receipt_items.append(receipt_item(name=it.name, price_kopeks=price_kopeks, quantity=qty, amount_kopeks=amount))

    # Safety: if rounding/discounts appear later, keep Receipt consistent with Amount.
    if sum_items != int(total_kopeks):
        receipt_items = [
            receipt_item(name=f"Заказ №{order.id}", price_kopeks=int(total_kopeks), quantity=1, amount_kopeks=int(total_kopeks))
        ]

    return build_receipt(order.user, receipt_items)


def _cart_purchase_summary(cart_items: list, *, max_items: int = 5, max_len: int = 140) -> str:
    if not cart_items:
        return ""

    parts = []
    for it in cart_items[:max_items]:
        qty = int(it.qty or 0)
        name = (it.name or "").strip() or "Товар"
        parts.append(f"{name} x{qty}")
    if len(cart_items) > max_items:
        parts.append(f"+{len(cart_items) - max_items} поз.")

    summary = ", ".join(parts).strip()
    if len(summary) <= max_len:
        return summary
    return summary[: max_len - 1].rstrip() + "…"


def _checkout_legal_ok(request) -> bool:
    offer_ok = is_checked(request, "agree_offer")
    pd_ok = is_checked(request, "agree_personal_data")
    if not offer_ok or not pd_ok:
        messages.error(
            request,
            "Для оплаты необходимо принять публичную оферту и согласие на обработку персональных данных.",
        )
        return False
    return True


@login_required
def checkout(request):
    if request.method != "POST":
        return redirect("shop:cart")
    widget_request = is_widget_request(request)
    if not _checkout_legal_ok(request):
        if widget_request:
            return JsonResponse(
                {"error": "Для оплаты необходимо принять оферту и согласие на обработку персональных данных."},
                status=400,
            )
        return redirect("shop:cart")

    cart = Cart(request)
    items = list(cart)
    if not items:
        if widget_request:
            return JsonResponse({"error": "Корзина пуста."}, status=400)
        return redirect("shop:cart")

    product_ids = [int(it.product_id) for it in items]
    products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    total = sum(int(it.total_price_rub) for it in items)

    order = Order.objects.create(
        user=request.user,
        total_rub=total,
        status="new",
        legal_accepted_at=timezone.now(),
        legal_accept_ip=client_ip(request),
    )
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
        if widget_request:
            success_redirect_url = request.build_absolute_uri(reverse("payments:success"))
            return JsonResponse({"paymentUrl": success_redirect_url, "PaymentURL": success_redirect_url})
        return redirect("payments:success")

    client = TBankClient(settings.TBANK_TERMINAL_KEY, settings.TBANK_PASSWORD, settings.TBANK_IS_TEST)

    notify_url = notification_url(request)
    ok_url = success_url(request, setting_name="TBANK_SUCCESS_URL", view_name="payments:success")
    no_url = fail_url(request, setting_name="TBANK_FAIL_URL", view_name="payments:fail")

    total_kopeks = int(total) * 100
    receipt = _build_tbank_receipt_for_order(request, order, items, total_kopeks)

    try:
        pay = client.init_payment(
            order_id=str(order.id),
            amount_kopeks=total_kopeks,  # ✅ копейки
            description=f"WOOM FIT order #{order.id}",
            notification_url=notify_url,
            success_url=ok_url,
            fail_url=no_url,
            receipt=receipt,
            data=build_widget_init_data(request),
            extra={"PayType": settings.TBANK_PAY_TYPE} if settings.TBANK_PAY_TYPE else None,
        )
    except Exception as exc:
        order.status = "canceled"
        order.tb_status = "INIT_FAILED"
        order.save(update_fields=["status", "tb_status"])
        if widget_request:
            return JsonResponse({"error": "Не удалось создать онлайн-оплату.", "details": str(exc)}, status=400)
        return render(request, "payments/fail.html", {"error": {"Message": "Init failed", "Details": str(exc)}})

    payment_url = str(pay.get("PaymentURL") or "").strip()
    if pay.get("Success") and payment_url:
        order.tb_payment_id = str(pay.get("PaymentId") or "")
        order.tb_status = str(pay.get("Status") or "")
        order.status = "payment_pending"
        order.save(update_fields=["tb_payment_id", "tb_status", "status"])
        cart.clear()
        if widget_request:
            return JsonResponse({"paymentUrl": payment_url, "PaymentURL": payment_url})
        return redirect(payment_url)

    order.status = "canceled"
    order.tb_status = str(pay.get("Status") or "")
    order.save(update_fields=["status", "tb_status"])
    if widget_request:
        return JsonResponse({"error": "Не удалось создать онлайн-оплату.", "details": pay}, status=400)
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
    if not _checkout_legal_ok(request):
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
    order = Order.objects.create(
        user=request.user,
        total_rub=total,
        status="new",
        legal_accepted_at=timezone.now(),
        legal_accept_ip=client_ip(request),
    )
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
        purchase_summary = _cart_purchase_summary(items)
        reason = f"Оплата заказа #{order.id}: {purchase_summary}" if purchase_summary else f"Оплата заказа #{order.id}"
        debit(request.user, Decimal(str(total)), reason=reason)
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
