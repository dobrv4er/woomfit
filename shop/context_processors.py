from .cart import Cart
from .models import Product

def cart_summary(request):
    cart = Cart(request)
    total_rub = 0
    if cart.data:
        ids = [int(pid) for pid in cart.data.keys()]
        products = Product.objects.filter(id__in=ids).only("id","price_rub")
        prices = {p.id: p.price_rub for p in products}
        for pid_str, qty in cart.data.items():
            total_rub += int(prices.get(int(pid_str), 0)) * int(qty)
    return {"cart": {"count": cart.count, "total_rub": total_rub}}
