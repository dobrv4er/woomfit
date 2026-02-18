from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),

    path("about/", views.about, name="about"),
    path("privacy/", views.privacy, name="privacy"),
    path("cookies/", views.cookies_policy, name="cookies_policy"),
    path("legal/cookies-settings/", views.cookie_settings, name="cookie_settings"),
    path("legal/cookies-consent/", views.cookie_consent, name="cookie_consent"),
    path("legal/offer/", views.public_offer, name="public_offer"),
    path("legal/refund/", views.refund_policy, name="refund_policy"),
    path("legal/consent/", views.personal_data_consent, name="personal_data_consent"),
    path("legal/requisites/", views.requisites, name="requisites"),
    path("trainers/", views.trainers, name="trainers"),
    path("rent/", views.rent, name="rent"),
    path("rent/pay/success/<int:intent_id>/", views.rent_pay_success, name="rent_pay_success"),
    path("rent/pay/fail/<int:intent_id>/", views.rent_pay_fail, name="rent_pay_fail"),
    path("call/", views.call, name="call"),
]
