from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("", views.profile, name="profile"),
    path("personal/", views.personal_data, name="personal"),
    path("signup/", views.signup, name="signup"),
]
