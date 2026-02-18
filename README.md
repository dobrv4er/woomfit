# WOOM FIT — Django (mobile-first) + Desktop + MySQL + T‑Bank acquiring

## Запуск через nginx (macOS и Windows)
Проект запускается одинаково на обеих ОС через Docker Desktop:  
`nginx -> gunicorn -> django -> mysql`.

### 1) Подготовка `.env`
macOS:
```bash
cp .env.example .env
```

Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

### 2) Запуск
macOS / Windows:
```bash
docker compose up --build -d
```

Открыть: http://localhost:8000  
Админка: http://localhost:8000/admin

Остановка:
```bash
docker compose down
```

## Если не запускается на Windows
Частая причина: `CRLF` в `entrypoint.sh` (ошибка вида `bad interpreter: /bin/sh^M`).
Также проект по умолчанию рассчитан на запуск через `docker compose` (а не `python manage.py runserver` напрямую).

В этом репозитории уже добавлена защита:
- `.gitattributes` фиксирует `LF` для `*.sh`;
- `docker-compose.yml` перед стартом удаляет `CRLF` из `/app/entrypoint.sh`.

После обновления репозитория выполните:
```powershell
docker compose down -v
docker compose up --build
```

Если всё ещё не стартует, пришлите логи:
```powershell
docker compose logs web --tail=200
docker compose logs db --tail=200
```

## HTTPS (домен + Let's Encrypt)
Нужен публичный сервер с доменом и открытыми портами `80` и `443`.

### 1) Подготовьте `.env` для прода
```env
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=ваш-домен.ru
DJANGO_CSRF_TRUSTED_ORIGINS=https://ваш-домен.ru
NGINX_HTTP_PORT=80
SSL_DOMAIN=ваш-домен.ru
```

### 2) Запустите HTTP-версию (для ACME challenge)
```bash
docker compose up -d --build
```

### 3) Выпустите сертификат
macOS/Linux (bash):
```bash
docker compose --profile certbot -f docker-compose.yml -f docker-compose.https.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d ваш-домен.ru \
  --email you@example.com --agree-tos --no-eff-email
```

Windows (PowerShell, в одну строку):
```powershell
docker compose --profile certbot -f docker-compose.yml -f docker-compose.https.yml run --rm certbot certonly --webroot -w /var/www/certbot -d ваш-домен.ru --email you@example.com --agree-tos --no-eff-email
```

### 4) Включите HTTPS nginx
```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d db web nginx
```

После этого сайт будет доступен по `https://ваш-домен.ru`.
Не забудьте в `.env` перевести `TBANK_NOTIFICATION_URL`, `TBANK_SUCCESS_URL`, `TBANK_FAIL_URL` на `https://`.

### 5) Продление сертификата
```bash
docker compose --profile certbot -f docker-compose.yml -f docker-compose.https.yml run --rm certbot renew
docker compose -f docker-compose.yml -f docker-compose.https.yml exec nginx nginx -s reload
```

### Если сертификат уже выдан у регистратора/хостинга
Скопируйте файлы в:
- `certbot/conf/live/ваш-домен.ru/privkey.pem`
- `certbot/conf/live/ваш-домен.ru/fullchain.pem`

После этого поднимайте только рабочие сервисы:
```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d db web nginx
```

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
