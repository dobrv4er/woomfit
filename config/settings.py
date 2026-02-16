import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,192.168.0.6").split(",")
    if h.strip()
]
if DEBUG:
    ALLOWED_HOSTS = ["*"]

# ЖЁСТКИЙ СПИСОК АДРЕСОВ (2 штуки)
# Можно переопределять через .env:
# WOOMFIT_LOCATIONS="Адрес 1|Адрес 2"
WOOMFIT_LOCATIONS = [
    x.strip()
    for x in os.environ.get("WOOMFIT_LOCATIONS", "Сакко и Ванцетти,93а|Аркадия Гайдара,8б").split("|")
    if x.strip()
]

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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_NOTIFICATIONS = os.getenv("TELEGRAM_NOTIFICATIONS", "0") == "1"
