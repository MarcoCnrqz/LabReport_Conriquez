# settings.py

from pathlib import Path
import os
import dj_database_url

# ========== CLOUDINARY ==========
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ======================================================================
# BASE
# ======================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================================================
# SEGURIDAD
# ======================================================================

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-o^-c3$bfs+wt)dvk$y#5gq8(tigycm#()iq6^hz_uercc+y9+b'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    '127.0.0.1,localhost,labconriquezsw-v0dy.onrender.com,icelaboratorio.com,www.icelaboratorio.com'
).split(',')

# ======================================================================
# SEGURIDAD HTTPS (RENDER)
# ======================================================================

SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False') == 'True'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'False') == 'True'

SESSION_COOKIE_HTTPONLY = True

CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://127.0.0.1,https://icelaboratorio.com,https://www.icelaboratorio.com,https://labconriquezsw-v0dy.onrender.com'
).split(',')

# ======================================================================
# APLICACIONES
# ======================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # TERCEROS
    'rest_framework',
    'cloudinary',
    'cloudinary_storage',

    # TUS APPS
    'LabApp',
]

# ======================================================================
# MIDDLEWARE
# ======================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # STATIC en Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'LabConriquez.urls'

# ======================================================================
# TEMPLATES
# ======================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'LabConriquez.wsgi.application'

# ======================================================================
# BASE DE DATOS (SQLITE LOCAL / POSTGRES RENDER)
# ======================================================================

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}

# ======================================================================
# VALIDACIÓN DE PASSWORDS
# ======================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# ======================================================================
# INTERNACIONALIZACIÓN
# ======================================================================

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'

USE_I18N = True
USE_TZ = True

# ======================================================================
# STATIC FILES (WHITENOISE + RENDER)
# ======================================================================

STATIC_URL = '/static/'

STATICFILES_DIRS = [BASE_DIR / 'static']

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ======================================================================
# MEDIA (CLOUDINARY EN PRODUCCIÓN)
# ⚠️ EN RENDER SE USA CLOUDINARY, NO ESTE DISCO
# ======================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Solo útil EN LOCAL

# ======================================================================
# CLOUDINARY CONFIGURACIÓN
# ======================================================================

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ======================================================================
# OTROS
# ======================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
