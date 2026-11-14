from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")  # already set environment variables are not overwritten


def database_from_env(default: str | None) -> dict:
    """Read DATABASE_URL and force the GeoDjango backend for any postgres scheme."""
    config = env.db("DATABASE_URL", default=default)
    config["ENGINE"] = "django.contrib.gis.db.backends.postgis"
    if "-pooler" in config.get("HOST", ""):
        # Neon's PgBouncer pooler (transaction mode) does not support server-side cursors.
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
    return config


def allowed_hosts_from_env() -> list[str]:
    """ALLOWED_HOSTS plus the hostname Render injects, so a fresh deploy works without extra setup."""
    hosts = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
    render_host = env.str("RENDER_EXTERNAL_HOSTNAME", default="")
    if render_host:
        hosts.append(render_host)
    return hosts


SECRET_KEY = env.str("SECRET_KEY", default="kamqor-demo-insecure-secret-key")
DEBUG = env.bool("DEBUG", False)
ALLOWED_HOSTS = allowed_hosts_from_env()
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEPLOY_PROFILE = env.str("DEPLOY_PROFILE", default="demo")
DEMO_OTP_CODE = env.str("DEMO_OTP_CODE", default="0000")
DEMO_CONTACT_PHONE = env.str("DEMO_CONTACT_PHONE", default="")

BRAND_NAME = "Особенный путь с Mama Pro"  # not translated: the same name in RU and KZ

GDAL_LIBRARY_PATH = env.str("GDAL_LIBRARY_PATH", default=None)
if GDAL_LIBRARY_PATH is None:
    del GDAL_LIBRARY_PATH
GEOS_LIBRARY_PATH = env.str("GEOS_LIBRARY_PATH", default=None)
if GEOS_LIBRARY_PATH is None:
    del GEOS_LIBRARY_PATH

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    "django_tailwind_cli",
    "parler",
    "apps.core",
    "apps.accounts",
    "apps.consents",
    "apps.geo",
    "apps.catalog",
    "apps.search",
    "apps.demo",
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
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": database_from_env("postgis://kamqor:kamqor@localhost:5433/kamqor"),
}

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGES = [("ru", "Русский"), ("kk", "Қазақша")]
LANGUAGE_CODE = "ru"
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
FORMAT_MODULE_PATH = ["config.formats"]
USE_TZ = True

PARLER_LANGUAGES = {
    None: ({"code": "ru"}, {"code": "kk"}),
    "default": {"fallbacks": ["ru"], "hide_untranslated": False},
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
TAILWIND_CLI_SRC_CSS = "static/src/css/input.css"
TAILWIND_CLI_VERSION = "4.3.5"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

SEARCH_TRIGRAM_MIN = 0.3
SEARCH_PAGE_SIZE = 20
GEOJSON_MAX_FEATURES = 2000
OTP_TTL_MIN = 5
OTP_MAX_ATTEMPTS = 5
