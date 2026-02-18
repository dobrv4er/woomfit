import re
from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm, _unicode_ci_compare
from django.utils.crypto import get_random_string

from .models import User


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def build_full_name(first_name: str, last_name: str) -> str:
    return f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = f"7{digits}"
    if len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    return digits


def format_phone(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    return (phone or "").strip()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_phone(phone: str, *, required: bool) -> str:
    if not (phone or "").strip():
        if required:
            raise forms.ValidationError("Укажите телефон.")
        return ""

    digits = normalize_phone(phone)
    if len(digits) != 11:
        raise forms.ValidationError("Телефон должен содержать 11 цифр, например +7 999 999 99 99.")
    if not digits.startswith("7"):
        raise forms.ValidationError("Телефон должен начинаться с +7 или 8.")
    return digits


def phone_conflicts(phone: str, *, exclude_user_id=None) -> bool:
    qs = User.objects.exclude(phone="")
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)
    for existing_phone in qs.values_list("phone", flat=True):
        if normalize_phone(existing_phone) == phone:
            return True
    return False


def email_conflicts(email: str, *, exclude_user_id=None) -> bool:
    if not email:
        return False
    qs = User.objects.filter(email__iexact=email)
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)
    return qs.exists()


def generate_unique_username(phone: str = "") -> str:
    base = f"user_{phone}" if phone else f"user_{get_random_string(8)}"
    username = base
    index = 1
    while User.objects.filter(username=username).exists():
        index += 1
        suffix = f"_{index}"
        username = f"{base[:150 - len(suffix)]}{suffix}"
    return username


class ProfileForm(forms.ModelForm):
    phone = forms.CharField(
        label="Телефон",
        required=False,
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "inputmode": "tel",
                "autocomplete": "tel",
                "placeholder": "+7 999 999 99 99",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "client@example.com",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["phone", "email", "birth_date"]
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["phone"] = format_phone(self.instance.phone)
            self.initial["email"] = self.instance.email

    def clean_phone(self):
        phone = validate_phone(self.cleaned_data.get("phone"), required=False)
        if not phone:
            return ""
        if phone_conflicts(phone, exclude_user_id=self.instance.pk):
            raise forms.ValidationError("Пользователь с таким телефоном уже существует.")
        return phone

    def clean_email(self):
        email = normalize_email(self.cleaned_data.get("email", ""))
        if not email:
            return ""
        if email_conflicts(email, exclude_user_id=self.instance.pk):
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class ProfileNameForm(forms.Form):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)

    def __init__(self, *args, user: User, **kwargs):
        self.user = user
        initial = kwargs.get("initial") or {}
        kwargs["initial"] = initial
        first_name, last_name = split_full_name(user.get_full_name())
        initial.setdefault("first_name", first_name)
        initial.setdefault("last_name", last_name)
        super().__init__(*args, **kwargs)

    def save(self) -> User:
        self.user.full_name = build_full_name(
            self.cleaned_data["first_name"], self.cleaned_data["last_name"]
        )
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save(update_fields=["full_name", "first_name", "last_name"])
        return self.user


class SignUpForm(UserCreationForm):
    username = forms.CharField(required=False, widget=forms.HiddenInput)
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)
    phone = forms.CharField(
        label="Телефон",
        required=True,
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "inputmode": "tel",
                "autocomplete": "tel",
                "placeholder": "+7 999 999 99 99",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        required=True,
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "client@example.com",
            }
        ),
    )
    agree_offer = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"style": "width:16px; margin-top:2px;"}),
        error_messages={"required": "Необходимо принять условия публичной оферты."},
    )
    agree_personal_data = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"style": "width:16px; margin-top:2px;"}),
        error_messages={"required": "Необходимо дать согласие на обработку персональных данных."},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "phone", "email", "password1", "password2")

    def clean_username(self):
        return ""

    def clean_phone(self):
        phone = validate_phone(self.cleaned_data.get("phone"), required=True)
        if phone_conflicts(phone):
            raise forms.ValidationError("Пользователь с таким телефоном уже существует.")
        return phone

    def clean_email(self):
        email = normalize_email(self.cleaned_data.get("email", ""))
        if email_conflicts(email):
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        first_name = self.cleaned_data.get("first_name", "")
        last_name = self.cleaned_data.get("last_name", "")

        user.full_name = build_full_name(first_name, last_name)
        user.first_name = ""
        user.last_name = ""
        user.phone = self.cleaned_data.get("phone", "")
        user.email = self.cleaned_data.get("email", "")
        user.username = generate_unique_username(user.phone)

        if commit:
            user.save()
        return user


class PasswordResetByEmailForm(PasswordResetForm):
    """
    Разрешаем восстановление для импортированных клиентов с unusable password.
    """

    def get_users(self, email):
        user_model = get_user_model()
        email_field_name = user_model.get_email_field_name()
        active_users = user_model._default_manager.filter(
            **{
                f"{email_field_name}__iexact": email,
                "is_active": True,
            }
        )
        return (
            u
            for u in active_users
            if getattr(u, email_field_name) and _unicode_ci_compare(email, getattr(u, email_field_name))
        )

    def save(self, *args, **kwargs):
        base_url = (getattr(settings, "PASSWORD_RESET_BASE_URL", "") or "").strip()
        if base_url and not kwargs.get("domain_override"):
            parsed = urlsplit(base_url)
            domain = (parsed.netloc or parsed.path or "").strip().rstrip("/")
            if domain:
                kwargs["domain_override"] = domain
                kwargs["request"] = None
                if parsed.scheme in ("http", "https"):
                    kwargs["use_https"] = parsed.scheme == "https"
        return super().save(*args, **kwargs)
