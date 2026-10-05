"""Configuración de Django para el proyecto Contabilidad UNI.

Todo apunta a un uso local: SQLite, DEBUG activable por variable de entorno y
sin dependencias externas. La aplicación no tiene login: como en la versión web
estática, cada navegador trabaja con sus propios casos guardados en la sesión.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Clave de desarrollo. En un servidor real se pasa por la variable de entorno.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "clave-solo-para-desarrollo-no-usar-en-produccion"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# En un servidor de verdad, DJANGO_DEBUG=0 y DJANGO_HOSTS con el dominio.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

ALLOWED_HOSTS = os.environ.get("DJANGO_HOSTS", "localhost,127.0.0.1,[::1]").split(",")

CSRF_TRUSTED_ORIGINS = [
    origen
    for origen in os.environ.get("DJANGO_CSRF_ORIGINS", "").split(",")
    if origen.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "nucleo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sirve el CSS y los iconos sin necesitar nginx ni Apache:
    # asi el proyecto se despliega igual en un hosting de Python.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "contabilidad.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "plantillas"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "nucleo.contexto.navegacion",
            ],
        },
    },
]

WSGI_APPLICATION = "contabilidad.wsgi.application"
ASGI_APPLICATION = "contabilidad.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
