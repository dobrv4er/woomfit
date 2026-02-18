import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


NON_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(phone: str) -> str:
    digits = NON_DIGITS_RE.sub("", phone or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = f"7{digits}"
    if len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    return digits


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class UsernameOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if password is None:
            return None

        user_model = get_user_model()
        login_value = (username or kwargs.get(user_model.USERNAME_FIELD) or "").strip()
        if not login_value:
            return None

        by_username = user_model._default_manager.filter(username__iexact=login_value).first()
        if by_username and by_username.check_password(password) and self.user_can_authenticate(by_username):
            return by_username

        email = normalize_email(login_value)
        if email:
            by_email = list(user_model._default_manager.filter(email__iexact=email).exclude(email="")[:2])
            if len(by_email) == 1:
                user = by_email[0]
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user

        phone = normalize_phone(login_value)
        if not phone:
            return None

        users = user_model._default_manager.exclude(phone="")
        matched = [u for u in users if normalize_phone(getattr(u, "phone", "")) == phone]
        if len(matched) != 1:
            return None

        user = matched[0]
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
