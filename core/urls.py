from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    
    path("about/", views.about, name="about"),
    path("trainers/", views.trainers, name="trainers"),
    path("rent/", views.rent, name="rent"),
    path("call/", views.call, name="call"),
]
