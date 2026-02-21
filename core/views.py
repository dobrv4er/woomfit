from datetime import date, datetime, time, timedelta
import re
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from core.telegram_notify import notify_rent_request_paid
from schedule.models import Booking, Trainer, Session, RentPaymentIntent, RentRequest


def home(request):
    my_bookings = []
    if request.user.is_authenticated:
        my_bookings = (
            Booking.objects.select_related("session")
            .filter(user=request.user, booking_status=Booking.Status.BOOKED)
            .order_by("session__start_at")
        )

    return render(request, "core/home.html", {"my_bookings": my_bookings})


def _legal_meta() -> dict:
    studio_addresses = [
        str(x).strip()
        for x in getattr(settings, "LEGAL_STUDIO_ADDRESSES", [])
        if str(x).strip()
    ]
    return {
        "brand_name": (getattr(settings, "LEGAL_BRAND_NAME", "WOOM FIT") or "WOOM FIT").strip(),
        "operator_name": (getattr(settings, "LEGAL_OPERATOR_NAME", "") or "").strip(),
        "operator_address": (getattr(settings, "LEGAL_OPERATOR_ADDRESS", "") or "").strip(),
        "operator_email": (getattr(settings, "LEGAL_OPERATOR_EMAIL", "support@woomfit.ru") or "support@woomfit.ru").strip(),
        "operator_phone": (getattr(settings, "LEGAL_OPERATOR_PHONE", "") or "").strip(),
        "operator_inn": (getattr(settings, "LEGAL_OPERATOR_INN", "") or "").strip(),
        "operator_ogrn": (getattr(settings, "LEGAL_OPERATOR_OGRN", "") or "").strip(),
        "operator_website": (getattr(settings, "LEGAL_OPERATOR_WEBSITE", "") or "").strip(),
        "studio_addresses": studio_addresses,
        "bank_account": (getattr(settings, "LEGAL_BANK_ACCOUNT", "") or "").strip(),
        "bank_name": (getattr(settings, "LEGAL_BANK_NAME", "") or "").strip(),
        "bank_bik": (getattr(settings, "LEGAL_BANK_BIK", "") or "").strip(),
        "bank_corr_account": (getattr(settings, "LEGAL_BANK_CORR_ACCOUNT", "") or "").strip(),
        "bank_address": (getattr(settings, "LEGAL_BANK_ADDRESS", "") or "").strip(),
    }


def _required_or_placeholder(value: str) -> str:
    value = (value or "").strip()
    return value if value else "НЕ ЗАПОЛНЕНО"


def _requisites_lines(meta: dict) -> list[str]:
    lines = [
        f"Оператор: {_required_or_placeholder(meta['operator_name'])}",
        f"ИНН: {_required_or_placeholder(meta['operator_inn'])}",
        f"ОГРН/ОГРНИП: {_required_or_placeholder(meta['operator_ogrn'])}",
        f"Адрес регистрации: {_required_or_placeholder(meta['operator_address'])}",
        f"E-mail: {_required_or_placeholder(meta['operator_email'])}",
        f"Телефон: {_required_or_placeholder(meta['operator_phone'])}",
        f"Р/с: {_required_or_placeholder(meta['bank_account'])}",
        f"Банк: {_required_or_placeholder(meta['bank_name'])}",
        f"БИК: {_required_or_placeholder(meta['bank_bik'])}",
        f"Корр. счёт: {_required_or_placeholder(meta['bank_corr_account'])}",
        f"Юридический адрес банка: {_required_or_placeholder(meta['bank_address'])}",
    ]
    if meta["studio_addresses"]:
        lines.append("Адреса студий:")
        lines.extend([f"• {addr}" for addr in meta["studio_addresses"]])
    if meta["operator_website"]:
        lines.append(f"Сайт: {meta['operator_website']}")
    return lines


