import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "woomfit-dev-only-change-me-before-production-6f42f4c9b8"
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,192.168.0.6").split(",")
    if h.strip()
]
if DEBUG:
    ALLOWED_HOSTS = ["*"]

# Security defaults for production; can be overridden from .env
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", SECURE_HSTS_SECONDS > 0)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", SECURE_HSTS_SECONDS > 0)
# T-Bank IntegrationJS requires COOP header to be absent.
_secure_coop = (os.environ.get("DJANGO_SECURE_CROSS_ORIGIN_OPENER_POLICY", "none") or "").strip().lower()
SECURE_CROSS_ORIGIN_OPENER_POLICY = None if _secure_coop in ("", "none", "null", "off") else _secure_coop
# Trust HTTPS forwarded by nginx when SSL is terminated at proxy level.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# ЖЁСТКИЙ СПИСОК АДРЕСОВ (2 штуки)
# Можно переопределять через .env:
# WOOMFIT_LOCATIONS="Адрес 1|Адрес 2"
WOOMFIT_LOCATIONS = [
    x.strip()
    for x in os.environ.get("WOOMFIT_LOCATIONS", "Сакко и Ванцетти, 93а|А. Гайдара, 8Б").split("|")
    if x.strip()
]

# Юридические реквизиты для документов на сайте
LEGAL_BRAND_NAME = os.environ.get("LEGAL_BRAND_NAME", "WOOM FIT")
LEGAL_OPERATOR_NAME = os.environ.get("LEGAL_OPERATOR_NAME", "Индивидуальный предприниматель Карамит Дарья Романовна")
LEGAL_OPERATOR_ADDRESS = os.environ.get("LEGAL_OPERATOR_ADDRESS", "г. Пермь, ул. Сапфирная, 10")
LEGAL_OPERATOR_EMAIL = os.environ.get("LEGAL_OPERATOR_EMAIL", "Karamit_darya@mail.ru")
LEGAL_OPERATOR_PHONE = os.environ.get("LEGAL_OPERATOR_PHONE", "+7 (922) 355-53-61")
LEGAL_OPERATOR_INN = os.environ.get("LEGAL_OPERATOR_INN", "590619040190")
LEGAL_OPERATOR_OGRN = os.environ.get("LEGAL_OPERATOR_OGRN", "321595800041980")
LEGAL_OPERATOR_WEBSITE = os.environ.get("LEGAL_OPERATOR_WEBSITE", "")
LEGAL_STUDIO_ADDRESSES = [
    x.strip()
    for x in os.environ.get(
        "LEGAL_STUDIO_ADDRESSES",
        "г. Пермь, ул. Сакко и Ванцетти, 93а|г. Пермь, ул. А. Гайдара, 8Б",
    ).split("|")
    if x.strip()
]
LEGAL_BANK_ACCOUNT = os.environ.get("LEGAL_BANK_ACCOUNT", "40802810000005159784")
LEGAL_BANK_NAME = os.environ.get("LEGAL_BANK_NAME", "АО «ТБанк»")
LEGAL_BANK_BIK = os.environ.get("LEGAL_BANK_BIK", "044525974")
LEGAL_BANK_CORR_ACCOUNT = os.environ.get("LEGAL_BANK_CORR_ACCOUNT", "30101810145250000974")
LEGAL_BANK_ADDRESS = os.environ.get(
    "LEGAL_BANK_ADDRESS",
    "127287, г. Москва, ул. Хуторская 2-я, д. 38А, стр. 26",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "wallet.apps.WalletConfig",
    "core",
    "accounts",
    "schedule",
    "shop",
    "orders",
    "payments",
    "crmdata",
    "memberships",
    "loyalty.apps.LoyaltyConfig",


    # ✅ новости
    "news",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shop.context_processors.cart_summary",

                # ✅ топ-новости на главной
                "news.context_processors.top_news",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", "woomfit"),
        "USER": os.environ.get("MYSQL_USER", "woomfit"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "woomfit"),
        "HOST": os.environ.get("MYSQL_HOST", "db"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

# ✅ Кэш (под оптимизацию расписания/новостей)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "woomfit-cache",
        "TIMEOUT": int(os.environ.get("DJANGO_CACHE_TIMEOUT", "60")),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.UsernameOrPhoneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_REDIRECT_URL = "/profile/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", "86400"))
PASSWORD_RESET_BASE_URL = (os.environ.get("PASSWORD_RESET_BASE_URL", "") or "").strip()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Yekaterinburg"
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ✅ медиа (фото новостей, обложки и т.д.)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ✅ ВАЖНО: должен быть default storage, иначе загрузка в админке падает
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# T-Bank (use .env, do NOT hardcode secrets)
TBANK_TERMINAL_KEY = os.getenv("TBANK_TERMINAL_KEY", "")
TBANK_PASSWORD = os.getenv("TBANK_PASSWORD", "")  # именно SecretKey!
TBANK_IS_TEST = os.getenv("TBANK_IS_TEST", "1") in ("1", "true", "True", "yes")


TBANK_NOTIFICATION_URL = os.getenv("TBANK_NOTIFICATION_URL", "")
TBANK_SUCCESS_URL = os.getenv("TBANK_SUCCESS_URL", "")
TBANK_FAIL_URL = os.getenv("TBANK_FAIL_URL", "")

# Receipt (online cashbox). Required if online-cashbox is enabled on the terminal.
# Common values:
#   TBANK_TAXATION: osn | usn_income | usn_income_outcome | envd | esn | patent
#   TBANK_ITEM_TAX: none | vat0 | vat10 | vat20 | ...
TBANK_TAXATION = os.getenv("TBANK_TAXATION", "usn_income")
TBANK_ITEM_TAX = os.getenv("TBANK_ITEM_TAX", "none")
TBANK_FFD_VERSION = os.getenv("TBANK_FFD_VERSION", "1.2")
TBANK_ITEM_PAYMENT_METHOD = os.getenv("TBANK_ITEM_PAYMENT_METHOD", "full_payment")
TBANK_ITEM_PAYMENT_OBJECT = os.getenv("TBANK_ITEM_PAYMENT_OBJECT", "service")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_NOTIFICATIONS = os.getenv("TELEGRAM_NOTIFICATIONS", "0") == "1"

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", LEGAL_OPERATOR_EMAIL or "no-reply@woomfit.local")
