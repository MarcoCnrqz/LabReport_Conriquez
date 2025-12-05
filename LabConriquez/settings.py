# settings.py

from pathlib import Path
import os
import dj_database_url  # Librería para conectar a la BD de Render

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# CONFIGURACIÓN DE SEGURIDAD Y ENTORNO
# ==============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
# En Render, leerá la variable SECRET_KEY. 
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-o^-c3$bfs+wt)dvk$y#5gq8(tigycm#()iq6^hz_uercc+y9+b')


# --- CONFIGURACIÓN PARA PRODUCCIÓN (RENDER) ---

# 💡 CORRECCIÓN 1: DEBUG es False por defecto en producción si la variable no existe.
DEBUG = os.environ.get('DJANGO_DEBUG') == 'True' 

# 💡 CORRECCIÓN 2: Lee los hosts permitidos (e.g., icelaboratorio.com, labconriquez.onrender.com).
# El valor por defecto '*' es solo para desarrollo local.
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ==============================================================================
# AJUSTES DE SEGURIDAD ADICIONALES PARA HTTPS/PRODUCCIÓN
# ==============================================================================

# 💡 CORRECCIÓN 3: Configuración para asegurar cookies en HTTPS (Necesario en Render).
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False') == 'True'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'False') == 'True'

# Solo permite que las cookies de sesión se accedan a través de HTTP (no JavaScript), mayor seguridad.
SESSION_COOKIE_HTTPONLY = True


CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS', 
    'http://127.0.0.1,https://icelaboratorio.com,https://www.icelaboratorio.com,https://labconriquezsw-v0dy.onrender.com'
).split(',')

# ==============================================================================
# APLICACIONES INSTALADAS
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # Django REST Framework
    'LabApp',  
]

# ==============================================================================
# MIDDLEWARE (Intermediarios de procesamiento)
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Whitenoise debe ir justo después de SecurityMiddleware para servir estáticos en la nube
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'LabConriquez.urls'

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


# ==============================================================================
# BASE DE DATOS (Híbrida: SQLite Local / PostgreSQL Render)
# ==============================================================================

DATABASES = {
    'default': dj_database_url.config(
        # Si no hay variable DATABASE_URL (estás en local), usa SQLite
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}


# ==============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==============================================================================
# INTERNACIONALIZACIÓN (Idioma y Hora)
# ==============================================================================

LANGUAGE_CODE = 'es-mx'  # Cambiado a Español México

TIME_ZONE = 'America/Mexico_City'  # Cambiado a zona horaria central

USE_I18N = True

USE_TZ = True


# ==============================================================================
# ARCHIVOS ESTÁTICOS (CSS, JS, Imágenes del sistema)
# ==============================================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Carpeta donde Whitenoise/Render buscarán los archivos estáticos listos para producción
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# 💡 CORRECCIÓN 5: Motor de almacenamiento optimizado de Whitenoise (Confirmado)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==============================================================================
# ARCHIVOS MEDIA (Imágenes subidas por usuarios/logos)
# ==============================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==============================================================================
# OTROS AJUSTES
# ==============================================================================

# Tipo de campo para claves primarias
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'