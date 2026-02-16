import requests
from django.conf import settings


def tg_send(text: str):
    if not getattr(settings, "TELEGRAM_NOTIFICATIONS", True):
        return

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "8461664850:AAFx8pDlvP23E5ylJ0NvW_bBd0GA5ZMhXrg")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "-5116053559")

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
    except Exception as e:
        print("Telegram error:", e)


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

