from decimal import Decimal

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from loyalty.services import build_bonus_payment_plan, get_bonus_balance
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


def _membership_total_rub(items, products_by_id) -> int:
    total = 0
    for it in items:
        p = products_by_id.get(int(it.product_id))
        if not p or p.grant_kind != Product.GrantKind.MEMBERSHIP:
            continue
        total += int(it.total_price_rub)
    return total


def cart_view(request):
    cart = Cart(request)
    ids = [int(pid) for pid in cart.data.keys()]
    products = Product.objects.filter(id__in=ids)
    products_by_id = {p.id: p for p in products}
    items = list(cart.items(products_by_id))
    total_rub = cart.total_rub(products_by_id)
    membership_total_rub = _membership_total_rub(items, products_by_id)

    wallet_balance = None
    bonus_balance = Decimal("0.00")
    bonus_apply_rub = Decimal("0.00")
    bonus_cap_rub = Decimal("0.00")
    wallet_cash_needed_rub = Decimal(str(total_rub))
    can_pay_wallet = False
    if request.user.is_authenticated:
        wallet = get_wallet(request.user)
        wallet_balance = wallet.balance
        bonus_balance = get_bonus_balance(request.user)
        payment_plan = build_bonus_payment_plan(
            user=request.user,
            total_amount=Decimal(str(total_rub)),
            bonus_eligible_amount=Decimal(str(membership_total_rub)),
        )
        bonus_apply_rub = payment_plan["bonus_used"]
        bonus_cap_rub = payment_plan["bonus_cap"]
        wallet_cash_needed_rub = payment_plan["cash_needed"]
        can_pay_wallet = total_rub <= 0 or wallet_balance >= wallet_cash_needed_rub

    return render(
        request,
        "shop/cart.html",
        {
            "items": items,
            "total_rub": total_rub,
            "membership_total_rub": membership_total_rub,
            "wallet_balance": wallet_balance,
            "bonus_balance": bonus_balance,
            "bonus_apply_rub": bonus_apply_rub,
            "bonus_cap_rub": bonus_cap_rub,
            "wallet_cash_needed_rub": wallet_cash_needed_rub,
            "can_pay_wallet": can_pay_wallet,
        },
    )


def cart_set(request, product_id: int):
    cart = Cart(request)
    qty = int(request.POST.get("qty", "1"))
    cart.set(product_id, qty)
    return redirect("shop:cart")