def _phone_to_tel(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if not digits:
        return ""
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return f"+{digits}"


def about(request):
    meta = _legal_meta()
    return render(request, "core/static_page.html", {
        "title": "О клубе",
        "subtitle": "Информация о нас, контактная информация и телефоны",
        "lines": [
            f"{meta['brand_name']} — студия тренировок.",
            f"Контакты: {_required_or_placeholder(meta['operator_phone'])}, {_required_or_placeholder(meta['operator_email'])}.",
            f"Адрес оператора: {_required_or_placeholder(meta['operator_address'])}.",
        ]
    })


def trainers(request):
    return render(request, "core/trainers.html", {"trainers": Trainer.objects.order_by('name')})


RENT_OPEN_HOUR = 8
RENT_CLOSE_HOUR = 22
RENT_SLOT_MIN = 60
RENT_PRICE_RUB = 650
RENT_PAYMENT_TTL_MIN = 15
RENT_LOCATION_FALLBACK = "Сакко и Ванцетти, 93а"
RENT_LOCATION_TOKEN = "саккоиванцетти"
RENT_TRAINER_NAME = "Аренда зала"
_RU_WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def _parse_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _norm_addr(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", s)


def _rent_location() -> str:
    locations = [x.strip() for x in getattr(settings, "WOOMFIT_LOCATIONS", []) if str(x).strip()]
    for loc in locations:
        if RENT_LOCATION_TOKEN in _norm_addr(loc):
            return loc
    return RENT_LOCATION_FALLBACK


def _slot_start(day: date, hour: int):
    tz = timezone.get_current_timezone()
    naive = datetime.combine(day, time(hour=hour, minute=0))
    return timezone.make_aware(naive, tz)


def _slot_key(dt):
    local_dt = timezone.localtime(dt)
    return local_dt.strftime("%Y-%m-%dT%H:%M")


def _parse_slot_key(raw: str):
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    tz = timezone.get_current_timezone()
    return timezone.make_aware(naive, tz)


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


def _expire_rent_payment_intents() -> None:
    RentPaymentIntent.objects.filter(
        status__in=(RentPaymentIntent.Status.NEW, RentPaymentIntent.Status.PENDING),
        expires_at__lte=timezone.now(),
    ).update(status=RentPaymentIntent.Status.CANCELED, tb_status="DEADLINE_EXPIRED")


def _pending_intents_for_location_between(
    *,
    location: str,
    range_start,
    range_end,
    lock: bool = False,
    exclude_intent_id: int | None = None,
):
    now = timezone.now()
    qs = (
        RentPaymentIntent.objects
        .filter(slot_start__lt=range_end, slot_start__gte=range_start)
        .filter(status__in=(RentPaymentIntent.Status.NEW, RentPaymentIntent.Status.PENDING))
        .filter(expires_at__gt=now)
        .order_by("slot_start")
    )
    if exclude_intent_id:
        qs = qs.exclude(id=exclude_intent_id)
    if lock:
        qs = qs.select_for_update()

    target = _norm_addr(location)
    intents = []
    for intent in qs:
        if _norm_addr(intent.location) == target:
            intents.append(intent)
    return intents


def _slot_is_busy(slot_start, sessions: list[Session], pending_intents: list[RentPaymentIntent]) -> bool:
    slot_end = slot_start + timedelta(minutes=RENT_SLOT_MIN)
    for s in sessions:
        s_start = timezone.localtime(s.start_at)
        s_end = s_start + timedelta(minutes=max(1, int(s.duration_min or 0)))
        if _intervals_overlap(slot_start, slot_end, s_start, s_end):
            return True
    for intent in pending_intents:
        i_start = timezone.localtime(intent.slot_start)
        i_end = i_start + timedelta(minutes=max(1, int(intent.duration_min or 0)))
        if _intervals_overlap(slot_start, slot_end, i_start, i_end):
            return True
    return False


def _busy_slot_states_for_week(*, week_start: date, location: str, viewer_user_id: int | None = None) -> dict[str, str]:
    week_end = week_start + timedelta(days=7)
    week_start_dt = _slot_start(week_start, 0)
    week_end_dt = _slot_start(week_end, 0)
    sessions = _sessions_for_location_between(
        location=location,
        range_start=week_start_dt - timedelta(days=1),
        range_end=week_end_dt + timedelta(days=1),
    )
    pending_intents = _pending_intents_for_location_between(
        location=location,
        range_start=week_start_dt,
        range_end=week_end_dt,
    )

    busy_states: dict[str, str] = {}
    priority = {"pending": 1, "busy": 2, "training": 2, "rent_paid": 3}

    def put_state(slot_key: str, state: str):
        current = busy_states.get(slot_key)
        if not current or priority[state] > priority[current]:
            busy_states[slot_key] = state

    for s in sessions:
        s_start = timezone.localtime(s.start_at)
        s_end = s_start + timedelta(minutes=max(1, int(s.duration_min or 0)))
        if s.kind == Session.Kind.RENT:
            state = "rent_paid" if (viewer_user_id and s.client_id == viewer_user_id) else "busy"
        else:
            state = "training"
        cur = s_start.replace(minute=0, second=0, microsecond=0)
        while cur < s_end:
            cur_end = cur + timedelta(hours=1)
            if (
                week_start <= cur.date() < week_end
                and RENT_OPEN_HOUR <= cur.hour < RENT_CLOSE_HOUR
                and _intervals_overlap(cur, cur_end, s_start, s_end)
            ):
                put_state(_slot_key(cur), state)
            cur = cur_end

    for intent in pending_intents:
        i_start = timezone.localtime(intent.slot_start)
        i_end = i_start + timedelta(minutes=max(1, int(intent.duration_min or 0)))
        cur = i_start.replace(minute=0, second=0, microsecond=0)
        while cur < i_end:
            cur_end = cur + timedelta(hours=1)
            if (
                week_start <= cur.date() < week_end
                and RENT_OPEN_HOUR <= cur.hour < RENT_CLOSE_HOUR
                and _intervals_overlap(cur, cur_end, i_start, i_end)
            ):
                put_state(_slot_key(cur), "pending")
            cur = cur_end

    return busy_states


def _slot_label(slot_start) -> str:
    local_start = timezone.localtime(slot_start)
    local_end = local_start + timedelta(minutes=RENT_SLOT_MIN)
    return f"{local_start.strftime('%d.%m.%Y %H:%M')} - {local_end.strftime('%H:%M')}"


def _initial_rent_contact(request):
    full_name = ""
    email = ""
    phone = ""
    if request.user.is_authenticated:
        full_name = (request.user.get_full_name() or "").strip()
        email = (request.user.email or "").strip()
        phone = (request.user.phone or "").strip()
    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "social_handle": "",
        "comment": "",
        "promo_code": "",
    }


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D+", "", raw or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    return digits


def rent(request):
    _expire_rent_payment_intents()

    today = timezone.localdate()
    selected_week = _parse_iso_date(request.GET.get("week") or request.POST.get("week") or "") or today
    if selected_week < today:
        selected_week = today

    rent_location = _rent_location()
    wallet_balance = None
    if request.user.is_authenticated:
        from wallet.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        wallet_balance = wallet.balance

    selected_slot = request.POST.get("slot", "").strip() if request.method == "POST" else (request.GET.get("slot", "").strip())
    contact = _initial_rent_contact(request)
    if request.method == "POST":
        contact.update({
            "full_name": (request.POST.get("full_name") or "").strip(),
            "email": (request.POST.get("email") or "").strip(),
            "phone": (request.POST.get("phone") or "").strip(),
            "social_handle": (request.POST.get("social_handle") or "").strip(),
            "comment": (request.POST.get("comment") or "").strip(),
            "promo_code": (request.POST.get("promo_code") or "").strip(),
        })

    selected_slot_start = _parse_slot_key(selected_slot)
    payment_method = ((request.POST.get("method") or "online").strip() if request.method == "POST" else "online")
    intent_for_redirect = None

    if request.method == "POST":
        if payment_method not in {"online", "wallet"}:
            messages.error(request, "Выберите способ оплаты.")
        elif payment_method == "wallet" and not request.user.is_authenticated:
            messages.error(request, "Для оплаты из кошелька войдите в аккаунт.")
        elif not selected_slot_start:
            messages.error(request, "Выберите свободный слот в сетке.")
        elif selected_slot_start <= timezone.localtime(timezone.now()):
            messages.error(request, "Нельзя бронировать прошедшее время.")
        elif not (RENT_OPEN_HOUR <= selected_slot_start.hour < RENT_CLOSE_HOUR):
            messages.error(request, "Выберите слот в рабочем диапазоне аренды.")
        elif not contact["full_name"]:
            messages.error(request, "Укажите имя.")
        else:
            phone_digits = _clean_phone(contact["phone"])
            if len(phone_digits) != 11 or not phone_digits.startswith("7"):
                messages.error(request, "Телефон должен быть в формате +7 999 999 99 99.")
            else:
                with transaction.atomic():
                    slot_end = selected_slot_start + timedelta(minutes=RENT_SLOT_MIN)
                    sessions = _sessions_for_location_between(
                        location=rent_location,
                        range_start=selected_slot_start - timedelta(days=1),
                        range_end=slot_end + timedelta(days=1),
                        lock=True,
                    )
                    pending_intents = _pending_intents_for_location_between(
                        location=rent_location,
                        range_start=selected_slot_start - timedelta(days=1),
                        range_end=slot_end + timedelta(days=1),
                        lock=True,
                    )
                    if _slot_is_busy(selected_slot_start, sessions, pending_intents):
                        messages.error(request, "Этот слот уже занят. Выберите другой.")
                    else:
                        now = timezone.now()
                        intent_for_redirect = RentPaymentIntent.objects.create(
                            user=request.user if request.user.is_authenticated else None,
                            location=rent_location,
                            slot_start=selected_slot_start,
                            duration_min=RENT_SLOT_MIN,
                            full_name=contact["full_name"],
                            email=contact["email"],
                            phone=phone_digits,
                            social_handle=contact["social_handle"],
                            comment=contact["comment"],
                            promo_code=contact["promo_code"],
                            amount_rub=RENT_PRICE_RUB,
                            expires_at=now + timedelta(minutes=RENT_PAYMENT_TTL_MIN),
                            status=RentPaymentIntent.Status.NEW,
                        )
                        if payment_method == "wallet":
                            from wallet.services import debit

                            try:
                                debit(
                                    request.user,
                                    Decimal(str(RENT_PRICE_RUB)),
                                    reason=(
                                        f"Оплата аренды зала: {rent_location} "
                                        f"({timezone.localtime(selected_slot_start).strftime('%d.%m %H:%M')})"
                                    ),
                                )
                            except ValidationError:
                                messages.error(request, "Недостаточно средств в кошельке.")
                                intent_for_redirect.status = RentPaymentIntent.Status.CANCELED
                                intent_for_redirect.tb_status = "WALLET_INSUFFICIENT"
                                intent_for_redirect.save(update_fields=["status", "tb_status"])
                            else:
                                trainer, _ = Trainer.objects.get_or_create(name=RENT_TRAINER_NAME)
                                session_title = f"Аренда зала — {contact['full_name']}".strip()[:160]
                                rent_session = Session.objects.create(
                                    title=session_title or "Аренда зала",
                                    kind=Session.Kind.RENT,
                                    client=request.user,
                                    start_at=selected_slot_start,
                                    duration_min=RENT_SLOT_MIN,
                                    location=rent_location,
                                    trainer=trainer,
                                    capacity=1,
                                )
                                rent_request = RentRequest.objects.create(
                                    session=rent_session,
                                    user=request.user,
                                    full_name=contact["full_name"],
                                    email=contact["email"],
                                    phone=phone_digits,
                                    social_handle=contact["social_handle"],
                                    comment=contact["comment"],
                                    promo_code=contact["promo_code"],
                                    price_rub=RENT_PRICE_RUB,
                                )

                                intent_for_redirect.session = rent_session
                                intent_for_redirect.status = RentPaymentIntent.Status.PAID
                                intent_for_redirect.tb_status = "WALLET_PAID"
                                intent_for_redirect.paid_at = now
                                intent_for_redirect.save(update_fields=["session", "status", "tb_status", "paid_at"])

                                notify_rent_request_paid(session=rent_session, request_obj=rent_request)
                                messages.success(request, f"Оплата прошла. Бронь подтверждена: {_slot_label(selected_slot_start)}")
                                return redirect(f"{reverse('core:rent')}?week={selected_week.isoformat()}")

        if intent_for_redirect and payment_method == "online":
            from payments.receipt import build_receipt, receipt_item
            from payments.tbank import TBankClient

            client = TBankClient(settings.TBANK_TERMINAL_KEY, settings.TBANK_PASSWORD, settings.TBANK_IS_TEST)
            notification_url = request.build_absolute_uri(reverse("payments:tbank_webhook"))
            success_url = request.build_absolute_uri(reverse("core:rent_pay_success", args=[intent_for_redirect.id]))
            fail_url = request.build_absolute_uri(reverse("core:rent_pay_fail", args=[intent_for_redirect.id]))
            amount_kopeks = int(RENT_PRICE_RUB) * 100
            receipt = build_receipt(
                request.user if request.user.is_authenticated else None,
                [receipt_item(name=f"Аренда зала: {rent_location}", price_kopeks=amount_kopeks, quantity=1)],
            )
            try:
                pay = client.init_payment(
                    order_id=f"R-{intent_for_redirect.id}",
                    amount_kopeks=amount_kopeks,
                    description=f"WOOM FIT rent intent #{intent_for_redirect.id}",
                    notification_url=notification_url,
                    success_url=success_url,
                    fail_url=fail_url,
                    receipt=receipt,
                    redirect_due_date=intent_for_redirect.expires_at.isoformat(timespec="seconds"),
                )
            except Exception:
                intent_for_redirect.status = RentPaymentIntent.Status.CANCELED
                intent_for_redirect.tb_status = "INIT_FAILED"
                intent_for_redirect.save(update_fields=["status", "tb_status"])
                messages.error(request, "Не удалось создать оплату. Попробуйте ещё раз.")
                return redirect(f"{reverse('core:rent')}?week={selected_week.isoformat()}")

            if pay.get("Success"):
                intent_for_redirect.tb_payment_id = str(pay.get("PaymentId") or "")
                intent_for_redirect.tb_status = str(pay.get("Status") or "")
                intent_for_redirect.status = RentPaymentIntent.Status.PENDING
                intent_for_redirect.save(update_fields=["tb_payment_id", "tb_status", "status"])
                return redirect(pay["PaymentURL"])

            intent_for_redirect.status = RentPaymentIntent.Status.CANCELED
            intent_for_redirect.tb_status = str(pay.get("Status") or "")
            intent_for_redirect.save(update_fields=["status", "tb_status"])
            messages.error(request, "Не удалось создать оплату. Попробуйте ещё раз.")

    week_days = [selected_week + timedelta(days=i) for i in range(7)]
    week_start_dt = _slot_start(selected_week, 0)
    week_end_dt = _slot_start(selected_week + timedelta(days=7), 0)
    viewer_user_id = request.user.id if request.user.is_authenticated else None
    busy_states = _busy_slot_states_for_week(
        week_start=selected_week,
        location=rent_location,
        viewer_user_id=viewer_user_id,
    )
    now_local = timezone.localtime(timezone.now())

    booked_slots = []
    if viewer_user_id:
        paid_rent_sessions = [
            s for s in _sessions_for_location_between(
                location=rent_location,
                range_start=week_start_dt,
                range_end=week_end_dt,
            )
            if s.kind == Session.Kind.RENT and s.client_id == viewer_user_id
        ]
        for s in paid_rent_sessions:
            start_local = timezone.localtime(s.start_at)
            end_local = start_local + timedelta(minutes=max(1, int(s.duration_min or 0)))
            booked_slots.append({
                "day_label": f"{_RU_WEEKDAYS[start_local.weekday()]}, {start_local.strftime('%d.%m')}",
                "time_label": f"{start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}",
            })

    rows = []
    for hour in range(RENT_OPEN_HOUR, RENT_CLOSE_HOUR):
        row = {"label": f"{hour:02d}:00", "cells": []}
        for day_obj in week_days:
            cell_start = _slot_start(day_obj, hour)
            key = _slot_key(cell_start)
            state = busy_states.get(key, "")
            is_busy = bool(state)
            is_past = cell_start <= now_local
            row["cells"].append({
                "key": key,
                "state": state,
                "is_busy": is_busy,
                "is_past": is_past,
                "is_selected": selected_slot == key,
                "label": f"{day_obj.strftime('%d.%m')} {hour:02d}:00-{(hour + 1):02d}:00",
            })
        rows.append(row)

    show_my_paid_rent_legend = any(
        cell.get("state") == "rent_paid"
        for row in rows
        for cell in row.get("cells", [])
    )

    selected_slot_label = _slot_label(selected_slot_start) if selected_slot_start else ""

    return render(request, "core/rent.html", {
        "location": rent_location,
        "week_label": f"{week_days[0].strftime('%d.%m')} — {week_days[-1].strftime('%d.%m')}",
        "prev_week_iso": (selected_week - timedelta(days=7)).isoformat(),
        "next_week_iso": (selected_week + timedelta(days=7)).isoformat(),
        "can_prev_week": selected_week > today,
        "days": [
            {"iso": d.isoformat(), "weekday": _RU_WEEKDAYS[d.weekday()], "day": d.day}
            for d in week_days
        ],
        "rows": rows,
        "selected_slot": selected_slot,
        "selected_slot_label": selected_slot_label,
        "price_rub": RENT_PRICE_RUB,
        "payment_ttl_min": RENT_PAYMENT_TTL_MIN,
        "wallet_balance": wallet_balance,
        "contact": contact,
        "selected_week_iso": selected_week.isoformat(),
        "booked_slots": booked_slots,
        "show_paid_rent_details": bool(viewer_user_id),
        "show_my_paid_rent_legend": show_my_paid_rent_legend,
    })


def rent_pay_success(request, intent_id: int):
    _expire_rent_payment_intents()
    intent = get_object_or_404(RentPaymentIntent, id=intent_id)
    back_week_iso = timezone.localtime(intent.slot_start).date().isoformat()

    if intent.status == RentPaymentIntent.Status.PAID:
        messages.success(request, "Оплата прошла. Бронь аренды подтверждена.")
        return redirect(f"{reverse('core:rent')}?week={back_week_iso}")
    if intent.status == RentPaymentIntent.Status.CANCELED:
        messages.error(request, "Оплата не завершена или время на оплату истекло.")
        return redirect(f"{reverse('core:rent')}?week={back_week_iso}")

    seconds_left = int(max(0, (intent.expires_at - timezone.now()).total_seconds()))
    return render(request, "core/rent_pay_success.html", {
        "intent": intent,
        "seconds_left": seconds_left,
        "back_week_iso": back_week_iso,
    })


def rent_pay_fail(request, intent_id: int):
    _expire_rent_payment_intents()
    intent = get_object_or_404(RentPaymentIntent, id=intent_id)
    back_week_iso = timezone.localtime(intent.slot_start).date().isoformat()

    if intent.status == RentPaymentIntent.Status.PAID:
        messages.success(request, "Платёж подтверждён. Бронь аренды создана.")
        return redirect(f"{reverse('core:rent')}?week={back_week_iso}")

    return render(request, "core/rent_pay_fail.html", {
        "intent": intent,
        "back_week_iso": back_week_iso,
    })


def call(request):
    meta = _legal_meta()
    phone = _required_or_placeholder(meta["operator_phone"])
    tel = _phone_to_tel(meta["operator_phone"])
    return render(request, "core/static_page.html", {
        "title": "Позвонить в клуб",
        "subtitle": "Быстрый способ позвонить на ресепшн нам в клуб",
        "lines": [f"Телефон: {phone}"],
        "button": {"label": "Позвонить", "href": f"tel:{tel}"} if tel else None,
    })


def privacy(request):
    meta = _legal_meta()
    studio_addresses = meta["studio_addresses"] or ["НЕ ЗАПОЛНЕНО"]

    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Политика конфиденциальности",
            "subtitle": "Порядок обработки и защиты персональных данных",
            "sections": [
                {
                    "title": "1. Общие положения",
                    "lines": [
                        "Настоящая Политика конфиденциальности определяет порядок обработки и защиты персональных данных клиентов и посетителей сайта студии «WOOM FIT».",
                        f"Администратор персональных данных: {_required_or_placeholder(meta['operator_name'])}, ОГРНИП {_required_or_placeholder(meta['operator_ogrn'])}, ИНН {_required_or_placeholder(meta['operator_inn'])}.",
                        "Адреса студий:",
                        *[f"• {addr}" for addr in studio_addresses],
                        "Политика разработана в соответствии с Федеральным законом РФ № 152-ФЗ «О персональных данных».",
                        "Использование сайта, регистрация и оплата услуг означает согласие пользователя с условиями Политики.",
                    ],
                },
                {
                    "title": "2. Сбор персональных данных",
                    "lines": [
                        "Под персональными данными понимаются сведения, позволяющие идентифицировать физическое лицо.",
                        "• ФИО",
                        "• дата рождения",
                        "• контактные данные (телефон, email)",
                        "• платежные данные (при онлайн-оплате)",
                        "• информация о посещениях и абонементах",
                        "Сайт также может собирать технические данные:",
                        "• IP-адрес, тип устройства, браузер",
                        "• действия на сайте и посещаемые страницы",
                        "• информация с cookie и аналогичных технологий",
                    ],
                },
                {
                    "title": "3. Цели обработки персональных данных",
                    "lines": [
                        "• предоставление услуг студии (запись, расписание, абонементы, оплата и возвраты)",
                        "• улучшение качества обслуживания и взаимодействия с клиентами",
                        "• обеспечение безопасности пользователей и предотвращение мошенничества",
                        "• выполнение требований законодательства РФ",
                        "• аналитические и маркетинговые цели при согласии пользователя",
                    ],
                },
                {
                    "title": "4. Обработка персональных данных",
                    "lines": [
                        "Обработка осуществляется законно, справедливо и прозрачно.",
                        "Сбор данных ограничен минимально необходимым для предоставления услуг.",
                        "Передача третьим лицам допускается только в необходимых случаях:",
                        "• банкам для проведения платежей",
                        "• органам власти по закону",
                        "• техническим сервисам для функционирования сайта (например, хостинг)",
                        "Доступ к персональным данным имеют только уполномоченные сотрудники Администратора.",
                        "Видеонаблюдение в помещениях студий ведется в целях безопасности и хранится ограниченный срок.",
                    ],
                },
                {
                    "title": "5. Сроки хранения данных",
                    "lines": [
                        "Персональные данные хранятся не дольше, чем это необходимо для целей обработки, но не менее 3 лет после окончания действия абонемента.",
                        "Видеозаписи хранятся до 30 дней, если не требуется для расследования инцидентов.",
                        "После истечения сроков данные удаляются или обезличиваются.",
                    ],
                },
                {
                    "title": "6. Права пользователя",
                    "lines": [
                        "Пользователь имеет право:",
                        "• получать информацию о своих персональных данных",
                        "• требовать исправления, удаления или ограничения обработки",
                        "• отзывать согласие на обработку данных в любой момент",
                        "• требовать удаления учетной записи на сайте",
                        f"Запросы направляются на email: {_required_or_placeholder(meta['operator_email'])}.",
                        "Администратор отвечает на запрос в срок не более 30 календарных дней.",
                    ],
                },
                {
                    "title": "7. Cookie и технологии отслеживания",
                    "lines": [
                        "Сайт использует cookie для авторизации, управления личным кабинетом, анализа работы сайта и маркетинговых целей при согласии пользователя.",
                        "Пользователь может отключить cookie в настройках браузера, но функционал сайта может быть ограничен.",
                        "Настройки cookie можно изменить через интерфейс сайта.",
                    ],
                },
                {
                    "title": "8. Безопасность персональных данных",
                    "lines": [
                        "Применяются организационные и технические меры для защиты данных от утраты, несанкционированного доступа и распространения.",
                        "Используются защищенные каналы передачи данных (SSL/TLS) для оплаты и передачи персональных данных.",
                    ],
                },
                {
                    "title": "9. Передача данных третьим лицам",
                    "lines": [
                        "Персональные данные могут передаваться третьим лицам только в случаях:",
                        "• выполнение условий договора (банки, платежные системы)",
                        "• требования законодательства РФ",
                        "• при согласии пользователя",
                        "Передача осуществляется на основании договоров с обязательствами по защите данных.",
                    ],
                },
                {
                    "title": "10. Изменение политики конфиденциальности",
                    "lines": [
                        "Администратор оставляет за собой право изменять Политику.",
                        "Новая версия публикуется на сайте с указанием даты обновления.",
                        "Использование сайта после изменений означает согласие с новой версией Политики.",
                    ],
                },
                {
                    "title": "11. Контакты",
                    "lines": [
                        "Для вопросов по обработке персональных данных:",
                        f"Email: {_required_or_placeholder(meta['operator_email'])}",
                        f"Телефон: {_required_or_placeholder(meta['operator_phone'])}",
                        "Адреса студий:",
                        *[f"• {addr}" for addr in studio_addresses],
                    ],
                },
            ],
        },
    )


