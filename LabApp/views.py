import requests as http_requests

from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse, JsonResponse
from django.views.decorators.http import require_GET
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
# 🔹 HELPER: Descarga imagen desde URL (Cloudinary)
# ======================================================

def _descargar_imagen_bytes(field):
    if not field:
        return None
    try:
        url = field.url
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"Error descargando imagen desde {getattr(field, 'name', '?')}: {e}")
        return None


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
    paciente    = analisis.paciente
    laboratorio = paciente.laboratorio if hasattr(paciente, 'laboratorio') else None
    quimico     = analisis.creado_por

    logo_bytes  = _descargar_imagen_bytes(laboratorio.logo if laboratorio else None)
    firma_bytes = _descargar_imagen_bytes(quimico.firma_digital if quimico else None)

    imagen_bytes1 = None
    imagen_bytes2 = None
    if analisis.plantilla and analisis.plantilla.tipo_formato == 'IMAGENES_RESULTADOS':
        imagen_bytes1 = _descargar_imagen_bytes(analisis.imagen_resultado1)
        imagen_bytes2 = _descargar_imagen_bytes(analisis.imagen_resultado2)

    resultados = []
    edad_meses = paciente.edad_en_meses

    for res in analisis.resultados.all():
        valor_min = None
        valor_max = None
        propiedad = None
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
            "nombre_propiedad":      res.nombre_propiedad,
            "valor":                 res.valor,
            "unidad":                res.unidad,
            "valor_min":             valor_min,
            "valor_max":             valor_max,
            # CORRECCIÓN: pasar las opciones cualitativas al PDF
            "opciones_cualitativas": propiedad.opciones_cualitativas if propiedad else "",
        })

    return {
        "paciente":               paciente.nombre_completo,
        "edad":                   paciente.edad,
        "sexo":                   paciente.sexo,
        "tipo":                   analisis.plantilla.titulo,
        "tipo_formato_raw":       analisis.plantilla.tipo_formato,
        "fecha_muestra":          analisis.fecha_analisis,
        "fecha_analisis":         analisis.fecha_analisis,
        "resultados":             resultados,
        "laboratorio_nombre":     laboratorio.nombre_laboratorio if laboratorio else "",
        "laboratorio_logo":       logo_bytes,
        "imagen_blob1":           imagen_bytes1,
        "imagen_blob2":           imagen_bytes2,
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


# ======================================================
# 🔹 ADMIN EXT — Tipo de formato de plantilla (para JS del admin)
# ======================================================

@require_GET
def plantilla_tipo_formato(request, plantilla_id):
    try:
        plantilla = Plantilla.objects.only('tipo_formato').get(pk=plantilla_id)
        return JsonResponse({'tipo_formato': plantilla.tipo_formato})
    except Plantilla.DoesNotExist:
        return JsonResponse({'tipo_formato': None}, status=404)


@require_GET
def plantilla_propiedades(request, plantilla_id):
    """
    Devuelve las propiedades de una plantilla en JSON.
    Incluye 'tipo' y 'opciones_cualitativas' para que el JS del admin
    pueda renderizar correctamente el <select> de opciones y el N/A de unidad.
    """
    try:
        plantilla = Plantilla.objects.get(pk=plantilla_id)
    except Plantilla.DoesNotExist:
        return JsonResponse({'propiedades': []}, status=404)

    paciente_id = request.GET.get('paciente_id')
    paciente    = None

    if paciente_id:
        try:
            paciente = Paciente.objects.get(pk=paciente_id)
        except Paciente.DoesNotExist:
            paciente = None

    propiedades_qs = plantilla.propiedades.all()
    resultado = []

    for prop in propiedades_qs:
        if paciente:
            edad_meses = paciente.edad_en_meses

            intervalo = prop.intervalos.filter(
                Q(sexo=paciente.sexo) | Q(sexo='AMBOS')
            ).filter(
                Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
            ).filter(
                Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
            ).first()

            if prop.intervalos.exists() and not intervalo:
                continue

            resultado.append({
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             intervalo.valor_min if intervalo else None,
                'valor_max':             intervalo.valor_max if intervalo else None,
            })
        else:
            resultado.append({
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             None,
                'valor_max':             None,
            })

    return JsonResponse({'propiedades': resultado})
