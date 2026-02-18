import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape


logger = logging.getLogger(__name__)


def tg_send(text: str):
    if not getattr(settings, "TELEGRAM_NOTIFICATIONS", True):
        return

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        requests.post(url, json=payload, timeout=5)
    except requests.RequestException:
        logger.warning("Telegram message was not sent due to a request error")


def occupancy_line(current: int, capacity):
    """
    Возвращает строку вида: 👥 Участники: 3 / 10
    Если вместимость неизвестна — показывает только текущее.
    """
    if capacity in (None, "", 0):
        return f"👥 Участники: <b>{current}</b>"
    return f"👥 Участники: <b>{current} / {capacity}</b>"


def occupancy_note(current: int, capacity):
    """
    Примечание по остаткам: осталось 2 / 1 / 0 мест.
    """
    if capacity in (None, "", 0):
        return ""

    left = capacity - current
    if left <= 0:
        return "🚫 <b>Занятие заполнено</b>"
    if left == 1:
        return "⚠️ <b>Осталось 1 место</b>"
    if left == 2:
        return "⚠️ <b>Осталось 2 места</b>"
    return ""


def trainer_label(session):
    """
    Универсально пытается получить имя тренера из session.
    Подходит если trainer = FK на Trainer/User или строковое поле.
    """
    t = getattr(session, "trainer", None)
    if not t:
        # иногда поле может называться иначе
        t = getattr(session, "coach", None) or getattr(session, "instructor", None)

    if not t:
        return "—"

    # если это User
    if hasattr(t, "get_full_name"):
        name = (t.get_full_name() or getattr(t, "username", "") or str(t)).strip()
        return name or str(t)

    # если это модель Trainer с полем name
    name = getattr(t, "name", None)
    if name:
        return str(name).strip()

    return str(t).strip()


def _fmt_user(user) -> str:
    if not user:
        return "—"
    full_name = ""
    if hasattr(user, "get_full_name"):
        full_name = (user.get_full_name() or "").strip()
    return escape(full_name or str(user) or "—")


def _fmt_session_time(session) -> str:
    start_at = getattr(session, "start_at", None)
    if not start_at:
        return "—"
    return timezone.localtime(start_at).strftime("%d.%m.%Y %H:%M")


def _session_occupancy(session):
    try:
        current = session.bookings.filter(booking_status="booked").count()
        capacity = getattr(session, "capacity", None)
        return occupancy_line(current, capacity), occupancy_note(current, capacity)
    except Exception:
        return "", ""


def notify_booking_created(*, user, session, source: str = ""):
    title = escape(getattr(session, "title", "") or "Занятие")
    trainer = escape(trainer_label(session))
    location = escape(getattr(session, "location", "") or "—")
    source_line = f"\nИсточник: <b>{escape(source)}</b>" if source else ""
    occ_line, occ_note = _session_occupancy(session)
    occ_note_line = f"\n{occ_note}" if occ_note else ""
    tg_send(
        "✅ <b>Новая запись на занятие</b>\n"
        f"Клиент: <b>{_fmt_user(user)}</b>\n"
        f"Занятие: <b>{title}</b>\n"
        f"Когда: <b>{_fmt_session_time(session)}</b>\n"
        f"Тренер: <b>{trainer}</b>\n"
        f"Адрес: <b>{location}</b>\n"
        f"{occ_line}{occ_note_line}{source_line}"
    )


def notify_booking_canceled(*, user, session, reason: str = ""):
    title = escape(getattr(session, "title", "") or "Занятие")
    trainer = escape(trainer_label(session))
    location = escape(getattr(session, "location", "") or "—")
    reason_line = f"\nПричина: <b>{escape(reason)}</b>" if reason else ""
    occ_line, occ_note = _session_occupancy(session)
    occ_note_line = f"\n{occ_note}" if occ_note else ""
    tg_send(
        "❌ <b>Отмена записи на занятие</b>\n"
        f"Клиент: <b>{_fmt_user(user)}</b>\n"
        f"Занятие: <b>{title}</b>\n"
        f"Когда: <b>{_fmt_session_time(session)}</b>\n"
        f"Тренер: <b>{trainer}</b>\n"
        f"Адрес: <b>{location}</b>\n"
        f"{occ_line}{occ_note_line}{reason_line}"
    )


def notify_order_payment(*, user, order_id: int, amount_rub, method: str, purchase: str = ""):
    purchase_line = f"Покупка: <b>{escape(purchase)}</b>\n" if purchase else ""
    tg_send(
        "💳 <b>Оплата заказа</b>\n"
        f"Клиент: <b>{_fmt_user(user)}</b>\n"
        f"Заказ: <b>#{order_id}</b>\n"
        f"{purchase_line}"
        f"Сумма: <b>{escape(str(amount_rub))} ₽</b>\n"
        f"Метод: <b>{escape(method)}</b>"
    )


def notify_session_payment(*, user, session, amount_rub, method: str):
    title = escape(getattr(session, "title", "") or "Занятие")
    tg_send(
        "💳 <b>Оплата занятия</b>\n"
        f"Клиент: <b>{_fmt_user(user)}</b>\n"
        f"Занятие: <b>{title}</b>\n"
        f"Когда: <b>{_fmt_session_time(session)}</b>\n"
        f"Сумма: <b>{escape(str(amount_rub))} ₽</b>\n"
        f"Метод: <b>{escape(method)}</b>"
    )


def notify_rent_request_paid(*, session, request_obj):
    social = (getattr(request_obj, "social_handle", "") or "").strip()
    comment = (getattr(request_obj, "comment", "") or "").strip()
    promo = (getattr(request_obj, "promo_code", "") or "").strip()
    email = (getattr(request_obj, "email", "") or "").strip() or "—"
    phone = (getattr(request_obj, "phone", "") or "").strip() or "—"

    extra = ""
    if social:
        extra += f"\nСоцсети: <b>{escape(social)}</b>"
    if promo:
        extra += f"\nПромокод: <b>{escape(promo)}</b>"
    if comment:
        extra += f"\nКомментарий: <b>{escape(comment)}</b>"

    tg_send(
        "🏠 <b>Оплачена аренда зала</b>\n"
        f"Клиент: <b>{escape(getattr(request_obj, 'full_name', '') or '—')}</b>\n"
        f"Телефон: <b>{escape(phone)}</b>\n"
        f"E-mail: <b>{escape(email)}</b>\n"
        f"Когда: <b>{_fmt_session_time(session)}</b>\n"
        f"Адрес: <b>{escape(getattr(session, 'location', '') or '—')}</b>\n"
        f"Сумма: <b>{escape(str(getattr(request_obj, 'price_rub', 0)))} ₽</b>"
        f"{extra}"
    )