def cookies_policy(request):
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Политика Cookie",
            "subtitle": "Правила использования файлов cookie на сайте",
            "sections": [
                {
                    "title": "1. Общие положения",
                    "lines": [
                        "Настоящая Политика Cookie описывает правила использования файлов cookie на сайте.",
                        "Пользуясь сайтом, вы соглашаетесь на использование cookie в соответствии с данной Политикой.",
                    ],
                },
                {
                    "title": "2. Что такое cookie",
                    "lines": [
                        "Cookie — это небольшие текстовые файлы, которые сохраняются на устройстве пользователя при посещении сайта.",
                        "Cookie помогают обеспечивать корректную работу сайта, сохранять настройки пользователя и анализировать посещаемость.",
                    ],
                },
                {
                    "title": "3. Типы используемых cookie",
                    "lines": [
                        "Необходимые cookie: обеспечивают работу сайта, авторизацию и доступ к функционалу (например, онлайн-оплата, личный кабинет).",
                        "Статистические и аналитические cookie: используются для сбора анонимной информации о работе сайта и улучшения качества услуг.",
                        "Функциональные cookie: сохраняют предпочтения пользователя, язык интерфейса, оформление и настройки.",
                    ],
                },
                {
                    "title": "4. Согласие и управление cookie",
                    "lines": [
                        "При первом посещении сайта отображается уведомление о cookie с возможностью согласиться.",
                        "Вы можете отключить cookie через настройки браузера, однако это может ограничить функционал сайта.",
                    ],
                },
                {
                    "title": "5. Передача данных третьим лицам",
                    "lines": [
                        "Cookie могут использоваться сторонними сервисами (например, платёжными системами и аналитикой).",
                        "Данные передаются в обезличенном виде и не позволяют идентифицировать пользователя без дополнительной информации.",
                    ],
                },
                {
                    "title": "6. Изменения в политике",
                    "lines": [
                        "Сайт вправе изменять данную Политику Cookie.",
                        "Все изменения вступают в силу с момента публикации на сайте.",
                    ],
                },
            ],
        },
    )


