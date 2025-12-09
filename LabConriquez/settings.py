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
    'jazzmin',  # Sirve para mejorar el apartado de administración

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
# BASE DE DATOS
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
# STATIC FILES (WHITENOISE)
# ======================================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# ❌ ESTO YA NO DEBE IR (Forma antigua):
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ======================================================================
# MEDIA (CLOUDINARY)
# ======================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

# ❌ ESTO YA NO DEBE IR (Forma antigua que causa el error):
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ======================================================================
# ✅ CONFIGURACIÓN NUEVA (ESTO SOLUCIONA TU PROBLEMA)
# ======================================================================

STORAGES = {
    # 1. Media (Tus imágenes) -> SE VAN A CLOUDINARY
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    # 2. Static (CSS, JS) -> SE QUEDAN EN RENDER CON WHITENOISE
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ======================================================================
# OTROS
# ======================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ======================================================================
# CONFIGURACION DE DISEÑO DE JAZZMIN
# settings.py (Al final del archivo)

JAZZMIN_SETTINGS = {
    # Títulos y Bienvenida
    "site_title": "Lab Conriquez",
    "site_header": "Sistema de Laboratorio",
    "site_brand": "Lab Conriquez",
    "welcome_sign": "Bienvenido al Panel de Control",
    "copyright": "Lab Conriquez Software",
    
    # Logo (Pon tu archivo en carpeta static/img)
    # "site_logo": "img/logo.png", 
    
    # Menú Lateral
    "search_model": ["LabApp.Paciente", "LabApp.Analisis"], # Buscador global

    # Iconos para tus modelos (Usa FontAwesome 5)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        
        # TUS MODELOS (Ajusta los nombres de la app si es necesario)
        "LabApp.Paciente": "fas fa-user-injured",
        "LabApp.Analisis": "fas fa-microscope",
        "LabApp.Plantilla": "fas fa-file-medical-alt",
        "LabApp.Laboratorio": "fas fa-clinic-medical",
        "LabApp.Pago": "fas fa-money-bill-wave",
        "LabApp.Reporte": "fas fa-file-pdf",
    },
    
    # Orden del menú lateral
    "order_with_respect_to": ["LabApp", "auth"],

    # Opciones de interfaz
    "show_ui_builder": True,  # <--- IMPORTANTE: Poner en False cuando termines de elegir colores
}

# Ajustes visuales (Tema médico/azul)
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-info",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "theme": "flatly", # Temas disponibles: cerulean, cosmo, flatly, journal, litera, lumen, lux, materia, minty, pulse, sandstone, simplex, sketchy, slate, solar, spacelab, superhero, united, yeti
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}