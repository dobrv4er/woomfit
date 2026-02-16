from django.db import models
from django.conf import settings
from django.utils import timezone


class Membership(models.Model):
    class Kind(models.TextChoices):
        VISITS = "visits", "По посещениям"
        TIME = "time", "По времени"
        UNLIMITED = "unlimited", "Безлимит"

    class Scope(models.TextChoices):
        GROUP = "group", "Групповые"
        PERSONAL = "personal", "Персональные"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")

    title = models.CharField(max_length=120, default="Абонемент")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.VISITS)

    # ✅ Для каких тренировок действует
    scope = models.CharField(
        max_length=16,
        choices=Scope.choices,
        blank=True,
        default="",
        help_text="group/personal (можно оставить пустым для совместимости со старыми данными)",
    )

    # Для VISITS
    total_visits = models.PositiveIntegerField(null=True, blank=True)
    left_visits = models.PositiveIntegerField(null=True, blank=True)

    # Для TIME / UNLIMITED (и можно для VISITS тоже, если есть срок)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def active_by_date(self) -> bool:
        today = timezone.localdate()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True

    def can_book_group(self) -> bool:
        if self.scope and self.scope != self.Scope.GROUP:
            return False
        if not self.is_active:
            return False
        if not self.active_by_date():
            return False
        if self.kind == self.Kind.VISITS:
            return (self.left_visits is None) or (self.left_visits > 0)
        return True

    def consume_visit(self) -> bool:
        """
        Списать 1 посещение.
        True если списали, False если нельзя списать.
        """
        if self.kind != self.Kind.VISITS:
            return True  # для TIME/UNLIMITED списания нет

        if self.left_visits is None:
            return True  # если вдруг "безлимит по посещениям"
        if self.left_visits <= 0:
            return False

        self.left_visits -= 1

        # если кончилось — делаем неактивным (чтобы не проходил проверки)
        if self.left_visits == 0:
            self.is_active = False
            self.save(update_fields=["left_visits", "is_active"])
        else:
            self.save(update_fields=["left_visits"])
        return True

    def refund_visit(self) -> None:
        """
        Вернуть 1 посещение (при отмене записи).
        Возврат делаем только для VISITS и только если left_visits ведётся.
        """
        if self.kind != self.Kind.VISITS:
            return
        if self.left_visits is None:
            return

        # Не превышаем total_visits если он задан
        if self.total_visits is not None:
            self.left_visits = min(self.total_visits, self.left_visits + 1)
        else:
            self.left_visits += 1

        # если возвращаем — активируем обратно
        if self.left_visits > 0 and not self.is_active:
            self.is_active = True
            self.save(update_fields=["left_visits", "is_active"])
        else:
            self.save(update_fields=["left_visits"])