def cookie_settings(request):
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Настройки Cookie",
            "subtitle": "Как управлять cookie и их категориями",
            "sections": [
                {
                    "title": "1. Общие положения",
                    "lines": [
                        "На сайте используются cookie для корректной работы, аналитики и улучшения качества услуг.",
                        "Настройки cookie позволяют пользователю управлять тем, какие файлы сохраняются на его устройстве.",
                    ],
                },
                {
                    "title": "2. Как управлять cookie",
                    "lines": [
                        "Браузер: вы можете изменить настройки браузера, чтобы блокировать или удалять cookie.",
                        "Учтите, что это может ограничить функционал сайта.",
                        "Функциональные cookie: сохраняют предпочтения пользователя, язык интерфейса и оформление.",
                        "Отключение функциональных cookie может повлиять на удобство использования сайта.",
                        "Статистические / аналитические cookie: позволяют анализировать посещаемость и улучшать работу сайта.",
                        "Отказаться от статистических cookie можно через настройки браузера или специальные расширения.",
                        "Необходимые cookie: обеспечивают работу сайта и онлайн-оплаты.",
                        "Отключение необходимых cookie может сделать сайт частично или полностью недоступным.",
                    ],
                },
                {
                    "title": "3. Согласие на cookie",
                    "lines": [
                        "При первом посещении сайта пользователь получает уведомление о cookie и подтверждает согласие.",
                        "Пользователь может в любой момент изменить настройки cookie в браузере.",
                    ],
                },
                {
                    "title": "4. Изменения и обновления",
                    "lines": [
                        "Сайт вправе изменять Настройки Cookie.",
                        "Все изменения вступают в силу с момента публикации на сайте.",
                    ],
                },
            ],
        },
    )


