
from pathlib import Path
import os
import dj_database_url  # Librería para conectar a la BD de Render

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# CONFIGURACIÓN DE SEGURIDAD Y ENTORNO
# ==============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
# En Render, leerá la variable SECRET_KEY. En local, usa la clave insegura por defecto.
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-o^-c3$bfs+wt)dvk$y#5gq8(tigycm#()iq6^hz_uercc+y9+b')


# --- CONFIGURACIÓN PARA DOCKER/PRODUCCIÓN (CORREGIDO) ---
# Lee la configuración de DEBUG de una variable de entorno, por defecto True para desarrollo
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True' 

# Lee los hosts permitidos de una variable de entorno, por defecto '*' para desarrollo local
# Cuando uses Heroku/AWS, esta variable se debe establecer allí.
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')
# --------------------------------------------------------


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

# Motor de almacenamiento optimizado de Whitenoise
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