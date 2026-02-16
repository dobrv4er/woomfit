# WOOM FIT — Django (mobile-first) + Desktop + MySQL + T‑Bank acquiring

## Запуск (Docker)
```bash
cp .env.example .env
docker compose up --build
```

Открыть: http://localhost:8000  
Админка: http://localhost:8000/admin

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