def cookie_consent(request):
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Согласие на Cookie",
            "subtitle": "Условия согласия пользователя на использование cookie",
            "sections": [
                {
                    "title": "1. Согласие",
                    "lines": [
                        "Используя сайт и его сервисы, пользователь дает согласие на использование файлов cookie.",
                        "Необходимые cookie обеспечивают корректное отображение страниц и работу онлайн-оплаты.",
                        "Отключение необходимых cookie может сделать сайт частично или полностью недоступным.",
                    ],
                },
                {
                    "title": "2. Категории cookie",
                    "lines": [
                        "Функциональные cookie сохраняют настройки интерфейса, язык, оформление и предпочтения пользователя.",
                        "Отключение функциональных cookie может снизить удобство использования сайта.",
                        "Статистические и аналитические cookie используются для сбора анонимной информации о посещаемости и улучшения качества услуг.",
                        "Данные передаются в обезличенном виде и не позволяют идентифицировать пользователя без дополнительной информации.",
                    ],
                },
                {
                    "title": "3. Управление cookie",
                    "lines": [
                        "Пользователь может изменить настройки cookie в браузере в любой момент.",
                        "Сайт уведомляет о том, что отключение некоторых cookie может ограничить функционал.",
                    ],
                },
                {
                    "title": "4. Изменения",
                    "lines": [
                        "Настоящее согласие действует до момента его отзыва.",
                        "Сайт вправе обновлять условия использования cookie; изменения вступают в силу с момента публикации.",
                    ],
                },
            ],
        },
    )


