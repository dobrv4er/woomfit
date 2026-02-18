# WOOM FIT — Django (mobile-first) + Desktop + MySQL + T‑Bank acquiring

## Запуск (Docker)
```bash
cp .env.example .env
docker compose up --build
```

Открыть: http://localhost:8000  
Админка: http://localhost:8000/admin

По умолчанию демо‑данные не загружаются.  
Если нужно загрузить их при старте контейнера, задайте `WOOMFIT_SEED_DEMO=1` в `.env`.

Создать суперюзера:
```bash
docker compose exec web python manage.py createsuperuser
```

## Что внутри
- Главная (лента + быстрые действия)
- Расписание (полоса дат + список занятий + запись/отмена)
- Магазин (категории-аккордеоны + sticky bar как в приложении)
- Корзина (кол-во + промокод-строка + итоги)
- Профиль / Личные данные
- Заказ + оплата через T‑Bank (Init) + webhook

> Для реальной оплаты нужен публичный HTTPS URL для NotificationURL/SuccessURL/FailURL.

## Юридическая и кассовая настройка (РФ)
Перед запуском в проде заполните в `.env`:

```env
# реквизиты продавца для страниц оферты/политик
LEGAL_BRAND_NAME=WOOM FIT
LEGAL_OPERATOR_NAME=
LEGAL_OPERATOR_ADDRESS=
LEGAL_OPERATOR_EMAIL=
LEGAL_OPERATOR_PHONE=
LEGAL_OPERATOR_INN=
LEGAL_OPERATOR_OGRN=
LEGAL_OPERATOR_WEBSITE=

# параметры чека T‑Bank (54-ФЗ)
TBANK_TAXATION=usn_income
TBANK_ITEM_TAX=none
TBANK_FFD_VERSION=1.2
TBANK_ITEM_PAYMENT_METHOD=full_payment
TBANK_ITEM_PAYMENT_OBJECT=service

# email-восстановление пароля
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=
PASSWORD_RESET_TIMEOUT=86400
PASSWORD_RESET_BASE_URL=https://ваш-домен.ru
```

Проверки в коде:
- отдельные страницы: оферта, оплата/возврат, согласие на ПДн, политика конфиденциальности, cookie, реквизиты;
- обязательные чекбоксы согласия на регистрации и перед оплатой;
- сохранение факта согласия (дата/IP) для пользователя и платежных сущностей;
- фискальный `Receipt` для T‑Bank с `Taxation`, `FfdVersion`, `PaymentMethod`, `PaymentObject`, `Tax`, `Email/Phone`.
