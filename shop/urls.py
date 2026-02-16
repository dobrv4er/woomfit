from django.urls import path
from . import views

app_name = "shop"

urlpatterns = [
    path("", views.shop_menu, name="index"),      # ✅ совместимость
    path("", views.shop_menu, name="menu"),
    path("section/<str:section>/", views.shop_section, name="section"),

    # Быстрая покупка: добавляет товар и ведёт в корзину
    path("buy/<int:product_id>/", views.buy_now, name="buy_now"),

    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/set/<int:product_id>/", views.cart_set, name="cart_set"),
]