def public_offer(request):
    meta = _legal_meta()
    studio_addresses = meta["studio_addresses"] or ["НЕ ЗАПОЛНЕНО"]
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Публичная оферта",
            "subtitle": "О заключении договора оказания физкультурно-оздоровительных услуг",
            "sections": [
                {
                    "title": "1. Общие положения",
                    "lines": [
                        f"Настоящая публичная оферта является официальным предложением {_required_or_placeholder(meta['operator_name'])}, ОГРНИП {_required_or_placeholder(meta['operator_ogrn'])}, ИНН {_required_or_placeholder(meta['operator_inn'])}, заключить договор оказания физкультурно-оздоровительных услуг.",
                        "Коммерческое обозначение студии — «WOOM FIT».",
                        "Услуги оказываются по адресам:",
                        *[f"• {addr}" for addr in studio_addresses],
                        "Договор регулируется законодательством Российской Федерации.",
                        "Оферта действует с момента размещения на сайте и до её отзыва Исполнителем.",
                        "Акцептом Оферты считается оплата услуги через сайт или иным способом, предложенным Исполнителем.",
                        "С момента оплаты договор считается заключённым.",
                        "Акцептуя Оферту, Клиент подтверждает согласие на обработку персональных данных в соответствии с Политикой конфиденциальности.",
                        "Актуальная стоимость услуг размещается на сайте Исполнителя и может быть изменена до момента оплаты.",
                    ],
                },
                {
                    "title": "2. Предмет договора",
                    "lines": [
                        "Исполнитель оказывает физкультурно-оздоровительные услуги (групповые и индивидуальные тренировки).",
                        "Услуги не являются медицинскими, не направлены на диагностику и лечение заболеваний и не требуют медицинской лицензии.",
                        "Клиент приобретает разовое занятие либо абонемент.",
                        "Услуга считается начатой с момента первого посещения по абонементу.",
                    ],
                },
                {
                    "title": "3. Активация и сроки действия абонементов",
                    "lines": [
                        "Активация абонемента происходит в день первого посещения либо автоматически через 14 календарных дней с даты покупки, если посещение не состоялось.",
                        "Сроки действия абонементов:",
                        "• 4, 8, 12 занятий — 1 месяц",
                        "• 16, 24 занятия — 2 месяца",
                        "• безлимит — 6 месяцев",
                        "• акционный безлимит — 100 календарных дней",
                        "Неиспользованные занятия по окончании срока действия абонемента аннулируются.",
                    ],
                },
                {
                    "title": "4. Заморозка абонемента",
                    "lines": [
                        "Клиент вправе воспользоваться заморозкой абонемента один раз в течение срока его действия на период от 1 до 14 календарных дней.",
                        "Заморозка осуществляется Клиентом самостоятельно через личный кабинет на сайте до даты начала периода заморозки.",
                        "Срок действия абонемента продлевается на количество календарных дней заморозки.",
                        "По истечении периода заморозки абонемент автоматически возобновляет действие.",
                        "Повторная заморозка в рамках одного абонемента не допускается.",
                        "Личные обстоятельства Клиента, включая болезнь, не являются основанием для дополнительного продления срока сверх предусмотренной заморозки.",
                    ],
                },
                {
                    "title": "5. Запись, отмена и расписание",
                    "lines": [
                        "Запись на занятия осуществляется через систему записи Исполнителя.",
                        "Клиент вправе отменить запись не позднее чем за 2 часа до начала занятия.",
                        "При отмене менее чем за 2 часа услуга считается оказанной и подлежит списанию.",
                        "Исполнитель вправе изменять расписание занятий, заменять тренера либо переносить занятия с предварительным уведомлением Клиентов.",
                        "Исполнитель вправе отказать в допуске к занятию при опоздании более 10 минут, признаках опьянения, нарушении техники безопасности или создании угрозы другим участникам.",
                        "В указанных случаях услуга считается оказанной.",
                    ],
                },
                {
                    "title": "6. Передача абонемента",
                    "lines": [
                        "Абонемент может быть передан другому лицу.",
                        "Для передачи Клиент обязан уведомить администратора студии до посещения занятия новым лицом.",
                        "С момента уведомления новый получатель принимает на себя все условия настоящей Оферты.",
                    ],
                },
                {
                    "title": "7. Стоимость и порядок оплаты",
                    "lines": [
                        "Оплата услуг осуществляется на условиях 100% предоплаты.",
                        "Датой оплаты считается момент зачисления денежных средств на расчётный счёт Исполнителя.",
                    ],
                },
                {
                    "title": "8. Возврат денежных средств",
                    "lines": [
                        "Клиент вправе отказаться от исполнения договора в любое время.",
                        "При возврате стоимость использованных занятий рассчитывается по цене разового занятия, действующей на дату приобретения абонемента.",
                        f"Возврат осуществляется тем же способом оплаты в течение 10 рабочих дней с момента получения письменного заявления на электронную почту: {_required_or_placeholder(meta['operator_email'])}.",
                    ],
                },
                {
                    "title": "9. Обязанности Клиента",
                    "lines": [
                        "Клиент обязан самостоятельно оценивать соответствие физической нагрузки состоянию своего здоровья и сообщать о противопоказаниях.",
                        "Клиент обязан соблюдать технику безопасности, рекомендации тренера, правила внутреннего распорядка и бережно относиться к имуществу студии.",
                        "Несовершеннолетние допускаются к занятиям только при наличии письменного согласия законного представителя.",
                    ],
                },
                {
                    "title": "10. Ответственность",
                    "lines": [
                        "Исполнитель не несёт ответственности за вред, причинённый вследствие сокрытия информации о состоянии здоровья, нарушения рекомендаций тренера и несоблюдения техники безопасности.",
                        "Клиент самостоятельно принимает решение об участии в занятиях и несёт риск неблагоприятных последствий при несоответствии состояния здоровья нагрузке.",
                        "Исполнитель не несёт ответственности за сохранность личных вещей Клиента.",
                    ],
                },
                {
                    "title": "11. Видеонаблюдение",
                    "lines": [
                        "В помещениях студий ведётся видеонаблюдение в целях обеспечения безопасности.",
                        "Записи хранятся ограниченный срок и используются исключительно для обеспечения безопасности и защиты прав сторон.",
                        "Передача записей третьим лицам осуществляется только в случаях, предусмотренных законодательством Российской Федерации.",
                    ],
                },
                {
                    "title": "12. Форс-мажор",
                    "lines": [
                        "Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы (ЧС, эпидемии, запреты органов власти, перебои энергоснабжения и иные обстоятельства, не зависящие от сторон).",
                        "На период действия таких обстоятельств сроки исполнения обязательств переносятся соразмерно времени их действия.",
                    ],
                },
                {
                    "title": "13. Порядок разрешения споров",
                    "lines": [
                        f"Претензии направляются в письменной форме на электронную почту: {_required_or_placeholder(meta['operator_email'])}.",
                        "Срок рассмотрения претензии — 30 календарных дней.",
                        "Споры разрешаются в порядке, установленном законодательством Российской Федерации.",
                    ],
                },
                {
                    "title": "14. Реквизиты",
                    "lines": [
                        *_requisites_lines(meta),
                    ],
                },
            ],
        },
    )


