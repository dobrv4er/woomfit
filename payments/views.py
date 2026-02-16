import json
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from decimal import Decimal

from orders.models import Order
from orders.services import fulfill_order

from loyalty.services import add_spent

from schedule.models import PaymentIntent, Booking


def _create_single_visit_membership(user):
    from memberships.models import Membership

    return Membership.objects.create(
        user=user,
        title="Разовое посещение",
        kind=Membership.Kind.VISITS,
        scope=Membership.Scope.GROUP,
        total_visits=1,
        left_visits=1,
        is_active=True,
    )


from .models import PaymentWebhookLog
from .tbank import TBankClient


def payment_success(request):
    return render(request, "payments/success.html")


def payment_fail(request):
    return render(request, "payments/fail.html")


@csrf_exempt
def tbank_webhook(request: HttpRequest):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse("BAD REQUEST", status=400)

    PaymentWebhookLog.objects.create(payload=data)

    client = TBankClient(settings.TBANK_TERMINAL_KEY, settings.TBANK_PASSWORD, settings.TBANK_IS_TEST)
    if settings.TBANK_PASSWORD and not client.validate_notification(data):
        return HttpResponse("INVALID TOKEN", status=400)

    order_id = str(data.get("OrderId", "")).strip()
    status = str(data.get("Status", "")).strip()
    success = str(data.get("Success", "")).lower() in ("true", "1", "yes")

    # --- заказы магазина ---
    if order_id.isdigit():
        order = Order.objects.filter(id=int(order_id)).first()
        if order:
            order.tb_status = status
            if success and status.upper() == "CONFIRMED":
                was_paid = (order.status == "paid")
                order.status = "paid"
                order.save(update_fields=["tb_status", "status"])
                if not was_paid:
                    fulfill_order(order)
                    if order.user_id:
                        add_spent(order.user, Decimal(str(order.total_rub)))
                return HttpResponse("OK", status=200, content_type="text/plain")
            elif status.upper() in ("CANCELED", "REJECTED", "DEADLINE_EXPIRED"):
                order.status = "canceled"
            order.save(update_fields=["tb_status", "status"])

    # --- оплата разового занятия: OrderId = S-<intent_id> ---
    if order_id.startswith("S-"):
        intent_id = order_id.split("-", 1)[1]
        if intent_id.isdigit():
            intent = PaymentIntent.objects.select_related("session", "user").filter(id=int(intent_id)).first()
            if intent:
                intent.tb_status = status

                if success and status.upper() == "CONFIRMED":
                    first_time = (intent.status != PaymentIntent.Status.PAID)
                    if first_time:
                        intent.status = PaymentIntent.Status.PAID
                        intent.paid_at = timezone.now()
                    intent.save(update_fields=["tb_status", "status", "paid_at"])

                    if first_time:
                        add_spent(intent.user, Decimal(str(intent.amount_rub)))

                    # после оплаты создаём абонемент на 1 посещение и сразу списываем
                    m = _create_single_visit_membership(intent.user)
                    m.consume_visit()

                    b, _ = Booking.objects.get_or_create(user=intent.user, session=intent.session)
                    b.booking_status = Booking.Status.BOOKED
                    b.canceled_at = None
                    b.membership = m
                    b.invite_sent_at = None
                    b.invite_expires_at = None
                    b.save(update_fields=[
                        "booking_status",
                        "canceled_at",
                        "membership",
                        "invite_sent_at",
                        "invite_expires_at",
                    ])
                    return HttpResponse("OK", status=200, content_type="text/plain")

                elif status.upper() in ("CANCELED", "REJECTED", "DEADLINE_EXPIRED"):
                    intent.status = PaymentIntent.Status.CANCELED
                    intent.save(update_fields=["tb_status", "status"])

    return HttpResponse("OK", status=200, content_type="text/plain")
