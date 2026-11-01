import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(os.environ.get(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- core
DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is False.")

def _host(value):
    """Accept 'https://example.com/' or 'example.com' and return just the hostname."""
    return value.strip().replace("https://", "").replace("http://", "").strip("/")


ALLOWED_HOSTS = [_host(h) for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Render tells every service its own public hostname; trust it automatically so a typo cannot lock the site out.
RENDER_HOST = env("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)
CSRF_TRUSTED_ORIGINS = [o.strip().rstrip("/") for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if RENDER_HOST and f"https://{RENDER_HOST}" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")
SITE_URL = (env("SITE_URL", "") or (f"https://{RENDER_HOST}" if RENDER_HOST else "http://localhost:8000")).rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # project apps
    "core",
    "accounts",
    "catalog",
    "inventory",
    "cart",
    "wishlist",
    "orders",
    "payments",
    "referrals",
    "notifications",
    "marketing",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ReferralCaptureMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
                "core.context_processors.site",
            ],
        },
    },
]

# ---------------------------------------------------------------- database
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- auth
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "core:home"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static / media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

def _first(*names):
    """First non-empty environment value among several accepted spellings."""
    for n in names:
        v = env(n, "").strip()
        if v:
            return v
    return ""


# Cloudinary can be configured with ONE variable (CLOUDINARY_URL) or with three separate ones.
CLOUDINARY_CLOUD_NAME = _first("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_NAME", "CLOUD_NAME")
CLOUDINARY_API_KEY = _first("CLOUDINARY_API_KEY", "CLOUDINARY_KEY", "API_KEY")
CLOUDINARY_API_SECRET = _first("CLOUDINARY_API_SECRET", "CLOUDINARY_SECRET", "API_SECRET")
CLOUDINARY_URL = env("CLOUDINARY_URL", "").strip()
if not CLOUDINARY_URL and CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    from urllib.parse import quote

    CLOUDINARY_URL = f"cloudinary://{quote(CLOUDINARY_API_KEY, safe='')}:{quote(CLOUDINARY_API_SECRET, safe='')}@{CLOUDINARY_CLOUD_NAME}"
if CLOUDINARY_URL:
    import os as _os

    _os.environ["CLOUDINARY_URL"] = CLOUDINARY_URL  # the cloudinary library reads its credentials from here
    # cloudinary_storage must come before staticfiles; cloudinary after it.
    INSTALLED_APPS = ["cloudinary_storage"] + INSTALLED_APPS + ["cloudinary"]
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}
    if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        CLOUDINARY_STORAGE = {
            "CLOUD_NAME": CLOUDINARY_CLOUD_NAME, "API_KEY": CLOUDINARY_API_KEY, "API_SECRET": CLOUDINARY_API_SECRET,
        }

DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 30
MAX_IMAGE_UPLOAD_MB = 5

# ---------------------------------------------------------------- email
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "A&M Home Appliances <no-reply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------- celery
CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_EAGER", DEBUG)
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "sync-promotions": {"task": "catalog.tasks.sync_promotions", "schedule": 60.0},
    "dispatch-due-campaigns": {"task": "marketing.tasks.dispatch_due_campaigns", "schedule": 60.0},
    "abandoned-cart-reminders": {"task": "cart.tasks.send_abandoned_cart_reminders", "schedule": 600.0},
    "retry-failed-emails": {"task": "notifications.tasks.retry_failed_emails", "schedule": 300.0},
    "expire-unpaid-orders": {"task": "orders.tasks.expire_unpaid_orders", "schedule": 900.0},
}

# ---------------------------------------------------------------- paystack
PAYSTACK_MODE = env("PAYSTACK_MODE", "test").lower()
if PAYSTACK_MODE not in ("test", "live"):
    raise ImproperlyConfigured("PAYSTACK_MODE must be 'test' or 'live'.")
PAYSTACK_SECRET_KEY = env(f"PAYSTACK_{PAYSTACK_MODE.upper()}_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = env(f"PAYSTACK_{PAYSTACK_MODE.upper()}_PUBLIC_KEY", "")

# ---------------------------------------------------------------- security
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------- logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
