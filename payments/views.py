import json
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from decimal import Decimal

from core.telegram_notify import (
    notify_booking_created,
    notify_order_payment,
    notify_rent_request_paid,
    notify_session_payment,
)
from loyalty.services import grant_cashback
from orders.models import Order
from orders.services import fulfill_order
from shop.models import Product

from schedule.models import PaymentIntent, Booking, RentPaymentIntent, RentRequest, Session, Trainer


RENT_TRAINER_NAME = "Аренда зала"


def _order_purchase_summary(order: Order, *, max_items: int = 5, max_len: int = 220) -> str:
    items = list(order.items.all())
    if not items:
        return ""

    parts = []
    for it in items[:max_items]:
        qty = int(it.qty or 0)
        name = (it.product_name or "").strip() or "Товар"
        parts.append(f"{name} x{qty}")
    if len(items) > max_items:
        parts.append(f"+{len(items) - max_items} поз.")

    summary = ", ".join(parts).strip()
    if len(summary) <= max_len:
        return summary
    return summary[: max_len - 1].rstrip() + "…"


def _order_membership_total(order: Order) -> Decimal:
    total = Decimal("0.00")
    for item in order.items.select_related("product").all():
        product = item.product
        if not product or product.grant_kind != Product.GrantKind.MEMBERSHIP:
            continue
        qty = int(item.qty or 0)
        price = int(item.unit_price_rub or 0)
        if qty <= 0 or price <= 0:
            continue
        total += Decimal(str(price * qty))
    return total


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


def _norm_addr(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", s)


def _intervals_overlap(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def _sessions_for_location_between(*, location: str, range_start, range_end, lock: bool = False):
    qs = Session.objects.filter(start_at__lt=range_end, start_at__gte=range_start).order_by("start_at")
    if lock:
        qs = qs.select_for_update()
    target = _norm_addr(location)
    sessions = []
    for s in qs:
        if _norm_addr(s.location) == target:
            sessions.append(s)
    return sessions


def _finalize_rent_intent(intent: RentPaymentIntent, tb_status: str) -> None:
    with transaction.atomic():
        locked = RentPaymentIntent.objects.select_for_update().filter(id=intent.id).first()
        if not locked:
            return

        locked.tb_status = tb_status
        if locked.status == RentPaymentIntent.Status.PAID:
            locked.save(update_fields=["tb_status"])
            return
        if locked.status == RentPaymentIntent.Status.CANCELED:
            locked.save(update_fields=["tb_status"])
            return

        now = timezone.now()
        if locked.expires_at <= now:
            locked.status = RentPaymentIntent.Status.CANCELED
            locked.save(update_fields=["tb_status", "status"])
            return

        slot_start = timezone.localtime(locked.slot_start)
        duration = max(1, int(locked.duration_min or 0))
        slot_end = slot_start + timedelta(minutes=duration)

        sessions = _sessions_for_location_between(
            location=locked.location,
            range_start=slot_start - timedelta(days=1),
            range_end=slot_end + timedelta(days=1),
            lock=True,
        )
        for s in sessions:
            s_start = timezone.localtime(s.start_at)
            s_end = s_start + timedelta(minutes=max(1, int(s.duration_min or 0)))
            if _intervals_overlap(slot_start, slot_end, s_start, s_end):
                locked.status = RentPaymentIntent.Status.CANCELED
                locked.tb_status = "SLOT_CONFLICT"
                locked.save(update_fields=["tb_status", "status"])
                return

        trainer, _ = Trainer.objects.get_or_create(name=RENT_TRAINER_NAME)
        session_title = f"Аренда зала — {locked.full_name}".strip()[:160]
        rent_session = Session.objects.create(
            title=session_title or "Аренда зала",
            kind=Session.Kind.RENT,
            client=locked.user,
            start_at=slot_start,
            duration_min=duration,
            location=locked.location,
            trainer=trainer,
            capacity=1,
        )

        rent_request = RentRequest.objects.create(
            session=rent_session,
            user=locked.user,
            full_name=locked.full_name,
            email=locked.email,
            phone=locked.phone,
            social_handle=locked.social_handle,
            comment=locked.comment,
            promo_code=locked.promo_code,
            price_rub=locked.amount_rub,
        )

        locked.session = rent_session
        locked.status = RentPaymentIntent.Status.PAID
        locked.paid_at = now
        locked.save(update_fields=["tb_status", "session", "status", "paid_at"])

    notify_rent_request_paid(session=rent_session, request_obj=rent_request)


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
                        grant_cashback(
                            user=order.user,
                            base_amount=_order_membership_total(order),
                            source_type="order",
                            source_id=order.id,
                            reason=f"Кэшбек за заказ #{order.id}",
                        )
                    notify_order_payment(
                        user=order.user,
                        order_id=order.id,
                        amount_rub=order.total_rub,
                        method="Онлайн (T-Bank)",
                        purchase=_order_purchase_summary(order),
                    )
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

                    if not first_time:
                        return HttpResponse("OK", status=200, content_type="text/plain")

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
                    notify_session_payment(
                        user=intent.user,
                        session=intent.session,
                        amount_rub=intent.amount_rub,
                        method="Онлайн (T-Bank)",
                    )
                    notify_booking_created(
                        user=intent.user,
                        session=intent.session,
                        source="Разовая оплата (онлайн)",
                    )
                    return HttpResponse("OK", status=200, content_type="text/plain")

                elif status.upper() in ("CANCELED", "REJECTED", "DEADLINE_EXPIRED"):
                    intent.status = PaymentIntent.Status.CANCELED
                    intent.save(update_fields=["tb_status", "status"])

    # --- оплата аренды: OrderId = R-<intent_id> ---
    if order_id.startswith("R-"):
        intent_id = order_id.split("-", 1)[1]
        if intent_id.isdigit():
            intent = RentPaymentIntent.objects.filter(id=int(intent_id)).first()
            if intent:
                if success and status.upper() == "CONFIRMED":
                    _finalize_rent_intent(intent, status)
                    return HttpResponse("OK", status=200, content_type="text/plain")

                if status.upper() in ("CANCELED", "REJECTED", "DEADLINE_EXPIRED"):
                    intent.tb_status = status
                    if intent.status != RentPaymentIntent.Status.PAID:
                        intent.status = RentPaymentIntent.Status.CANCELED
                    intent.save(update_fields=["tb_status", "status"])
                    return HttpResponse("OK", status=200, content_type="text/plain")

                intent.tb_status = status
                intent.save(update_fields=["tb_status"])

    return HttpResponse("OK", status=200, content_type="text/plain")
