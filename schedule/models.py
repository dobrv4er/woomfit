from django.conf import settings
from django.db import models
from django.utils import timezone


class Trainer(models.Model):
    name = models.CharField("Имя", max_length=120)

    class Meta:
        verbose_name = "Тренер"
        verbose_name_plural = "Тренеры"

    def __str__(self) -> str:
        return self.name


class Workout(models.Model):
    name = models.CharField("Название", max_length=160)

    level = models.CharField("Уровень", max_length=80, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    what_to_bring = models.TextField("Что взять с собой", blank=True, default="")

    image = models.ImageField("Картинка", upload_to="workouts/", blank=True, null=True)

    default_duration_min = models.PositiveIntegerField("Длительность по умолчанию, мин", default=50)
    default_capacity = models.PositiveIntegerField("Вместимость по умолчанию", default=20)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Тренировка (шаблон)"
        verbose_name_plural = "Тренировки (шаблоны)"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Session(models.Model):
    class Kind(models.TextChoices):
        GROUP = "group", "Групповая"
        PERSONAL = "personal", "Персональная"
        RENT = "rent", "Аренда"

    # ✅ выбираемый шаблон тренировки
    workout = models.ForeignKey(
        Workout,
        verbose_name="Шаблон тренировки",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sessions",
        db_index=True,
    )

    title = models.CharField("Название", max_length=160)

    # kind определяет видимость:
    # - group: публичное расписание
    # - personal/rent: приватно (в публичном расписании НЕ показываем)
    kind = models.CharField(
        "Тип",
        max_length=16,
        choices=Kind.choices,
        default=Kind.GROUP,
        db_index=True,
    )

    # Для персональных/аренды: кому показывать (и на кого "создано")
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Клиент",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="private_sessions",
        db_index=True,
    )

    start_at = models.DateTimeField("Дата/время", db_index=True)
    duration_min = models.PositiveIntegerField("Длительность, мин", default=50)
    location = models.CharField("Адрес", max_length=160, db_index=True)

    trainer = models.ForeignKey(
        Trainer,
        verbose_name="Тренер",
        on_delete=models.PROTECT,
        related_name="sessions",
    )

    capacity = models.PositiveIntegerField("Вместимость", default=20)

    class Meta:
        verbose_name = "Занятие"
        verbose_name_plural = "Занятия"
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["location", "start_at"], name="sess_loc_start_idx"),
            models.Index(fields=["start_at"], name="sess_start_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} — {timezone.localtime(self.start_at).strftime('%d.%m %H:%M')}"

    @property
    def seats_left(self) -> int:
        booked = self.bookings.filter(booking_status=Booking.Status.BOOKED).count()
        return max(0, int(self.capacity) - int(booked))


class Booking(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Записан"
        WAITLIST = "waitlist", "Лист ожидания"
        INVITED = "invited", "Приглашён"
        CANCELED = "canceled", "Отменён"

    class Attendance(models.TextChoices):
        NOT_MARKED = "not_marked", "Не отмечено"
        ATTENDED = "attended", "Посетил"
        MISSED = "missed", "Не пришёл"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="bookings",
        db_index=True,
    )

    session = models.ForeignKey(
        Session,
        verbose_name="Занятие",
        on_delete=models.CASCADE,
        related_name="bookings",
        db_index=True,
    )

    membership = models.ForeignKey(
        "memberships.Membership",
        verbose_name="Абонемент",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        db_index=True,
    )

    booking_status = models.CharField(
        "Статус записи",
        max_length=16,
        choices=Status.choices,
        default=Status.BOOKED,
        db_index=True,
    )

    attendance_status = models.CharField(
        "Посещаемость",
        max_length=16,
        choices=Attendance.choices,
        default=Attendance.NOT_MARKED,
        db_index=True,
    )
    marked_at = models.DateTimeField("Отмечено", null=True, blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    canceled_at = models.DateTimeField("Отменено", null=True, blank=True)

    # --- лист ожидания / приглашения ---
    invite_sent_at = models.DateTimeField("Приглашение отправлено", null=True, blank=True)
    invite_expires_at = models.DateTimeField("Приглашение истекает", null=True, blank=True)

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        constraints = [
            models.UniqueConstraint(fields=["user", "session"], name="uniq_user_session"),
        ]
        indexes = [
            models.Index(fields=["user", "booking_status"], name="book_user_status_idx"),
            models.Index(fields=["session", "booking_status"], name="book_sess_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.session} ({self.booking_status})"

    def cancel(self):
        if self.booking_status != self.Status.CANCELED:
            self.booking_status = self.Status.CANCELED
            self.canceled_at = timezone.now()
            self.save(update_fields=["booking_status", "canceled_at"])

    # ⚠️ ВАЖНО: списание абонемента теперь делаем при записи (book),
    # а не при отметке посещаемости, иначе будет двойное списание.
    def mark_attended(self):
        self.attendance_status = self.Attendance.ATTENDED
        self.marked_at = timezone.now()
        self.save(update_fields=["attendance_status", "marked_at"])

    def mark_missed(self):
        self.attendance_status = self.Attendance.MISSED
        self.marked_at = timezone.now()
        self.save(update_fields=["attendance_status", "marked_at"])


class PaymentIntent(models.Model):
    """Оплата разового занятия (без абонемента)."""

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PENDING = "pending", "Ожидает оплату"
        PAID = "paid", "Оплачен"
        CANCELED = "canceled", "Отменён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="session_payment_intents",
        db_index=True,
    )
    session = models.ForeignKey(
        Session,
        verbose_name="Занятие",
        on_delete=models.CASCADE,
        related_name="payment_intents",
        db_index=True,
    )

    amount_rub = models.PositiveIntegerField("Сумма, руб", default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)

    tb_payment_id = models.CharField("TBank payment id", max_length=64, blank=True, default="")
    tb_status = models.CharField("TBank status", max_length=32, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Оплата занятия"
        verbose_name_plural = "Оплаты занятий"
        indexes = [
            models.Index(fields=["status", "created_at"], name="pi_status_created_idx"),
            models.Index(fields=["user", "created_at"], name="pi_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"PaymentIntent#{self.id} {self.user_id} → session#{self.session_id} ({self.status})"
