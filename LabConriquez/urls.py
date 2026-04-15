from django.contrib import admin
from django.urls import path, include
from django.conf import settings 
from django.conf.urls.static import static 
from rest_framework.routers import DefaultRouter

from django.contrib.auth import logout
from django.shortcuts import redirect

from LabApp import views


# ======================================================
# 1. FIX LOGOUT (DJANGO 5)
# ======================================================
def logout_fix(request):
    logout(request)
    return redirect('/admin/')


# ======================================================
# 2. ROUTER API REST (CORREGIDO)
# ======================================================
router = DefaultRouter()

# --- ENTIDADES PRINCIPALES ---
router.register(r'plantillas', views.PlantillaViewSet, basename='plantillas')
router.register(r'propiedades', views.PropiedadViewSet, basename='propiedades')  # ✔️ FIX CRÍTICO

router.register(r'laboratorios', views.LaboratorioViewSet, basename='laboratorios')
router.register(r'pacientes', views.PacienteViewSet, basename='pacientes')
router.register(r'analisis', views.AnalisisViewSet, basename='analisis')
router.register(r'resultados', views.ResultadoAnalisisViewSet, basename='resultados')

# --- RELACIONES (MUCHOS A MUCHOS) ---
router.register(
    r'plantilla-propiedades',
    views.PropiedadPlantillaViewSet,
    basename='plantilla-propiedades'
)

# --- CONFIGURACIONES / APOYO ---
router.register(
    r'intervalos_referencia',
    views.IntervaloReferenciaViewSet,
    basename='intervalos_referencia'
)

# (Opcional pero recomendado si tienes usuarios vía API)
if hasattr(views, 'UsuarioViewSet'):
    router.register(r'usuarios', views.UsuarioViewSet, basename='usuarios')


# ======================================================
# 3. URLS PRINCIPALES
# ======================================================
urlpatterns = [
    # --- ADMIN ---
    path('admin/logout/', logout_fix, name='logout_fix'),
    path('admin/', admin.site.urls),

    # --- INICIO ---
    path('', views.inicio, name="inicio"),
    path("LabConriquezMex/", views.inicio, name="inicio_legacy"),

    # --- API REST ---
    path('api/', include(router.urls)),

    # --- AUTH API ---
    path('api/login/', views.login_api, name='api_login'),
    path('api/token/refresh/', views.refresh_token_api, name='api_token_refresh'),
    path('api/mi_laboratorio/', views.mi_laboratorio_api, name='mi_laboratorio_api'),

    # ==================================================
    # 4. FUNCIONES EXTENDIDAS (ADMIN PERSONALIZADO)
    # ==================================================
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
# 5. MEDIA (SOLO DESARROLLO)
# ======================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)