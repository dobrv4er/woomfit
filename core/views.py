from django.shortcuts import render
from schedule.models import Booking, Trainer


def home(request):
    my_bookings = []
    if request.user.is_authenticated:
        my_bookings = (
            Booking.objects.select_related("session")
            .filter(user=request.user, booking_status=Booking.Status.BOOKED)
            .order_by("session__start_at")
        )

    # ВАЖНО: top_news НЕ трогаем — если он подмешивается где-то ещё, он останется.
    # Но чтобы шаблон не ломался, если top_news не пришёл — подадим пустой список.
    ctx = {"my_bookings": my_bookings}
    if "top_news" not in ctx:
        ctx["top_news"] = []

    return render(request, "core/home.html", ctx)


def about(request):
    return render(request, "core/static_page.html", {
        "title": "О клубе",
        "subtitle": "Информация о нас, контактная информация и телефоны",
        "lines": [
            "WOOM FIT — студия тренировок.",
            "Заполните контакты в шаблоне или вынесите в настройки (SiteSettings).",
        ]
    })


def trainers(request):
    return render(request, "core/trainers.html", {"trainers": Trainer.objects.order_by('name')})


def rent(request):
    return render(request, "core/static_page.html", {
        "title": "Аренда зала",
        "subtitle": "Вы можете взять в аренду зал в нашем клубе",
        "lines": ["Оставьте заявку у администратора или позвоните в клуб."],
    })


def call(request):
    phone = "+7 (000) 000-00-00"
    tel = "+70000000000"
    return render(request, "core/static_page.html", {
        "title": "Позвонить в клуб",
        "subtitle": "Быстрый способ позвонить на ресепшн нам в клуб",
        "lines": [f"Телефон: {phone}"],
        "button": {"label": "Позвонить", "href": f"tel:{tel}"},
    })
