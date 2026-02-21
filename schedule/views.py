from datetime import date, datetime, timedelta
import re
from django.urls import reverse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from core.telegram_notify import notify_booking_canceled, notify_booking_created
from core.legal import client_ip, is_checked
from payments.receipt import build_receipt, receipt_item

from .models import Session, Booking, PaymentIntent


def _detail_url(session_id: int, notice: str | None = None) -> str:
    url = reverse("schedule:detail", args=[session_id])
    if notice:
        return f"{url}?notice={notice}"
    return url


def _create_single_visit_membership(user):
    """Создаёт абонемент на 1 групповое посещение ("разовое")."""
    from memberships.models import Membership

    m = Membership.objects.create(
        user=user,
        title="Разовое посещение",
        kind=Membership.Kind.VISITS,
        scope=Membership.Scope.GROUP,
        total_visits=1,
        left_visits=1,
        is_active=True,
    )
    return m


def _set_booked(*, user, session: Session, membership=None):
    """Создаёт/обновляет Booking в BOOKED, привязывая абонемент (если указан)."""
    b, _ = Booking.objects.get_or_create(user=user, session=session)
    b.booking_status = Booking.Status.BOOKED
    b.canceled_at = None
    b.membership = membership
    b.invite_sent_at = None
    b.invite_expires_at = None
    b.save(update_fields=[
        "booking_status",
        "canceled_at",
        "membership",
        "invite_sent_at",
        "invite_expires_at",
    ])
    return b


def _invite_next_waiter(session: Session) -> None:
    """Если появилось место — приглашаем первого из листа ожидания на 1 час."""
    if getattr(session, "seats_left", 0) <= 0:
        return

    now = timezone.now()

    active_invited = session.bookings.filter(
        booking_status=Booking.Status.INVITED,
        invite_expires_at__gt=now,
    ).exists()
    if active_invited:
        return

    b = (
        session.bookings
        .select_related("user")
        .filter(booking_status=Booking.Status.WAITLIST)
        .order_by("created_at")
        .first()
    )
    if not b:
        return

    b.booking_status = Booking.Status.INVITED
    b.invite_sent_at = now
    b.invite_expires_at = now + timedelta(hours=1)
    b.save(update_fields=["booking_status", "invite_sent_at", "invite_expires_at"])
    # уведомления отключены


def _parse_iso_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _days_between(start: date, end: date):
    days = []
    cur = start
    while cur <= end:
        days.append({"date": cur})
        cur += timedelta(days=1)
    return days