def refund_policy(request):
    meta = _legal_meta()
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Оплата и возврат",
            "subtitle": "Порядок оплаты, абонементов, заморозки и возвратов",
            "sections": [
                {
                    "title": "1. Способы оплаты",
                    "lines": [
                        "Оплата услуг осуществляется:",
                        "• онлайн на сайте через платёжную систему",
                        "• по ссылке, отправленной клиенту для оплаты",
                        "• наличными в студии при записи на занятие",
                    ],
                },
                {
                    "title": "2. Типы занятий и абонементов",
                    "lines": [
                        "Оплата возможна за разовые занятия и абонементы.",
                        "Условия, состав и сроки действия абонементов указываются на сайте и могут изменяться.",
                        "Абонемент начинает действовать с момента первого посещения или автоматически через время, указанное при покупке.",
                        "Все изменения в условиях абонементов вступают в силу с момента публикации на сайте.",
                    ],
                },
                {
                    "title": "3. Заморозка абонемента",
                    "lines": [
                        "Заморозка возможна один раз за один абонемент.",
                        "Минимальный срок заморозки — 1 день, максимальный — 14 дней.",
                        "Заморозка продлевает срок действия абонемента на количество дней заморозки.",
                        "Заморозку абонемента клиент может оформить самостоятельно через сайт, заявление не требуется.",
                    ],
                },
                {
                    "title": "4. Правила возврата",
                    "lines": [
                        "Разовые занятия не подлежат возврату после оплаты, если занятие было посещено.",
                        f"Возврат по абонементам возможен только за неиспользованные занятия и только по письменному обращению на email: {_required_or_placeholder(meta['operator_email'])}.",
                        "Возврат средств производится в течение 10 рабочих дней с момента подтверждения запроса.",
                        "При частичной заморозке возврат производится с учётом дней, на которые абонемент был заморожен.",
                    ],
                },
                {
                    "title": "5. Ограничения и условия",
                    "lines": [
                        "Минимальное время до занятия для отметки в системе: не менее 2 часов.",
                        "Сроки заморозки и ограничения использования абонементов учитываются при расчёте возврата.",
                    ],
                },
                {
                    "title": "6. Дополнительная информация",
                    "lines": [
                        "Все цены указаны на сайте и могут быть изменены с уведомлением клиентов.",
                        f"В случае технических проблем с оплатой необходимо обратиться на email: {_required_or_placeholder(meta['operator_email'])}.",
                    ],
                },
            ],
        },
    )


