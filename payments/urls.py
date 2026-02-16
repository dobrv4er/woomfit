from django.urls import path
from . import views

app_name="payments"
urlpatterns = [
    path("success/", views.payment_success, name="success"),
    path("fail/", views.payment_fail, name="fail"),
    path("tbank/webhook/", views.tbank_webhook, name="tbank_webhook"),
]
