import requests as http_requests
 
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
 
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, Propiedad, IntervaloReferencia, Usuario
)
from .serializers import (
    PacienteSerializer, LaboratorioSerializer, AnalisisSerializer,
    PlantillaSerializer, IntervaloReferenciaSerializer, UsuarioSerializer,
    LoginSerializer, UsuarioLoginResponseSerializer,
    MiLaboratorioResponseSerializer,
    PacienteBusquedaNubeSerializer,
)
from .utils.imprimir_pdf import generar_pdf_reporte
 
 
# ======================================================
# HELPER: Descarga imagen desde URL (Cloudinary)
# ======================================================
 
def _descargar_imagen_bytes(field):
    if not field:
        return None
    try:
        url  = field.url
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"Error descargando imagen desde {getattr(field, 'name', '?')}: {e}")
        return None
 
 
# ======================================================
# VIEWSETS
# ======================================================
 
class LaboratorioViewSet(viewsets.ModelViewSet):
    queryset         = Laboratorio.objects.all()
    serializer_class = LaboratorioSerializer
 
class AnalisisViewSet(viewsets.ModelViewSet):
    queryset         = Analisis.objects.all()
    serializer_class = AnalisisSerializer
 
class PlantillaViewSet(viewsets.ModelViewSet):
    queryset         = Plantilla.objects.all()
    serializer_class = PlantillaSerializer
 
class IntervaloReferenciaViewSet(viewsets.ModelViewSet):
    queryset         = IntervaloReferencia.objects.all()
    serializer_class = IntervaloReferenciaSerializer
 
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset         = Usuario.objects.all()
    serializer_class = UsuarioSerializer
 
 
# ======================================================
# PACIENTE VIEWSET
# ======================================================
 
