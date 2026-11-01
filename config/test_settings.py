"""Settings for the automated test suite: python manage.py test --settings=config.test_settings"""
import os

os.environ["DJANGO_DEBUG"] = "True"
os.environ["DATABASE_URL"] = "sqlite://:memory:"
os.environ["CELERY_EAGER"] = "True"
os.environ["CLOUDINARY_URL"] = ""
os.environ["PAYSTACK_MODE"] = "test"
os.environ["PAYSTACK_TEST_SECRET_KEY"] = "sk_test_unit_tests"
os.environ["PAYSTACK_TEST_PUBLIC_KEY"] = "pk_test_unit_tests"

from .settings import *  # noqa: E402,F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
MEDIA_ROOT = BASE_DIR / "test_media"  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
