from django.contrib import admin
from django.urls import path, include
from django.conf import settings 
from django.conf.urls.static import static 
from rest_framework.routers import DefaultRouter

# --- IMPORTACIONES PARA ARREGLAR EL ERROR 405 (LOGOUT) ---
from django.contrib.auth import logout
from django.shortcuts import redirect

# Importamos las vistas desde la app
from LabApp import views

# ======================================================
# 1. FUNCIÓN FIX PARA LOGOUT (DJANGO 5)
# ======================================================
def logout_fix(request):
    """
    Fuerza el cierre de sesión mediante GET y redirige al admin,
    evitando el error 405 en Django 5.0+
    """
    logout(request)
    return redirect('/admin/') 

# ======================================================
# 2. CONFIGURACIÓN DEL ROUTER (API REST)
# ======================================================
router = DefaultRouter()
router.register(r'pacientes', views.PacienteViewSet)
router.register(r'laboratorios', views.LaboratorioViewSet)
router.register(r'analisis', views.AnalisisViewSet)

# 🌟 REGISTRO DE PLANTILLAS Y SUS DEPENDENCIAS
router.register(r'plantillas', views.PlantillaViewSet) 
router.register(r'propiedades_plantilla', views.PropiedadPlantillaViewSet)
router.register(r'intervalos_referencia', views.IntervaloReferenciaViewSet)

# ======================================================
# 3. PATRONES DE URL
# ======================================================
urlpatterns = [
    # --- Fix del Logout (Debe ir antes de admin/) ---
    path('admin/logout/', logout_fix, name='logout_fix'),

    # --- Rutas de Admin ---
    path('admin/', admin.site.urls),
    
    # --- ⚠️ CORRECCIÓN APLICADA AQUÍ ⚠️ ---
    # Se renombró name="home" a name="inicio" para solucionar el error NoReverseMatch
    path('', views.inicio, name="inicio"), 
    
    # (Opcional) Ruta legacy por si algún enlace viejo la usa
    path("LabConriquezMex/", views.inicio, name="inicio_legacy"),
    
    # --- Rutas de la API ---
    path('api/', include(router.urls)),
    
    # --- Endpoints Personalizados ---
    path('api/login/', views.login_api, name='api_login'),
    path('api/mi_laboratorio/', views.mi_laboratorio_api, name='mi_laboratorio_api'),
]

# ======================================================
# 4. CONFIGURACIÓN DE MEDIA (SUBIDA DE IMÁGENES)
# ======================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)