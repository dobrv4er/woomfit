from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .cart import Cart
from .models import Category, Product, TrialUse
from wallet.services import get_wallet


def _add_product_to_cart(request, product: Product):
    """Общая логика добавления товара в корзину (включая ограничения по пробному)."""
    # пробное нельзя купить дважды
    if product.is_trial:
        if not request.user.is_authenticated:
            messages.error(request, "Пробное доступно только после входа.")
            return False

        if not product.trial_scope:
            messages.error(request, "У товара «Пробное» не указан тип (group/personal).")
            return False

        already = TrialUse.objects.filter(user=request.user, scope=product.trial_scope).exists()
        if already:
            messages.error(request, "Пробное уже было использовано.")
            return False

        # Чтобы «пробное» исчезало сразу после нажатия, фиксируем факт использования здесь.
        TrialUse.objects.get_or_create(user=request.user, scope=product.trial_scope)

    cart = Cart(request)
    cart.add(product.id, 1)
    return True


def shop_menu(request):
    cards = [
        {"key": Category.Section.MEMBERSHIPS, "title": "Абонементы", "sub": "Групповые и персональные", "emoji": "🎫"},
        {"key": Category.Section.PERSONAL, "title": "Персональные", "sub": "Разовые услуги + пробное", "emoji": "👤"},
        {"key": Category.Section.GROUP, "title": "Групповые", "sub": "Разовые услуги + пробное", "emoji": "🧘"},
        {"key": Category.Section.OTHER, "title": "Прочее", "sub": "Аренда и доп. услуги", "emoji": "✨"},
    ]
    return render(request, "shop/menu.html", {"cards": cards})


def shop_section(request, section: str):
    allowed = {k for (k, _) in Category.Section.choices}
    if section not in allowed:
        section = Category.Section.MEMBERSHIPS

    # какие пробные уже использовал пользователь
    used_scopes = set()
    if request.user.is_authenticated:
        used_scopes = set(
            TrialUse.objects.filter(user=request.user).values_list("scope", flat=True)
        )

    categories = Category.objects.filter(section=section).prefetch_related("products").all()

    # фильтруем товары (скрываем пробное после использования)
    cat_rows = []
    for c in categories:
        prods = []
        for p in c.products.all():
            if not p.is_active:
                continue

            if p.is_trial:
                # пробное видно только авторизованным и только если не использовано
                if not request.user.is_authenticated:
                    continue
                if not p.trial_scope:
                    # если админ забыл поставить scope — лучше скрыть
                    continue
                if p.trial_scope in used_scopes:
                    continue

            prods.append(p)

        if prods:
            cat_rows.append({"cat": c, "products": prods})

    section_label = dict(Category.Section.choices).get(section, "Магазин")
    return render(
        request,
        "shop/section.html",
        {"categories": cat_rows, "section": section, "section_label": section_label},
    )


def cart_add(request, product_id: int):
    p = get_object_or_404(Product, id=product_id, is_active=True)

    ok = _add_product_to_cart(request, p)
    if ok:
        messages.success(request, f"Добавлено: {p.name}")
    return redirect(request.META.get("HTTP_REFERER", "shop:index"))


def buy_now(request, product_id: int):
    """Купить сейчас: добавить товар в корзину и сразу открыть корзину."""
    p = get_object_or_404(Product, id=product_id, is_active=True)

    ok = _add_product_to_cart(request, p)
    if ok:
        messages.success(request, f"Добавлено: {p.name}")
        return redirect("shop:cart")

    # если не удалось (например, пробное без авторизации) — остаёмся на странице
    return redirect(request.META.get("HTTP_REFERER", "shop:index"))


def cart_view(request):
    cart = Cart(request)
    ids = [int(pid) for pid in cart.data.keys()]
    products = Product.objects.filter(id__in=ids)
    products_by_id = {p.id: p for p in products}
    items = list(cart.items(products_by_id))
    total_rub = cart.total_rub(products_by_id)

    wallet_balance = None
    can_pay_wallet = False
    if request.user.is_authenticated:
        wallet = get_wallet(request.user)
        wallet_balance = wallet.balance
        can_pay_wallet = total_rub <= 0 or wallet_balance >= Decimal(str(total_rub))

    return render(
        request,
        "shop/cart.html",
        {
            "items": items,
            "total_rub": total_rub,
            "wallet_balance": wallet_balance,
            "can_pay_wallet": can_pay_wallet,
            "tbank_terminal_key": settings.TBANK_TERMINAL_KEY,
        },
    )


def cart_set(request, product_id: int):
    cart = Cart(request)
    qty = int(request.POST.get("qty", "1"))
    cart.set(product_id, qty)
    return redirect("shop:cart")
