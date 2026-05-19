"""Minimal Django settings for the django-q2 sample project.

Uses the ORM broker so the sample stack stays single-image — no Redis or
external broker required. The web and worker containers share a SQLite file
via a docker volume.
"""

import os
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SAMPLE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", uuid.uuid4().hex)
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_q",
    "tasks_app",
]

MIDDLEWARE = []

ROOT_URLCONF = "sample.urls"
WSGI_APPLICATION = "sample.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {},
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DATA_DIR / "db.sqlite3"),
        "OPTIONS": {
            # WAL lets the web and worker processes read/write the same file safely.
            "init_command": "PRAGMA journal_mode=WAL;",
            "timeout": 20,
        },
    },
}

# django-q2's `async_iter` coalesces sub-task results through `broker.cache`,
# which is Django's cache framework. The default `LocMemCache` is process-local,
# so the worker processes that finish each sub-task can't see each other's
# intermediate results and the iter result never lands. A file-backed cache
# inside the shared SAMPLE_DATA_DIR volume is the simplest cross-process option
# that works without standing up Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(DATA_DIR / "django-cache"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

Q_CLUSTER = {
    "name": os.environ.get("Q_CLUSTER_NAME", "sample-cluster"),
    "workers": int(os.environ.get("Q_CLUSTER_WORKERS", "2")),
    "timeout": 60,
    "retry": 90,
    "orm": "default",
    "sync": False,
    "catch_up": False,
    "save_limit": 200,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "loggers": {
        "django_q": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "tasks_app": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
