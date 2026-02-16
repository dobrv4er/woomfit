from dataclasses import dataclass


@dataclass
class CartItem:
    product_id: int
    name: str
    price_rub: int
    qty: int

    @property
    def total_price_rub(self) -> int:
        return int(self.price_rub) * int(self.qty)


class Cart:
    SESSION_KEY = "cart_v1"

    def __init__(self, request):
        self.request = request
        self.data = request.session.get(self.SESSION_KEY, {})  # {"12":2}

    def add(self, product_id: int, qty: int = 1):
        pid = str(product_id)
        self.data[pid] = max(1, int(self.data.get(pid, 0)) + int(qty))
        self._save()

    def set(self, product_id: int, qty: int):
        pid = str(product_id)
        qty = int(qty)
        if qty <= 0:
            self.data.pop(pid, None)
        else:
            self.data[pid] = qty
        self._save()

    def clear(self):
        self.data = {}
        self._save()

    def _save(self):
        self.request.session[self.SESSION_KEY] = self.data
        self.request.session.modified = True

    @property
    def count(self):
        return sum(int(q) for q in self.data.values())

    def __len__(self):
        return self.count

    def __iter__(self):
        """Позволяет делать list(cart) / for it in cart (нужно checkout)."""
        from .models import Product  # lazy import

        ids = [int(pid) for pid in self.data.keys()]
        products_by_id = {p.id: p for p in Product.objects.filter(id__in=ids)}
        yield from self.items(products_by_id)

    def items(self, products_by_id):
        for pid_str, qty in self.data.items():
            pid = int(pid_str)
            p = products_by_id.get(pid)
            if not p:
                continue
            yield CartItem(product_id=pid, name=p.name, price_rub=int(p.price_rub), qty=int(qty))

    def total_rub(self, products_by_id):
        return sum(it.price_rub * it.qty for it in self.items(products_by_id))