class PacienteViewSet(viewsets.ModelViewSet):
    queryset         = Paciente.objects.all()
    serializer_class = PacienteSerializer
 
    def get_queryset(self):
        qs = Paciente.objects.all()
        usuario_id = self.request.query_params.get('usuario_id')
        if usuario_id:
            qs = qs.filter(laboratorio__usuarios__id=usuario_id)
        return qs
 
    @action(detail=False, methods=['get'], url_path='buscar_nube')
    def buscar_nube(self, request):
        """
        GET /api/pacientes/buscar_nube/
            ?usuario_id=<id>
            &nombre=<texto>
            &apellido_paterno=<texto>
 
        Devuelve LISTA de todos los pacientes que coincidan con los filtros.
        Cada paciente incluye sus análisis para poder importarlos.
 
        Respuestas:
            200 → Lista de pacientes (puede ser [] si no hay resultados)
            400 → Faltan parámetros requeridos
        """
        usuario_id       = request.query_params.get('usuario_id')
        nombre           = request.query_params.get('nombre', '').strip()
        apellido_paterno = request.query_params.get('apellido_paterno', '').strip()
 
        if not usuario_id:
            return Response(
                {"error": "Se requiere usuario_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        if not nombre and not apellido_paterno:
            return Response(
                {"error": "Debes enviar al menos nombre o apellido_paterno"},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        # Filtramos dentro del laboratorio del usuario
        qs = Paciente.objects.filter(laboratorio__usuarios__id=usuario_id)
 
        # Filtro con OR: coincide si el nombre aparece en nombre
        # O si el apellido aparece en apellido_paterno.
        # Si mandan ambos campos, busca pacientes que cumplan AMBAS condiciones.
        if nombre and apellido_paterno:
            filtros = Q(nombre__icontains=nombre) & Q(apellido_paterno__icontains=apellido_paterno)
        elif nombre:
            filtros = Q(nombre__icontains=nombre)
        else:
            filtros = Q(apellido_paterno__icontains=apellido_paterno)
 
        pacientes = qs.filter(filtros).order_by('apellido_paterno', 'nombre')
 
        # Siempre devuelve 200 con lista vacía si no hay resultados
        # (el cliente ya maneja el caso de lista vacía)
        serializer = PacienteBusquedaNubeSerializer(
            pacientes,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
 
 
# ======================================================
# VISTAS GENERALES
# ======================================================
 
def inicio(request):
    return render(request, 'inicio.html', {})
 
 
def logout_fix(request):
    from django.contrib.auth import logout
    logout(request)
    return render(request, 'admin/login.html', {})
 
 
# ======================================================
# LOGIN
# ======================================================
 
@api_view(['POST'])
def login_api(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Datos inválidos", "detalle": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
 
    correo   = serializer.validated_data["correo"]
    password = serializer.validated_data["password"]
 
    try:
        usuario = Usuario.objects.get(correo_electronico=correo, is_active=True)
    except Usuario.DoesNotExist:
        return Response(
            {"error": "Credenciales incorrectas"},
            status=status.HTTP_401_UNAUTHORIZED
        )
 
    if not usuario.check_password(password):
        return Response(
            {"error": "Credenciales incorrectas"},
            status=status.HTTP_401_UNAUTHORIZED
        )
 
    data = UsuarioLoginResponseSerializer(usuario).data
    return Response(data, status=status.HTTP_200_OK)
 
 
# ======================================================
# MI LABORATORIO
# ======================================================
 
@api_view(['GET'])
def mi_laboratorio_api(request):
    usuario_id = request.query_params.get('usuario_id')
 
    if not usuario_id:
        return Response(
            {"error": "Se requiere el parámetro usuario_id"},
            status=status.HTTP_400_BAD_REQUEST
        )
 
    try:
        usuario = Usuario.objects.get(id=usuario_id, is_active=True)
    except Usuario.DoesNotExist:
        return Response(
            {"error": "Usuario no encontrado"},
            status=status.HTTP_404_NOT_FOUND
        )
 
    laboratorio = usuario.laboratorios.first()
 
    if not laboratorio:
        return Response(
            {"error": "El usuario no tiene laboratorio asignado"},
            status=status.HTTP_404_NOT_FOUND
        )
 
    data = MiLaboratorioResponseSerializer(
        laboratorio,
        context={'request': request}
    ).data
    return Response(data, status=status.HTTP_200_OK)
 
 
# ======================================================
# PDF — FUNCIÓN AUXILIAR
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
 
    resultados  = []
    edad_meses  = paciente.edad_en_meses
 
    for res in analisis.resultados.all():
        valor_min = None
        valor_max = None
        propiedad = res.propiedad
 
        try:
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
            "opciones_cualitativas": propiedad.opciones_cualitativas if propiedad else "",
        })
 
    return {
        "paciente":                    paciente.nombre_completo,
        "edad":                        paciente.edad,
        "sexo":                        paciente.sexo,
        "tipo":                        analisis.plantilla.titulo if analisis.plantilla else "",
        "tipo_formato_raw":            analisis.plantilla.tipo_formato if analisis.plantilla else "",
        "fecha_muestra":               analisis.fecha_muestra,
        "fecha_analisis":              analisis.fecha_analisis,
        "hora_toma":                   analisis.hora_toma,
        "resultados":                  resultados,
        "laboratorio_nombre":          laboratorio.nombre_laboratorio if laboratorio else "",
        "laboratorio_logo":            logo_bytes,
        "imagen_blob1":                imagen_bytes1,
        "imagen_blob2":                imagen_bytes2,
        "tipo_muestra":                analisis.tipo_muestra or "",
        "metodo":                      analisis.metodo or "",
        "usuario_generador":           quimico.nombre                if quimico else "",
        "quimico_puesto":              quimico.puesto                if quimico else "",
        "quimico_titulo":              quimico.titulo_abreviado       if quimico else "",
        "quimico_cedula":              quimico.cedula_profesional     if quimico else "",
        "quimico_cedula_especialidad": quimico.cedula_especialidad    if quimico else "",
        "quimico_ssg":                 quimico.registro_ssg           if quimico else "",
        "quimico_universidad":         quimico.universidad_egreso     if quimico else "",
        "quimico_firma_bytes":         firma_bytes,
    }
 
 
# ======================================================
# PDF — VISTAS
# ======================================================
 
def generar_pdf_admin(request, analisis_id):
    analisis     = get_object_or_404(Analisis, id=analisis_id)
    detalles     = _construir_detalles_analisis(analisis)
    archivo_path = generar_pdf_reporte(detalles)
    return FileResponse(
        open(archivo_path, 'rb'),
        content_type='application/pdf',
        filename=f"analisis_{analisis_id}.pdf"
    )
 
 
def generar_pdf_analisis(request, pk):
    analisis     = get_object_or_404(Analisis, pk=pk)
    detalles     = _construir_detalles_analisis(analisis)
    archivo_path = generar_pdf_reporte(detalles)
    return FileResponse(
        open(archivo_path, 'rb'),
        content_type='application/pdf',
        filename=f"analisis_{pk}.pdf"
    )
 
 
# ======================================================
# ADMIN EXT
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
    resultado      = []
 
    for prop in propiedades_qs:
        if paciente:
            edad_meses = paciente.edad_en_meses
            intervalo  = prop.intervalos.filter(
                Q(sexo=paciente.sexo) | Q(sexo='AMBOS')
            ).filter(
                Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
            ).filter(
                Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
            ).first()
 
            if prop.intervalos.exists() and not intervalo:
                continue
 
            resultado.append({
                'id':                    prop.id,
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             intervalo.valor_min if intervalo else None,
                'valor_max':             intervalo.valor_max if intervalo else None,
            })
        else:
            resultado.append({
                'id':                    prop.id,
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             None,
                'valor_max':             None,
            })
 
    return JsonResponse({'propiedades': resultado})
 
 
@require_GET
def propiedades_disponibles(request):
    plantilla_id = request.GET.get('plantilla_id')
 
    if plantilla_id:
        try:
            plantilla        = Plantilla.objects.get(pk=plantilla_id)
            ids_en_plantilla = plantilla.propiedades.values_list('id', flat=True)
        except Plantilla.DoesNotExist:
            ids_en_plantilla = []
    else:
        ids_en_plantilla = []
 
    propiedades = Propiedad.objects.exclude(id__in=ids_en_plantilla).order_by('nombre_propiedad')
 
    resultado = [
        {
            'id':                    prop.id,
            'nombre_propiedad':      prop.nombre_propiedad,
            'tipo':                  prop.tipo,
            'unidad':                prop.unidad or '',
            'opciones_cualitativas': prop.opciones_cualitativas or '',
        }
        for prop in propiedades
    ]
 
    return JsonResponse({'propiedades': resultado})