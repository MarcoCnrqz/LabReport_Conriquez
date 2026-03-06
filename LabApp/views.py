from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q

from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PropiedadPlantilla, IntervaloReferencia, Usuario, Reporte
)
from .serializers import (
    PacienteSerializer, LaboratorioSerializer, AnalisisSerializer,
    PlantillaSerializer, PropiedadPlantillaSerializer,
    IntervaloReferenciaSerializer, UsuarioSerializer, ReporteSerializer
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

class ReporteViewSet(viewsets.ModelViewSet):
    queryset = Reporte.objects.all()
    serializer_class = ReporteSerializer

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
# 🔹 PDF ADMIN
# ======================================================

def generar_pdf_admin(request, analisis_id):
    analisis = get_object_or_404(Analisis, id=analisis_id)
    paciente = analisis.paciente
    laboratorio = paciente.laboratorio if hasattr(paciente, 'laboratorio') else None
    quimico = analisis.creado_por

    # Logo en bytes
    logo_bytes = None
    if laboratorio and laboratorio.logo:
        try:
            with laboratorio.logo.open("rb") as f:
                logo_bytes = f.read()
        except Exception:
            logo_bytes = None

    # Firma en bytes (Nuevo)
    firma_bytes = None
    if quimico and quimico.firma_digital:
        try:
            with quimico.firma_digital.open("rb") as f:
                firma_bytes = f.read()
        except Exception:
            firma_bytes = None

    # Resultados con lógica de búsqueda de intervalos
    resultados = []
    edad = paciente.edad
    grupo_edad = "NINO" if edad <= 18 else "ADULTO" if edad <= 59 else "ADULTO_MAYOR"

    for res in analisis.resultados.all():
        valor_min = None
        valor_max = None
        try:
            propiedad = analisis.plantilla.propiedades.filter(nombre_propiedad=res.nombre_propiedad).first()
            if propiedad:
                # Búsqueda precisa por grupo de edad y sexo
                intervalo = propiedad.intervalos.filter(
                    Q(grupo_edad=grupo_edad) & (Q(sexo=paciente.sexo) | Q(sexo="AMBOS"))
                ).first()
                if intervalo:
                    valor_min = intervalo.valor_min
                    valor_max = intervalo.valor_max
        except Exception:
            pass

        resultados.append({
            "nombre_propiedad": res.nombre_propiedad,
            "valor": res.valor,
            "unidad": res.unidad,
            "valor_min": valor_min,
            "valor_max": valor_max
        })

    detalles = {
        "paciente": paciente.nombre_completo, # Usa la property de nombre + apellidos
        "edad": paciente.edad,
        "sexo": paciente.sexo,
        "usuario_generador": quimico.nombre if quimico else "",
        "quimico_puesto": quimico.puesto if quimico else "",
        "quimico_titulo": quimico.titulo_abreviado if quimico else "",
        "quimico_cedula": quimico.cedula_profesional if quimico else "",
        "quimico_ssg": quimico.registro_ssg if quimico else "",
        "quimico_firma_bytes": firma_bytes,
        "fecha_muestra": analisis.fecha_analisis,
        "fecha_analisis": analisis.fecha_analisis,
        "tipo": analisis.plantilla.titulo,
        "tipo_formato_raw": analisis.plantilla.tipo_formato,
        "laboratorio_logo": logo_bytes,
        "resultados": resultados,
        "imagen_blob1": None,
        "imagen_blob2": None,
    }

    return generar_pdf_reporte(detalles)