def personal_data_consent(request):
    meta = _legal_meta()
    studio_addresses = meta["studio_addresses"] or ["НЕ ЗАПОЛНЕНО"]
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Согласие на обработку персональных данных",
            "subtitle": "Согласие на условиях Федерального закона № 152-ФЗ",
            "sections": [
                {
                    "title": "Преамбула",
                    "lines": [
                        "Я, предоставляя свои персональные данные на сайте и/или при оформлении услуг, свободно, своей волей и в своём интересе, даю конкретное, предметное, информированное и сознательное согласие на обработку персональных данных.",
                        f"Оператор: {_required_or_placeholder(meta['operator_name'])}.",
                        f"ОГРНИП: {_required_or_placeholder(meta['operator_ogrn'])}.",
                        f"ИНН: {_required_or_placeholder(meta['operator_inn'])}.",
                        f"Адрес регистрации: {_required_or_placeholder(meta['operator_address'])}.",
                        "Адреса оказания услуг:",
                        *[f"• {addr}" for addr in studio_addresses],
                        f"Email Оператора: {_required_or_placeholder(meta['operator_email'])}.",
                    ],
                },
                {
                    "title": "1. Правовые основания обработки",
                    "lines": [
                        "Обработка персональных данных осуществляется:",
                        "• на основании настоящего согласия",
                        "• для исполнения договора оказания физкультурно-оздоровительных услуг",
                        "• для соблюдения требований законодательства Российской Федерации",
                    ],
                },
                {
                    "title": "2. Цели обработки персональных данных",
                    "lines": [
                        "Персональные данные обрабатываются в целях:",
                        "• регистрации на сайте и создания личного кабинета",
                        "• оформления, оплаты и предоставления услуг",
                        "• ведения абонементов и учёта посещаемости",
                        "• связи с клиентом (уведомления, подтверждение записи, изменения расписания)",
                        "• обработки платежей и возвратов",
                        "• ведения бухгалтерского и налогового учёта",
                        "• обеспечения безопасности, предотвращения противоправных действий",
                        "• улучшения качества услуг, статистики и аналитики",
                    ],
                },
                {
                    "title": "3. Перечень персональных данных",
                    "lines": [
                        "Согласие распространяется на следующие персональные данные:",
                        "• фамилия, имя, отчество",
                        "• номер телефона",
                        "• адрес электронной почты",
                        "• сведения о приобретённых услугах и посещениях",
                        "• платёжная информация в объёме, необходимом для оплаты (реквизиты банковских карт Оператором не хранятся при использовании платёжных агрегаторов)",
                        "• технические данные: IP-адрес, данные файлов cookie, сведения о браузере и устройстве",
                        "Оператор не осуществляет обработку специальных категорий персональных данных и биометрических персональных данных.",
                    ],
                },
                {
                    "title": "4. Действия с персональными данными",
                    "lines": [
                        "Оператор вправе осуществлять сбор, запись, систематизацию, накопление, хранение, уточнение, использование, извлечение, передачу, обезличивание, блокирование, удаление и уничтожение персональных данных.",
                        "Обработка осуществляется как с использованием средств автоматизации, так и без их использования.",
                    ],
                },
                {
                    "title": "5. Передача третьим лицам",
                    "lines": [
                        "Персональные данные могут передаваться третьим лицам исключительно для достижения целей обработки.",
                        "• банкам и платёжным системам",
                        "• организациям, обеспечивающим техническое обслуживание сайта",
                        "• сервисам онлайн-записи и автоматизации",
                        "Передача осуществляется на основании договоров и обязательств по соблюдению конфиденциальности и требований законодательства РФ.",
                        "Трансграничная передача персональных данных может осуществляться при соблюдении требований законодательства РФ.",
                    ],
                },
                {
                    "title": "6. Срок обработки и хранения",
                    "lines": [
                        "Персональные данные обрабатываются в течение срока действия договора оказания услуг.",
                        "Данные могут храниться в течение сроков, установленных законодательством РФ для бухгалтерского и налогового учёта (не менее 5 лет), если применимо.",
                        "Либо до момента отзыва согласия субъектом персональных данных.",
                    ],
                },
                {
                    "title": "7. Права субъекта персональных данных",
                    "lines": [
                        "Субъект персональных данных вправе:",
                        "• получать информацию, касающуюся обработки его персональных данных",
                        "• требовать уточнения, блокирования или уничтожения персональных данных",
                        "• отозвать согласие на обработку",
                        "• обжаловать действия или бездействие Оператора в уполномоченный орган по защите прав субъектов персональных данных",
                    ],
                },
                {
                    "title": "8. Отзыв согласия",
                    "lines": [
                        f"Согласие может быть отозвано путём направления письменного уведомления на электронную почту: {_required_or_placeholder(meta['operator_email'])}.",
                        "Оператор прекращает обработку персональных данных в течение 30 календарных дней с момента получения отзыва, за исключением случаев, когда обработка обязательна в силу закона.",
                    ],
                },
                {
                    "title": "9. Форма выражения согласия",
                    "lines": [
                        "Согласие считается предоставленным при проставлении отметки (чекбокса) на сайте при регистрации, оформлении записи или оплате услуг, либо при подписании соответствующего документа на бумажном носителе.",
                    ],
                },
            ],
        },
    )


def requisites(request):
    meta = _legal_meta()
    studio_addresses = meta["studio_addresses"] or ["НЕ ЗАПОЛНЕНО"]
    return render(
        request,
        "core/legal_page.html",
        {
            "title": "Реквизиты продавца",
            "subtitle": "Сведения об операторе, банке и адресах оказания услуг",
            "sections": [
                {
                    "title": "Оператор",
                    "lines": [
                        f"Оператор: {_required_or_placeholder(meta['operator_name'])}",
                        f"ИНН: {_required_or_placeholder(meta['operator_inn'])}",
                        f"ОГРНИП: {_required_or_placeholder(meta['operator_ogrn'])}",
                        f"Адрес регистрации: {_required_or_placeholder(meta['operator_address'])}",
                        f"Email: {_required_or_placeholder(meta['operator_email'])}",
                        f"Телефон: {_required_or_placeholder(meta['operator_phone'])}",
                    ],
                },
                {
                    "title": "Банковские реквизиты",
                    "lines": [
                        f"Р/с: {_required_or_placeholder(meta['bank_account'])}",
                        f"Банк: {_required_or_placeholder(meta['bank_name'])}",
                        f"БИК: {_required_or_placeholder(meta['bank_bik'])}",
                        f"Корр. счёт: {_required_or_placeholder(meta['bank_corr_account'])}",
                        f"Юридический адрес банка: {_required_or_placeholder(meta['bank_address'])}",
                    ],
                },
                {
                    "title": "Адреса студий",
                    "lines": [f"• {addr}" for addr in studio_addresses],
                },
            ],
        },
    )
