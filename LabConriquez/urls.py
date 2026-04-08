from django.contrib import admin
from django.urls import path, include
from django.conf import settings 
from django.conf.urls.static import static 
from rest_framework.routers import DefaultRouter

from django.contrib.auth import logout
from django.shortcuts import redirect
from LabApp import views


# ======================================================
# 1. FUNCIÓN FIX PARA LOGOUT (DJANGO 5)
# ======================================================
def logout_fix(request):
    logout(request)
    return redirect('/admin/')


# ======================================================
# 2. CONFIGURACIÓN DEL ROUTER (API REST)
# ======================================================
router = DefaultRouter()

router.register(r'pacientes', views.PacienteViewSet)
router.register(r'laboratorios', views.LaboratorioViewSet)
router.register(r'analisis', views.AnalisisViewSet)
router.register(r'plantillas', views.PlantillaViewSet)

# 🔥 FIX CRÍTICO: agregar propiedades
router.register(r'propiedades', views.PropiedadViewSet)

router.register(r'intervalos_referencia', views.IntervaloReferenciaViewSet)

# Resultados individuales — permite PATCH /api/resultados/<id>/ desde la app local
router.register(r'resultados', views.ResultadoAnalisisViewSet, basename='resultados')


# ======================================================
# 3. PATRONES DE URL
# ======================================================
urlpatterns = [
    # --- Admin ---
    path('admin/logout/', logout_fix, name='logout_fix'),
    path('admin/', admin.site.urls),

    # --- Inicio ---
    path('', views.inicio, name="inicio"),
    path("LabConriquezMex/", views.inicio, name="inicio_legacy"),

    # --- API REST ---
    path('api/', include(router.urls)),
    path('api/login/', views.login_api, name='api_login'),
    path('api/mi_laboratorio/', views.mi_laboratorio_api, name='mi_laboratorio_api'),

    # --- Funciones extendidas ---
    path(
        'admin_ext/analisis/<int:pk>/generar_pdf/',
        views.generar_pdf_analisis,
        name='generar_pdf_analisis'
    ),
    path(
        'admin_ext/plantilla/<int:plantilla_id>/tipo_formato/',
        views.plantilla_tipo_formato,
        name='plantilla_tipo_formato'
    ),
    path(
        'admin_ext/plantilla/<int:plantilla_id>/propiedades/',
        views.plantilla_propiedades,
        name='plantilla_propiedades'
    ),
    path(
        'admin_ext/propiedades_disponibles/',
        views.propiedades_disponibles,
        name='propiedades_disponibles'
    ),
]


# ======================================================
# 4. CONFIGURACIÓN DE MEDIA (solo en desarrollo)
# ======================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)