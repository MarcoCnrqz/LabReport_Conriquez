# 1. Usamos una imagen base de Python ligera (Slim)
FROM python:3.11-slim

# 2. Evita que Python genere archivos .pyc y permite ver los logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalamos dependencias del sistema necesarias para PostgreSQL (psycopg2) y Pillow (Imágenes)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiamos los requerimientos primero (para aprovechar el caché de Docker)
COPY requirements.txt .

# 6. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copiamos el resto del código del proyecto
COPY . .

# 8. Recolectamos los archivos estáticos (CSS del admin) para que Whitenoise los sirva
# Usamos una clave secreta dummy solo para este paso de construcción
RUN SECRET_KEY=dummy python manage.py collectstatic --noinput

# 9. Comando para iniciar el servidor de producción (Gunicorn)
# IMPORTANTE: Asegúrate que 'LabConriquez' sea el nombre de la carpeta donde está wsgi.py
CMD sh -c "python manage.py migrate --noinput && python manage.py shell -c \"from django.contrib.auth import get_user_model; import os; User=get_user_model(); u=os.environ.get('DJANGO_SUPERUSER_USERNAME'); p=os.environ.get('DJANGO_SUPERUSER_PASSWORD'); e=os.environ.get('DJANGO_SUPERUSER_EMAIL'); print('Creando superusuario...' if not User.objects.filter(username=u).exists() else 'Superusuario ya existe'); User.objects.create_superuser(u, e, p) if (u and p and not User.objects.filter(username=u).exists()) else None\" && gunicorn LabConriquez.wsgi:application --bind 0.0.0.0:$PORT"