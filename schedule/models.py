from datetime import timedelta
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _norm_addr(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", s)


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

    def clean(self):
        super().clean()

        if not self.start_at or not self.duration_min or not self.location:
            return

        own_start = self.start_at
        own_duration = max(1, int(self.duration_min or 0))
        own_end = own_start + timedelta(minutes=own_duration)
        own_loc = _norm_addr(self.location)

        # Запрещаем пересечения по залу: это защищает от постановки тренировки
        # поверх оплаченной аренды и наоборот.
        location_qs = (
            Session.objects
            .filter(start_at__lt=own_end)
            .exclude(pk=self.pk)
            .order_by("start_at")
        )
        for other in location_qs:
            if _norm_addr(other.location) != own_loc:
                continue
            other_start = other.start_at
            other_end = other_start + timedelta(minutes=max(1, int(other.duration_min or 0)))
            if own_start < other_end and other_start < own_end:
                other_start_local = timezone.localtime(other_start)
                other_end_local = timezone.localtime(other_end)
                if self.kind == self.Kind.RENT or other.kind == self.Kind.RENT:
                    raise ValidationError({
                        "start_at": (
                            "Зал уже забронирован на это время: "
                            f"{other_start_local.strftime('%d.%m %H:%M')}–{other_end_local.strftime('%H:%M')}."
                        )
                    })
                raise ValidationError({
                    "start_at": (
                        "В этом зале уже есть занятие: "
                        f"{other_start_local.strftime('%d.%m %H:%M')}–{other_end_local.strftime('%H:%M')}."
                    )
                })

        if not self.trainer_id:
            return

        trainer_qs = (
            Session.objects
            .filter(trainer_id=self.trainer_id, start_at__lt=own_end)
            .exclude(pk=self.pk)
            .order_by("start_at")
        )
        for other in trainer_qs:
            other_start = other.start_at
            other_end = other_start + timedelta(minutes=max(1, int(other.duration_min or 0)))
            if own_start < other_end and other_start < own_end:
                other_start_local = timezone.localtime(other_start)
                other_end_local = timezone.localtime(other_end)
                raise ValidationError({
                    "trainer": (
                        "У тренера уже есть занятие в это время: "
                        f"{other_start_local.strftime('%d.%m %H:%M')}–{other_end_local.strftime('%H:%M')}."
                    )
                })

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


class RentRequest(models.Model):
    session = models.OneToOneField(
        Session,
        verbose_name="Слот аренды",
        on_delete=models.CASCADE,
        related_name="rent_request",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rent_requests",
        db_index=True,
    )

    full_name = models.CharField("ФИО", max_length=255)
    email = models.EmailField("E-mail", blank=True, default="")
    phone = models.CharField("Телефон", max_length=32)
    social_handle = models.CharField("Соцсети", max_length=120, blank=True, default="")
    comment = models.TextField("Комментарий", blank=True, default="")
    promo_code = models.CharField("Промокод", max_length=64, blank=True, default="")

    price_rub = models.PositiveIntegerField("Стоимость, руб", default=650)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Заявка на аренду"
        verbose_name_plural = "Заявки на аренду"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="rentreq_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} — {timezone.localtime(self.session.start_at).strftime('%d.%m %H:%M')}"


class RentPaymentIntent(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PENDING = "pending", "Ожидает оплату"
        PAID = "paid", "Оплачен"
        CANCELED = "canceled", "Отменён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rent_payment_intents",
        db_index=True,
    )
    session = models.ForeignKey(
        Session,
        verbose_name="Слот аренды",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rent_payment_intents",
        db_index=True,
    )

    location = models.CharField("Адрес", max_length=160, db_index=True)
    slot_start = models.DateTimeField("Начало слота", db_index=True)
    duration_min = models.PositiveIntegerField("Длительность, мин", default=60)

    full_name = models.CharField("ФИО", max_length=255)
    email = models.EmailField("E-mail", blank=True, default="")
    phone = models.CharField("Телефон", max_length=32)
    social_handle = models.CharField("Соцсети", max_length=120, blank=True, default="")
    comment = models.TextField("Комментарий", blank=True, default="")
    promo_code = models.CharField("Промокод", max_length=64, blank=True, default="")

    amount_rub = models.PositiveIntegerField("Сумма, руб", default=650)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)

    tb_payment_id = models.CharField("TBank payment id", max_length=64, blank=True, default="")
    tb_status = models.CharField("TBank status", max_length=32, blank=True, default="")

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    expires_at = models.DateTimeField("Оплатить до", db_index=True)
    paid_at = models.DateTimeField("Оплачено", null=True, blank=True)

    class Meta:
        verbose_name = "Намерение оплаты аренды"
        verbose_name_plural = "Намерения оплаты аренды"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="rentpi_status_exp_idx"),
            models.Index(fields=["location", "slot_start"], name="rentpi_loc_slot_idx"),
        ]

    def __str__(self) -> str:
        return f"RentPaymentIntent#{self.id} {self.full_name} ({self.status})"


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
    legal_accepted_at = models.DateTimeField("Юр. согласие: дата", null=True, blank=True)
    legal_accept_ip = models.GenericIPAddressField("Юр. согласие: IP", null=True, blank=True)

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
