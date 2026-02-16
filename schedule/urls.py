from django.urls import path
from . import views

app_name = "schedule"

urlpatterns = [
    path("", views.schedule_list, name="list"),
    path("fragment/", views.schedule_fragment, name="fragment"),

    path("session/<int:session_id>/", views.session_detail, name="detail"),

    # обработчик выбора оплаты (POST из bottom-sheet, GET fallback)
    path("session/<int:session_id>/choose/", views.session_choose_payment, name="choose_payment"),

    path("session/<int:session_id>/pay/", views.session_pay, name="pay"),
    path("session/pay/success/<int:intent_id>/", views.session_pay_success, name="pay_success"),
    path("session/pay/fail/<int:intent_id>/", views.session_pay_fail, name="pay_fail"),

    # отмена записи
    path("unbook/<int:session_id>/", views.unbook_session, name="unbook"),
]
