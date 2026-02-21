from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import date

from core.legal import client_ip
from memberships.models import Membership
from orders.models import Order
from schedule.models import Booking, PaymentIntent
from wallet.models import WalletTx
from .forms import (
    ProfileForm,
    ProfileNameForm,
    SignUpForm,
)


def _membership_sort_key(m):
    # Сначала абонементы с ближайшим окончанием, бессрочные/неактивированные — в конце.
    return (
        1 if m.end_date is None else 0,
        m.end_date or date.max,
        m.created_at,
    )


def _get_unspent_memberships(user):
    today = timezone.localdate()
    rows = (
        Membership.objects
        .filter(user=user, is_active=True)
        .order_by("created_at")
    )
    result = []
    for m in rows:
        # Просроченные не показываем.
        if m.end_date and m.end_date < today:
            continue
        # Для абонементов по посещениям нужно > 0 оставшихся.
        if m.kind == Membership.Kind.VISITS and m.left_visits is not None and m.left_visits <= 0:
            continue
        result.append(m)
    result.sort(key=_membership_sort_key)
    return result


def _build_profile_journal(user):
    events = []

    wallet_txs = (
        WalletTx.objects
        .filter(wallet__user=user)
        .order_by("-created_at")[:150]
    )
    for tx in wallet_txs:
        if tx.kind == WalletTx.Kind.TOPUP:
            title = "Пополнение кошелька"
            amount = f"+{tx.amount} ₽"
            amount_class = "plus"
        elif tx.kind == WalletTx.Kind.REFUND:
            title = "Возврат в кошелёк"
            amount = f"+{tx.amount} ₽"
            amount_class = "plus"
        elif tx.kind == WalletTx.Kind.DEBIT:
            title = "Списание с кошелька"
            amount = f"-{tx.amount} ₽"
            amount_class = "minus"
        else:
            title = "Корректировка кошелька"
            amount = f"{tx.amount} ₽"
            amount_class = "neutral"

        events.append(
            {
                "at": tx.created_at,
                "title": title,
                "subtitle": tx.reason or "Без комментария",
                "amount": amount,
                "amount_class": amount_class,
            }
        )

    memberships = (
        Membership.objects
        .filter(user=user)
        .order_by("-created_at")[:100]
    )
    for m in memberships:
        events.append(
            {
                "at": m.created_at,
                "title": f"Оформлен абонемент «{m.title}»",
                "subtitle": f"{m.get_kind_display()} • {m.get_scope_display() if m.scope else 'Все тренировки'}",
                "amount": "",
                "amount_class": "neutral",
            }
        )

    orders = (
        Order.objects
        .filter(user=user)
        .order_by("-created_at")[:120]
    )
    for order in orders:
        events.append(
            {
                "at": order.created_at,
                "title": f"Заказ #{order.id}",
                "subtitle": f"{order.get_status_display()} • {order.total_rub} ₽",
                "amount": "",
                "amount_class": "neutral",
            }
        )

    intents = (
        PaymentIntent.objects
        .filter(user=user)
        .select_related("session")
        .order_by("-created_at")[:120]
    )
    for intent in intents:
        at = intent.paid_at or intent.created_at
        events.append(
            {
                "at": at,
                "title": f"Оплата занятия «{intent.session.title}»",
                "subtitle": f"{intent.get_status_display()} • {intent.amount_rub} ₽",
                "amount": "",
                "amount_class": "neutral",
            }
        )

    bookings = (
        Booking.objects
        .filter(user=user)
        .select_related("session")
        .order_by("-created_at")[:150]
    )
    for b in bookings:
        events.append(
            {
                "at": b.created_at,
                "title": f"Запись на занятие «{b.session.title}»",
                "subtitle": timezone.localtime(b.session.start_at).strftime("%d.%m.%Y %H:%M"),
                "amount": "",
                "amount_class": "neutral",
            }
        )
        if b.canceled_at:
            events.append(
                {
                    "at": b.canceled_at,
                    "title": f"Отмена записи «{b.session.title}»",
                    "subtitle": timezone.localtime(b.session.start_at).strftime("%d.%m.%Y %H:%M"),
                    "amount": "",
                    "amount_class": "neutral",
                }
            )
        if b.marked_at:
            if b.attendance_status == Booking.Attendance.ATTENDED:
                label = "Посещение отмечено"
            elif b.attendance_status == Booking.Attendance.MISSED:
                label = "Пропуск отмечен"
            else:
                label = "Обновлён статус посещения"
            events.append(
                {
                    "at": b.marked_at,
                    "title": f"{label}: «{b.session.title}»",
                    "subtitle": timezone.localtime(b.session.start_at).strftime("%d.%m.%Y %H:%M"),
                    "amount": "",
                    "amount_class": "neutral",
                }
            )

    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:250]


@login_required
def profile(request):
    memberships = _get_unspent_memberships(request.user)
    journal_events = _build_profile_journal(request.user)
    return render(
        request,
        "accounts/profile.html",
        {
            "memberships": memberships,
            "journal_events": journal_events,
            "today": timezone.localdate(),
        },
    )


@login_required
def settings(request):
    name_form = ProfileNameForm(user=request.user)
    password_form = PasswordChangeForm(user=request.user)
    profile_form = ProfileForm(instance=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "name":
            name_form = ProfileNameForm(request.POST, user=request.user)
            if name_form.is_valid():
                name_form.save()
                messages.success(request, "Имя обновлено")
                return redirect("accounts:settings")

        elif action == "password":
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Пароль обновлён")
                return redirect("accounts:settings")

        elif action == "personal":
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Личные данные сохранены")
                return redirect("accounts:settings")

        elif action == "logout":
            logout(request)
            return redirect("login")

        else:
            messages.error(request, "Неизвестное действие")

    return render(
        request,
        "accounts/settings.html",
        {"name_form": name_form, "password_form": password_form, "profile_form": profile_form},
    )


@login_required
def personal_data(request):
    return redirect("accounts:settings")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            consent_at = timezone.now()
            ip = client_ip(request)
            user.personal_data_consent_at = consent_at
            user.personal_data_consent_ip = ip
            user.offer_consent_at = consent_at
            user.offer_consent_ip = ip
            user.save()
            login(request, user, backend="accounts.backends.UsernameOrPhoneBackend")
            return redirect("core:home")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})
