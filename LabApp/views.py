from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render, redirect
from django.contrib.auth import logout

# ======================================================
# IMPORTACIONES DE MODELOS Y SERIALIZERS
# ======================================================
from .models import (
    Paciente, Laboratorio, Analisis, Usuario, 
    Plantilla, PropiedadPlantilla, IntervaloReferencia
)

from .serializers import (
    PacienteSerializer, LaboratorioSerializer, AnalisisSerializer,
    PlantillaSerializer, PropiedadPlantillaSerializer, IntervaloReferenciaSerializer
)

# ======================================================
# VISTA DE INICIO (WEB)
# ======================================================
def inicio(request):
    """Vista para la página de inicio (Landing Page o Login Web)."""
    return render(request, "inicio.html")

# ======================================================
# API VIEWSETS (CRUD AUTOMÁTICO)
# ======================================================

class LaboratorioViewSet(viewsets.ModelViewSet):
    queryset = Laboratorio.objects.all()
    serializer_class = LaboratorioSerializer

class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer

class AnalisisViewSet(viewsets.ModelViewSet):
    """
    CRUD de Análisis.
    ✅ OPTIMIZACIÓN: 'prefetch_related' carga los resultados junto con el análisis.
    Esto acelera drásticamente la descarga del historial a la app de escritorio.
    """
    queryset = Analisis.objects.prefetch_related('resultados').all()
    serializer_class = AnalisisSerializer

class PlantillaViewSet(viewsets.ModelViewSet):
    """
    CRUD de Plantillas.
    ✅ OPTIMIZACIÓN: 'prefetch_related' carga todo el árbol (propiedades e intervalos).
    Indispensable para que la Sincronización Profunda funcione rápido.
    """
    queryset = Plantilla.objects.prefetch_related(
        'propiedades', 
        'propiedades__intervalos'
    ).all()
    serializer_class = PlantillaSerializer

class PropiedadPlantillaViewSet(viewsets.ModelViewSet):
    queryset = PropiedadPlantilla.objects.all()
    serializer_class = PropiedadPlantillaSerializer

class IntervaloReferenciaViewSet(viewsets.ModelViewSet):
    queryset = IntervaloReferencia.objects.all()
    serializer_class = IntervaloReferenciaSerializer

# ======================================================
# ENDPOINTS PERSONALIZADOS (LOGIN Y EXTRAS)
# ======================================================

@api_view(['POST'])
def login_api(request):
    """
    Valida credenciales de usuario manualmente.
    Recibe: { "correo": "...", "password": "..." }
    """
    correo = request.data.get('correo')
    password = request.data.get('password')

    if not correo or not password:
        return Response({'error': 'Faltan datos'}, status=400)

    try:
        usuario = Usuario.objects.get(correo_electronico=correo)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=404)

    if usuario.check_password(password):
        if usuario.is_active:
            return Response({
                'valid': True,
                'id': usuario.id,
                'nombre': usuario.nombre,
                'correo': usuario.correo_electronico,
            }, status=200)
        else:
            return Response({'error': 'Usuario inactivo'}, status=403)
    else:
        return Response({'error': 'Contraseña incorrecta'}, status=401)

@api_view(['GET'])
def mi_laboratorio_api(request):
    """
    Devuelve la información y el logo del laboratorio asociado al usuario.
    Uso: GET /api/mi_laboratorio/?usuario_id=1
    """
    usuario_id = request.query_params.get('usuario_id')
    if not usuario_id:
        return Response({'error': 'Falta usuario_id'}, status=400)

    try:
        usuario = Usuario.objects.get(id=usuario_id)
        # Asumimos que el usuario puede tener varios, tomamos el primero
        laboratorio = usuario.laboratorios.first() 
        
        if not laboratorio:
             return Response({'error': 'Usuario sin laboratorio'}, status=404)

        # Construir URL absoluta para la imagen (logo)
        logo_url = None
        if laboratorio.logo:
            logo_url = request.build_absolute_uri(laboratorio.logo.url)

        return Response({
            'id': laboratorio.id,
            'nombre': laboratorio.nombre_laboratorio,
            'logo_url': logo_url
        })

    except Usuario.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=404)