def _norm_addr(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", s)


def _sessions_for_day_loc(*, selected: date, loc: str, user):
    tz = timezone.get_current_timezone()

    start_dt = datetime.combine(selected, datetime.min.time(), tzinfo=tz)
    end_dt = start_dt + timedelta(days=1)

    vis_q = Q(kind="group")

    base_qs = (
        Session.objects.select_related("trainer")
        .filter(vis_q)
        .filter(start_at__gte=start_dt, start_at__lt=end_dt)
        .exclude(location__isnull=True)
        .exclude(location__exact="")
        .order_by("start_at")
    )

    sessions_list = list(base_qs)
    if loc:
        target = _norm_addr(loc)
        sessions_list = [s for s in sessions_list if _norm_addr(s.location) == target]

    session_ids = [s.id for s in sessions_list]

    booked_ids = set()
    if getattr(user, "is_authenticated", False) and session_ids:
        booked_ids = set(
            Booking.objects.filter(
                user=user,
                session_id__in=session_ids,
                booking_status="booked",
            ).values_list("session_id", flat=True)
        )

    return sessions_list, booked_ids


def _membership_sort_key(m):
    # Сначала абонементы с ближайшим окончанием, бессрочные/неактивированные — в конце.
    return (
        1 if m.end_date is None else 0,
        m.end_date or date.max,
        m.created_at,
    )


def _group_memberships_for_payment(user):
    from memberships.models import Membership

    qs = (
        Membership.objects
        .filter(user=user, is_active=True)
        .filter(Q(scope="") | Q(scope=Membership.Scope.GROUP))
        .order_by("created_at")
    )
    memberships = [m for m in qs if m.can_book_group()]
    memberships.sort(key=_membership_sort_key)
    return memberships


def schedule_list(request):
    today = timezone.localdate()
    selected = _parse_iso_date(request.GET.get("day") or "") or today
    if selected < today:
        selected = today

    loc = (request.GET.get("loc") or "").strip()
    locations = [x for x in getattr(__import__("django.conf").conf.settings, "WOOMFIT_LOCATIONS", []) if x]
    if not loc and locations:
        loc = locations[0]

    STRIP_N = 10
    start_day = today
    end_day = start_day + timedelta(days=STRIP_N - 1)
    days = _days_between(start_day, end_day)

    sessions_list, booked_ids = _sessions_for_day_loc(selected=selected, loc=loc, user=request.user)

    return render(
        request,
        "schedule/list.html",
        {
            "locations": locations,
            "selected_location": loc,
            "selected": selected,
            "days": days,
            "strip_start": start_day.isoformat(),
            "strip_end": end_day.isoformat(),
            "today_iso": today.isoformat(),
            "sessions": sessions_list,
            "booked_ids": booked_ids,
        },
    )


def schedule_fragment(request):
    today = timezone.localdate()
    selected = _parse_iso_date(request.GET.get("day") or "") or today
    if selected < today:
        selected = today
    loc = (request.GET.get("loc") or "").strip()

    sessions_list, booked_ids = _sessions_for_day_loc(selected=selected, loc=loc, user=request.user)

    return render(
        request,
        "schedule/_sessions.html",
        {
            "sessions": sessions_list,
            "booked_ids": booked_ids,
            "selected": selected,
            "selected_location": loc,
        },
    )


def session_detail(request, session_id: int):
    """Страница тренировки + bottom-sheet выбора оплаты."""
    s = get_object_or_404(Session.objects.select_related("trainer", "workout"), id=session_id)

    if getattr(s, "kind", "group") != "group":
        messages.error(request, "Эта тренировка недоступна в публичном расписании")
        return redirect("schedule:list")

    booking = None
    if request.user.is_authenticated:
        booking = Booking.objects.filter(user=request.user, session=s).first()

    # действия (лист ожидания/отмена ожидания/подтверждение приглашения)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        action = (request.POST.get("action") or "").strip()

        if action == "cancel_waitlist":
            if booking and booking.booking_status in (Booking.Status.WAITLIST, Booking.Status.INVITED):
                booking.booking_status = Booking.Status.CANCELED
                booking.canceled_at = timezone.now()
                booking.invite_sent_at = None
                booking.invite_expires_at = None
                booking.save(update_fields=[
                    "booking_status",
                    "canceled_at",
                    "invite_sent_at",
                    "invite_expires_at",
                ])
                messages.success(request, "Ожидание отменено")
            return redirect("schedule:detail", session_id=s.id)

        if action == "waitlist":
            if booking and booking.booking_status in (Booking.Status.WAITLIST, Booking.Status.INVITED):
                messages.success(request, "Вы уже в листе ожидания")
                return redirect("schedule:detail", session_id=s.id)
            if booking and booking.booking_status == Booking.Status.BOOKED:
                messages.success(request, "Вы уже записаны")
                return redirect("schedule:detail", session_id=s.id)

            b, _ = Booking.objects.get_or_create(user=request.user, session=s)
            b.booking_status = Booking.Status.WAITLIST
            b.canceled_at = None
            b.invite_sent_at = None
            b.invite_expires_at = None
            b.membership = None
            b.save(update_fields=[
                "booking_status",
                "canceled_at",
                "invite_sent_at",
                "invite_expires_at",
                "membership",
            ])
            messages.success(request, "Вы записаны в лист ожидания")
            return redirect("schedule:detail", session_id=s.id)

        # NOTE: кнопка "Записаться" теперь НЕ POST’ит сюда — она открывает bottom sheet
        return redirect("schedule:detail", session_id=s.id)

    seats_left = getattr(s, "seats_left", 0)
    is_full = seats_left <= 0

    state = "free"
    if booking:
        state = booking.booking_status

    memberships = []
    if request.user.is_authenticated and not is_full and state not in ("booked", "waitlist"):
        memberships = _group_memberships_for_payment(request.user)

    return render(
        request,
        "schedule/detail.html",
        {
            "s": s,
            "seats_left": seats_left,
            "is_full": is_full,
            "booking": booking,
            "state": state,
            "memberships": memberships,
        },
    )


@login_required
def session_choose_payment(request, session_id: int):
    """POST-обработчик: membership/pay. GET оставляем как fallback (страница)."""
    s = get_object_or_404(Session.objects.select_related("trainer"), id=session_id)

    if getattr(s, "kind", "group") != "group":
        messages.error(request, "Эта тренировка недоступна")
        return redirect("schedule:list")

    if getattr(s, "seats_left", 0) <= 0:
        messages.error(request, "Свободных мест нет")
        return redirect("schedule:detail", session_id=s.id)

    booking = Booking.objects.filter(user=request.user, session=s).first()
    if booking and booking.booking_status == Booking.Status.BOOKED:
        messages.success(request, "Вы уже записаны")
        return redirect("schedule:detail", session_id=s.id)

    from memberships.models import Membership

    if request.method == "POST":
        method = (request.POST.get("method") or "").strip()

        if method == "pay":
            return redirect("schedule:pay", session_id=s.id)

        if method == "membership":
            mid = (request.POST.get("membership_id") or "").strip()
            if not mid.isdigit():
                messages.error(request, "Выберите абонемент")
                return redirect("schedule:detail", session_id=s.id)

            m = get_object_or_404(
                Membership.objects.filter(user=request.user)
                .filter(Q(scope="") | Q(scope=Membership.Scope.GROUP)),
                id=int(mid),
            )
            if not m.can_book_group():
                messages.error(request, "Этот абонемент нельзя использовать для групповой тренировки")
                return redirect("schedule:detail", session_id=s.id)

            if not m.consume_visit():
                messages.error(request, "На этом абонементе закончились посещения")
                return redirect("schedule:detail", session_id=s.id)

            _set_booked(user=request.user, session=s, membership=m)
            notify_booking_created(
                user=request.user,
                session=s,
                source=f"Абонемент: {m.title}",
            )
            messages.success(request, "Вы записались")
            return redirect(_detail_url(s.id, notice="booked"))

        messages.error(request, "Выберите способ оплаты")
        return redirect("schedule:detail", session_id=s.id)

    # GET fallback
    memberships = _group_memberships_for_payment(request.user)

    return render(
        request,
        "schedule/choose_payment.html",
        {"s": s, "memberships": memberships},
    )


@login_required
@transaction.atomic
def session_pay(request, session_id: int):
    """Оплата разового занятия: кошелёк или онлайн."""
    s = get_object_or_404(Session, id=session_id)
    wants_json = request.method == "POST" and (request.POST.get("integrationjs") or "").strip() == "1"

    def _json_error(message: str, status: int = 400):
        return JsonResponse({"error": message}, status=status)

    if getattr(s, "kind", "group") != "group":
        if wants_json:
            return _json_error("Эта тренировка недоступна для оплаты")
        messages.error(request, "Эта тренировка недоступна для оплаты")
        return redirect("schedule:list")

    if getattr(s, "seats_left", 0) <= 0:
        if wants_json:
            return _json_error("Свободных мест нет")
        messages.error(request, "Свободных мест нет")
        return redirect("schedule:detail", session_id=s.id)

    from django.conf import settings
    amount_rub = int(getattr(settings, "WOOMFIT_DROPIN_GROUP_PRICE_RUB", 700) or 700)

    from wallet.models import Wallet
    from wallet.services import debit
    from decimal import Decimal

    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    wallet_balance = int(wallet.balance)

    if request.method == "POST":
        method = (request.POST.get("method") or "").strip()
        if method not in {"wallet", "online"}:
            if wants_json:
                return _json_error("Выберите способ оплаты")
            messages.error(request, "Выберите способ оплаты")
            return redirect("schedule:pay", session_id=s.id)

        offer_ok = is_checked(request, "agree_offer")
        pd_ok = is_checked(request, "agree_personal_data")
        if not offer_ok or not pd_ok:
            if wants_json:
                return _json_error(
                    "Для оплаты необходимо принять публичную оферту и согласие на обработку персональных данных."
                )
            messages.error(
                request,
                "Для оплаты необходимо принять публичную оферту и согласие на обработку персональных данных.",
            )
            return redirect("schedule:pay", session_id=s.id)

        if method == "wallet":
            if wallet.balance < Decimal(str(amount_rub)):
                if wants_json:
                    return _json_error("Недостаточно средств в кошельке")
                messages.error(request, "Недостаточно средств в кошельке")
                return redirect("schedule:pay", session_id=s.id)

            try:
                debit(
                    request.user,
                    Decimal(str(amount_rub)),
                    reason=f"Оплата разового занятия: {s.title} ({timezone.localtime(s.start_at).strftime('%d.%m %H:%M')})",
                )
            except ValidationError as e:
                if wants_json:
                    return _json_error(str(e) or "Не удалось списать средства из кошелька")
                messages.error(request, str(e) or "Не удалось списать средства из кошелька")
                return redirect("schedule:pay", session_id=s.id)

            intent = PaymentIntent.objects.create(
                user=request.user,
                session=s,
                amount_rub=amount_rub,
                status=PaymentIntent.Status.PAID,
                paid_at=timezone.now(),
                tb_status="WALLET_PAID",
                legal_accepted_at=timezone.now(),
                legal_accept_ip=client_ip(request),
            )

            # Loyalty should grow only once, at the moment of real payment.
            from loyalty.services import add_spent
            add_spent(request.user, Decimal(str(amount_rub)))

            # ✅ разовый абонемент на 1 и сразу списание
            m = _create_single_visit_membership(request.user)
            m.consume_visit()
            _set_booked(user=request.user, session=s, membership=m)
            notify_booking_created(
                user=request.user,
                session=s,
                source="Разовая оплата (кошелёк)",
            )

            messages.success(request, "Оплачено. Вы записаны")
            return redirect(_detail_url(s.id, notice="booked"))

        if method == "online":
            from payments.tbank import TBankClient

            intent = PaymentIntent.objects.create(
                user=request.user,
                session=s,
                amount_rub=amount_rub,
                status=PaymentIntent.Status.NEW,
                legal_accepted_at=timezone.now(),
                legal_accept_ip=client_ip(request),
            )

            client = TBankClient(settings.TBANK_TERMINAL_KEY, settings.TBANK_PASSWORD, settings.TBANK_IS_TEST)

            notification_url = request.build_absolute_uri(reverse("payments:tbank_webhook"))
            success_url = request.build_absolute_uri(reverse("schedule:pay_success", args=[intent.id]))
            fail_url = request.build_absolute_uri(reverse("schedule:pay_fail", args=[intent.id]))

            amount_kopeks = int(amount_rub) * 100
            receipt = build_receipt(
                request.user,
                [receipt_item(name=f"Разовое посещение: {s.title}", price_kopeks=amount_kopeks, quantity=1)],
            )

            pay = client.init_payment(
                order_id=f"S-{intent.id}",
                amount_kopeks=amount_kopeks,
                description=f"WOOM FIT session #{s.id} intent #{intent.id}",
                notification_url=notification_url,
                success_url=success_url,
                fail_url=fail_url,
                receipt=receipt,
                data={"connection_type": "Widget"} if wants_json else None,
            )

            if pay.get("Success"):
                intent.tb_payment_id = str(pay.get("PaymentId") or "")
                intent.tb_status = str(pay.get("Status") or "")
                intent.status = PaymentIntent.Status.PENDING
                intent.save(update_fields=["tb_payment_id", "tb_status", "status"])
                if wants_json:
                    payment_url = str(pay.get("PaymentURL") or "").strip()
                    if not payment_url:
                        return _json_error("Платёж создан без ссылки на оплату.", status=502)
                    return JsonResponse({"paymentUrl": payment_url, "paymentId": intent.tb_payment_id})
                return redirect(pay["PaymentURL"])

            intent.status = PaymentIntent.Status.CANCELED
            intent.tb_status = str(pay.get("Status") or "")
            intent.save(update_fields=["status", "tb_status"])
            if wants_json:
                return JsonResponse({"error": "Не удалось создать оплату в T-Bank.", "details": pay}, status=400)
            return render(request, "payments/fail.html", {"error": pay})

    return render(
        request,
        "schedule/pay.html",
        {
            "s": s,
            "amount_rub": amount_rub,
            "wallet_balance": wallet_balance,
            "tbank_terminal_key": getattr(settings, "TBANK_TERMINAL_KEY", ""),
        },
    )


@login_required
def session_pay_success(request, intent_id: int):
    intent = get_object_or_404(PaymentIntent, id=intent_id, user=request.user)
    if intent.status == PaymentIntent.Status.PAID:
        messages.success(request, "Оплачено. Вы записаны")
        return redirect(_detail_url(intent.session_id, notice="booked"))
    return render(request, "schedule/pay_success.html", {"intent": intent, "s": intent.session})


@login_required
def session_pay_fail(request, intent_id: int):
    intent = get_object_or_404(PaymentIntent, id=intent_id, user=request.user)
    return render(request, "schedule/pay_fail.html", {"intent": intent, "s": intent.session})


@login_required
@transaction.atomic
def unbook_session(request, session_id: int):
    booking = get_object_or_404(Booking, session_id=session_id, user=request.user)

    s = booking.session
    if getattr(s, "start_at", None) and (s.start_at - timezone.now()) < timedelta(hours=2):
        messages.error(request, "Отмена возможна не позднее чем за 2 часа до начала.")
        return redirect(request.META.get("HTTP_REFERER", reverse("schedule:list")))

    had_membership = bool(booking.membership_id)

    if booking.membership:
        booking.membership.refund_visit()

    booking.cancel()
    _invite_next_waiter(s)
    notify_booking_canceled(
        user=request.user,
        session=s,
        reason="Возврат посещения: да" if had_membership else "Возврат посещения: нет",
    )

    messages.success(request, "Запись отменена. Посещение вернулось на абонемент (если было).")
    return redirect(request.META.get("HTTP_REFERER", reverse("schedule:list")))
