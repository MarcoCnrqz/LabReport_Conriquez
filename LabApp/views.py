from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.db.models import Q

from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PropiedadPlantilla, IntervaloReferencia, Usuario
)
from .serializers import (
    PacienteSerializer, LaboratorioSerializer, AnalisisSerializer,
    PlantillaSerializer, PropiedadPlantillaSerializer,
    IntervaloReferenciaSerializer, UsuarioSerializer
)
from .utils.imprimir_pdf import generar_pdf_reporte

# ======================================================
# 🔹 API VIEWSETS
# ======================================================

class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer

class LaboratorioViewSet(viewsets.ModelViewSet):
    queryset = Laboratorio.objects.all()
    serializer_class = LaboratorioSerializer

class AnalisisViewSet(viewsets.ModelViewSet):
    queryset = Analisis.objects.all()
    serializer_class = AnalisisSerializer

class PlantillaViewSet(viewsets.ModelViewSet):
    queryset = Plantilla.objects.all()
    serializer_class = PlantillaSerializer

class PropiedadPlantillaViewSet(viewsets.ModelViewSet):
    queryset = PropiedadPlantilla.objects.all()
    serializer_class = PropiedadPlantillaSerializer

class IntervaloReferenciaViewSet(viewsets.ModelViewSet):
    queryset = IntervaloReferencia.objects.all()
    serializer_class = IntervaloReferenciaSerializer

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

# ======================================================
# 🔹 VISTAS GENERALES
# ======================================================

def inicio(request):
    return render(request, 'inicio.html', {})

@api_view(['POST'])
def login_api(request):
    return Response({"ok": True})

@api_view(['GET'])
def mi_laboratorio_api(request):
    return Response({"laboratorio": "demo"})

def logout_fix(request):
    from django.contrib.auth import logout
    logout(request)
    return render(request, 'admin/login.html', {})

# ======================================================
# 🔹 PDF — FUNCIÓN AUXILIAR
# ======================================================

def _construir_detalles_analisis(analisis):
    """
    Extrae todos los datos del análisis y los convierte en el
    diccionario que espera generar_pdf_reporte.
    """
    paciente    = analisis.paciente
    laboratorio = paciente.laboratorio if hasattr(paciente, 'laboratorio') else None
    quimico     = analisis.creado_por

    # --- Logo del laboratorio ---
    logo_bytes = None
    if laboratorio and laboratorio.logo:
        try:
            with laboratorio.logo.open("rb") as f:
                logo_bytes = f.read()
        except Exception:
            logo_bytes = None

    # --- Firma digital del químico ---
    firma_bytes = None
    if quimico and quimico.firma_digital:
        try:
            with quimico.firma_digital.open("rb") as f:
                firma_bytes = f.read()
        except Exception:
            firma_bytes = None

    # --- Imágenes del análisis (solo para IMAGENES_RESULTADOS) ---
    imagen_bytes1 = None
    imagen_bytes2 = None
    if analisis.plantilla and analisis.plantilla.tipo_formato == 'IMAGENES_RESULTADOS':
        if analisis.imagen_resultado1:
            try:
                with analisis.imagen_resultado1.open("rb") as f:
                    imagen_bytes1 = f.read()
            except Exception:
                imagen_bytes1 = None
        if analisis.imagen_resultado2:
            try:
                with analisis.imagen_resultado2.open("rb") as f:
                    imagen_bytes2 = f.read()
            except Exception:
                imagen_bytes2 = None

    # --- Resultados con intervalos de referencia por edad y sexo ---
    resultados  = []
    edad_meses  = paciente.edad_en_meses

    for res in analisis.resultados.all():
        valor_min = None
        valor_max = None
        try:
            propiedad = analisis.plantilla.propiedades.filter(
                nombre_propiedad=res.nombre_propiedad
            ).first()

            if propiedad:
                intervalo = propiedad.intervalos.filter(
                    Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
                ).filter(
                    Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
                ).filter(
                    Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
                ).first()

                if intervalo:
                    valor_min = intervalo.valor_min
                    valor_max = intervalo.valor_max
        except Exception:
            pass

        resultados.append({
            "nombre_propiedad": res.nombre_propiedad,
            "valor":            res.valor,
            "unidad":           res.unidad,
            "valor_min":        valor_min,
            "valor_max":        valor_max,
        })

    # --- Diccionario completo para el PDF ---
    return {
        # Paciente
        "paciente":               paciente.nombre_completo,
        "edad":                   paciente.edad,
        "sexo":                   paciente.sexo,

        # Análisis
        "tipo":                   analisis.plantilla.titulo,
        "tipo_formato_raw":       analisis.plantilla.tipo_formato,
        "fecha_muestra":          analisis.fecha_analisis,
        "fecha_analisis":         analisis.fecha_analisis,
        "resultados":             resultados,

        # Laboratorio
        "laboratorio_logo":       logo_bytes,

        # Imágenes (formato especial)
        "imagen_blob1":           imagen_bytes1,
        "imagen_blob2":           imagen_bytes2,

        # Químico / Responsable sanitario — TODOS los campos
        "usuario_generador":           quimico.nombre               if quimico else "",
        "quimico_puesto":              quimico.puesto               if quimico else "",
        "quimico_titulo":              quimico.titulo_abreviado      if quimico else "",
        "quimico_cedula":              quimico.cedula_profesional    if quimico else "",
        "quimico_cedula_especialidad": quimico.cedula_especialidad   if quimico else "",
        "quimico_ssg":                 quimico.registro_ssg          if quimico else "",
        "quimico_universidad":         quimico.universidad_egreso    if quimico else "",
        "quimico_firma_bytes":         firma_bytes,
    }


# ======================================================
# 🔹 PDF — VISTAS
# ======================================================

def generar_pdf_admin(request, analisis_id):
    """Vista legacy — mantiene compatibilidad con enlaces anteriores."""
    analisis     = get_object_or_404(Analisis, id=analisis_id)
    detalles     = _construir_detalles_analisis(analisis)
    archivo_path = generar_pdf_reporte(detalles)

    return FileResponse(
        open(archivo_path, 'rb'),
        content_type='application/pdf',
        filename=f"analisis_{analisis_id}.pdf"
    )


def generar_pdf_analisis(request, pk):
    """Vista principal — responde a admin_ext/analisis/<pk>/generar_pdf/"""
    analisis     = get_object_or_404(Analisis, pk=pk)
    detalles     = _construir_detalles_analisis(analisis)
    archivo_path = generar_pdf_reporte(detalles)

    return FileResponse(
        open(archivo_path, 'rb'),
        content_type='application/pdf',
        filename=f"analisis_{pk}.pdf"
    )