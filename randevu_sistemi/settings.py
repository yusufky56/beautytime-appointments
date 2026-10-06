# randevu_sistemi/settings.py
import os
from pathlib import Path

# Build paths inside the project.
BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('1', 'true', 'yes')


# Secrets and environment-specific values come from environment variables.
# The defaults are for local development only.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-insecure-key-do-not-use-in-production')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Local apps
    'appointments.apps.AppointmentsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'randevu_sistemi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Custom context processors
                'appointments.context_processors.business_info',
                'appointments.context_processors.notification_count',
                'appointments.context_processors.site_statistics',
                'appointments.context_processors.user_preferences',
                'appointments.context_processors.app_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'randevu_sistemi.wsgi.application'

# Database: SQLite by default, SQL Server when DB_ENGINE=mssql
if os.environ.get('DB_ENGINE') == 'mssql':
    DATABASES = {
        'default': {
            'ENGINE': 'mssql',
            'NAME': os.environ.get('DB_NAME', 'OnlineRandevuDB'),
            'HOST': os.environ.get('DB_HOST', r'localhost\SQLEXPRESS'),
            'PORT': os.environ.get('DB_PORT', ''),
            'USER': os.environ.get('DB_USER', ''),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'OPTIONS': {
                'driver': os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
                'extra_params': 'TrustServerCertificate=yes',
                'host_is_server': True,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation - Development için basitleştirilmiş
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
]

# Form field error messages
from django.forms import Field
Field.default_error_messages = {
    'required': 'Bu alan zorunludur.',
}

# Internationalization
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'appointments' / 'static',  # Uygulamanın static dosyaları
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Email (Development - Console backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@beautytime.com'
CONTACT_EMAIL = 'info@beautytime.com'

# Business Settings
BUSINESS_SETTINGS = {
    'NAME': 'BeautyTime',
    'PHONE': '+90 (555) 123 45 67',
    'EMAIL': 'info@beautytime.com',
    'ADDRESS': 'İstanbul, Türkiye',
    'WORKING_HOURS': {
        'weekdays': '09:00 - 18:00',
        'saturday': '10:00 - 16:00',
        'sunday': 'Kapalı'
    },
    'SOCIAL_MEDIA': {
        'facebook': 'https://facebook.com/beautytime',
        'instagram': 'https://instagram.com/beautytime',
        'twitter': 'https://twitter.com/beautytime',
    }
}

# Site URL (for absolute URLs in emails)
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')

# Security
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'appointments': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Messages
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}