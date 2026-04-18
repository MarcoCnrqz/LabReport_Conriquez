import requests as http_requests
import jwt
import datetime
from functools import wraps

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
from django.conf import settings

from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, Propiedad, IntervaloReferencia, Usuario,
    PlantillaPropiedad,
)
from .serializers import (
    PacienteSerializer, LaboratorioSerializer, AnalisisSerializer,
    PlantillaSerializer, PropiedadSerializer, IntervaloReferenciaSerializer,
    UsuarioSerializer, LoginSerializer, UsuarioLoginResponseSerializer,
    MiLaboratorioResponseSerializer,
    PacienteBusquedaNubeSerializer,
    ResultadoSerializer,
    PlantillaPropiedadSerializer,
)
from .utils.imprimir_pdf import generar_pdf_reporte


# ======================================================
# UTILIDADES DE PRESENTACIÓN
# ======================================================

def _nombre_display(nombre: str) -> str:
    """
    Devuelve el nombre de una propiedad sin los prefijos de símbolo
    que se usan para diferenciar variantes del mismo analito.

    Convención del sistema:
        '%MONOCITOS'   → 'MONOCITOS'   (la variante % la da la unidad)
        '#ERITROCITOS' → 'ERITROCITOS' (la variante abs la da la unidad)
        'HEMOGLOBINA'  → 'HEMOGLOBINA' (sin cambio)

    Usar esta función en cualquier contexto de salida (PDF, API, etc.)
    para que el usuario final vea un nombre limpio.
    """
    import re
    return re.sub(r'^[#%]+', '', nombre).strip() if nombre else nombre


# ======================================================
# JWT — HELPERS
# ======================================================

def _jwt_crear_token(usuario_id: int, tipo: str) -> str:
    """
    Crea un token JWT.
    tipo: 'access'  -> expira en JWT_ACCESS_EXPIRY minutos
          'refresh' -> expira en JWT_REFRESH_EXPIRY minutos
    """
    if tipo == 'access':
        minutos = getattr(settings, 'JWT_ACCESS_EXPIRY',  60 * 8)
    else:
        minutos = getattr(settings, 'JWT_REFRESH_EXPIRY', 60 * 24 * 30)

    payload = {
        'user_id': usuario_id,
        'tipo':    tipo,
        'exp':     datetime.datetime.utcnow() + datetime.timedelta(minutes=minutos),
        'iat':     datetime.datetime.utcnow(),
    }
    return jwt.encode(
        payload,
        getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY),
        algorithm=getattr(settings, 'JWT_ALGORITHM', 'HS256'),
    )


def _jwt_verificar_token(token: str, tipo: str = 'access'):
    """
    Verifica y decodifica un token JWT.
    Devuelve el payload si es válido, o lanza jwt.PyJWTError si no lo es.
    """
    payload = jwt.decode(
        token,
        getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY),
        algorithms=[getattr(settings, 'JWT_ALGORITHM', 'HS256')],
    )
    if payload.get('tipo') != tipo:
        raise jwt.InvalidTokenError('Tipo de token incorrecto')
    return payload


def jwt_requerido(view_func):
    """
    Decorador para vistas basadas en funcion (api_view).
    Valida el header: Authorization: Bearer <access_token>
    Si es valido, inyecta request.usuario_jwt_id con el id del usuario.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Token no proporcionado. Usa: Authorization: Bearer <token>'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token = auth_header.split(' ', 1)[1].strip()
        try:
            payload = _jwt_verificar_token(token, tipo='access')
        except jwt.ExpiredSignatureError:
            return Response(
                {'error': 'Token expirado. Solicita uno nuevo con /api/token/refresh/'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except jwt.PyJWTError as e:
            return Response(
                {'error': f'Token invalido: {str(e)}'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        request.usuario_jwt_id = payload['user_id']
        return view_func(request, *args, **kwargs)
    return wrapper


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

    def get_queryset(self):
        qs         = Laboratorio.objects.all()
        usuario_id = self.request.query_params.get('usuario_id')
        if usuario_id:
            qs = qs.filter(usuarios__id=usuario_id)
        return qs.order_by('nombre_laboratorio')


class AnalisisViewSet(viewsets.ModelViewSet):
    queryset         = Analisis.objects.all()
    serializer_class = AnalisisSerializer


class ResultadoAnalisisViewSet(viewsets.ModelViewSet):
    queryset         = ResultadoAnalisis.objects.all()
    serializer_class = ResultadoSerializer

    def partial_update(self, request, *args, **kwargs):
        instancia    = self.get_object()
        nuevo_valor  = request.data.get('valor')
        nueva_unidad = request.data.get('unidad')

        if nuevo_valor is not None:
            instancia.valor = nuevo_valor
        if nueva_unidad is not None:
            instancia.unidad = nueva_unidad
        instancia.save()

        return Response(ResultadoSerializer(instancia).data, status=status.HTTP_200_OK)


class PlantillaViewSet(viewsets.ModelViewSet):
    queryset = Plantilla.objects.prefetch_related(
        'propiedades',
        'propiedades__intervalos',
    ).all()
    serializer_class = PlantillaSerializer


class PropiedadViewSet(viewsets.ModelViewSet):
    queryset         = Propiedad.objects.prefetch_related('intervalos').all()
    serializer_class = PropiedadSerializer


class PropiedadPlantillaViewSet(viewsets.ModelViewSet):
    queryset         = PlantillaPropiedad.objects.select_related('plantilla', 'propiedad').all()
    serializer_class = PlantillaPropiedadSerializer


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
        qs         = Paciente.objects.all()
        usuario_id = self.request.query_params.get('usuario_id')
        if usuario_id:
            qs = qs.filter(laboratorio__usuarios__id=usuario_id)
        return qs

    @action(detail=False, methods=['get'], url_path='buscar_nube')
    def buscar_nube(self, request):
        usuario_id       = request.query_params.get('usuario_id')
        nombre           = request.query_params.get('nombre', '').strip()
        apellido_paterno = request.query_params.get('apellido_paterno', '').strip()

        if not usuario_id:
            return Response({"error": "Se requiere usuario_id"}, status=status.HTTP_400_BAD_REQUEST)

        if not Usuario.objects.filter(id=usuario_id, is_active=True).exists():
            return Response({"error": "Usuario no encontrado o inactivo"}, status=status.HTTP_404_NOT_FOUND)

        if not nombre and not apellido_paterno:
            return Response(
                {"error": "Debes enviar al menos nombre o apellido_paterno"},
                status=status.HTTP_400_BAD_REQUEST
            )

        labs_usuario = Laboratorio.objects.filter(usuarios__id=usuario_id)
        if labs_usuario.exists():
            qs = Paciente.objects.filter(laboratorio__in=labs_usuario)
        else:
            print(f"  [buscar_nube] ADVERTENCIA: usuario {usuario_id} sin laboratorios. Buscando en todos.")
            qs = Paciente.objects.all()

        if nombre and apellido_paterno:
            filtros = Q(nombre__icontains=nombre) & Q(apellido_paterno__icontains=apellido_paterno)
        elif nombre:
            filtros = Q(nombre__icontains=nombre)
        else:
            filtros = Q(apellido_paterno__icontains=apellido_paterno)

        pacientes  = qs.filter(filtros).order_by('apellido_paterno', 'nombre')
        serializer = PacienteBusquedaNubeSerializer(pacientes, many=True, context={'request': request})
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
        return Response({"error": "Credenciales incorrectas"}, status=status.HTTP_401_UNAUTHORIZED)

    if not usuario.check_password(password):
        return Response({"error": "Credenciales incorrectas"}, status=status.HTTP_401_UNAUTHORIZED)

    data          = UsuarioLoginResponseSerializer(usuario).data
    access_token  = _jwt_crear_token(usuario.id, 'access')
    refresh_token = _jwt_crear_token(usuario.id, 'refresh')

    return Response({
        **data,
        'access_token':  access_token,
        'refresh_token': refresh_token,
    }, status=status.HTTP_200_OK)


# ======================================================
# REFRESH TOKEN
# ======================================================

@api_view(['POST'])
def refresh_token_api(request):
    """
    Genera un nuevo access_token a partir de un refresh_token valido.

    Body JSON:
        { "refresh_token": "<token>" }

    Respuesta:
        { "access_token": "<nuevo_token>" }
    """
    refresh_token = request.data.get('refresh_token', '').strip()
    if not refresh_token:
        return Response({'error': 'Se requiere refresh_token'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _jwt_verificar_token(refresh_token, tipo='refresh')
    except jwt.ExpiredSignatureError:
        return Response({'error': 'Refresh token expirado. Inicia sesion de nuevo.'}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.PyJWTError as e:
        return Response({'error': f'Refresh token invalido: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)

    nuevo_access = _jwt_crear_token(payload['user_id'], 'access')
    return Response({'access_token': nuevo_access}, status=status.HTTP_200_OK)


# ======================================================
# MI LABORATORIO
# ======================================================

@api_view(['GET'])
@jwt_requerido
def mi_laboratorio_api(request):
    usuario_id = request.usuario_jwt_id

    try:
        usuario = Usuario.objects.get(id=usuario_id, is_active=True)
    except Usuario.DoesNotExist:
        return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)

    laboratorio = usuario.laboratorios.first()

    if not laboratorio:
        return Response({"error": "El usuario no tiene laboratorio asignado"}, status=status.HTTP_404_NOT_FOUND)

    data = MiLaboratorioResponseSerializer(laboratorio, context={'request': request}).data
    return Response(data, status=status.HTTP_200_OK)


# ======================================================
# PRIORIDAD DE SECCIONES PARA EL PDF (fallback)
# ======================================================
#
# Se usa ÚNICAMENTE como fallback cuando ResultadoAnalisis.orden_seccion
# no está disponible (p. ej. análisis creados antes de la migración que
# agregó ese campo).
#
# Para análisis nuevos, el orden viene directamente de
# ResultadoAnalisis.orden_seccion, que se hereda de
# PlantillaPropiedad.orden_seccion o se asigna desde el picker JS.
#
PRIORIDAD_SECCIONES = {
    'FÓRMULA ROJA':                   1,
    'FÓRMULA BLANCA':                 2,
    'SERIE PLAQUETARIA':              3,
    'SERIE TROMBOCÍTICA':             3,
    'COAGULACIÓN':                    4,
    'GASOMETRÍA':                     5,
    'BIOQUÍMICA SANGUÍNEA':           10,
    'QUÍMICA SANGUÍNEA':              10,
    'PERFIL LIPÍDICO':                11,
    'PRUEBAS DE FUNCIÓN HEPÁTICA':    12,
    'PRUEBAS DE FUNCIÓN RENAL':       13,
    'ELECTRÓLITOS SÉRICOS':           14,
    'HORMONAS TIROIDEAS':             15,
    'HORMONAS REPRODUCTIVAS':         16,
    'MARCADORES TUMORALES':           17,
    'URIANÁLISIS':                    20,
    'INMUNOLOGÍA / SEROLOGÍA':        21,
    'MICROBIOLOGÍA':                  22,
}


def _prioridad_seccion_fallback(nombre_seccion: str) -> tuple:
    """
    Fallback de ordenamiento por nombre de sección.
    Se usa solo cuando orden_seccion == 9999 (valor por defecto/desconocido).

    Capa 1: busca el nombre en PRIORIDAD_SECCIONES (insensible a mayúsculas).
    Capa 2: si no está en el dict, ordena alfabéticamente (prioridad 9999).
    """
    clave     = nombre_seccion.strip().upper()
    prioridad = PRIORIDAD_SECCIONES.get(clave, 9999)
    return (prioridad, nombre_seccion)


# ======================================================
# PDF — FUNCIÓN AUXILIAR
# ======================================================

def _construir_detalles_analisis(analisis):
    """
    Construye el diccionario de datos que se pasa a generar_pdf_reporte().

    Orden de secciones (de mayor a menor prioridad):
      1. ResultadoAnalisis.orden_seccion  — valor guardado al crear el análisis,
         heredado de PlantillaPropiedad.orden_seccion o asignado por el picker JS.
      2. PRIORIDAD_SECCIONES (fallback)   — dict hardcodeado para análisis
         creados antes de que existiera el campo orden_seccion.

    Sección de propiedades extra:
      Se lee desde ResultadoAnalisis.seccion (guardado por el admin al crear
      el análisis desde el picker JS). Ya no se pierde la sección al guardar.
    """
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

    edad_meses    = paciente.edad_en_meses
    ids_excluidos = analisis.propiedades_excluidas.values_list('id', flat=True)
    resultados_qs = analisis.resultados.exclude(propiedad_id__in=ids_excluidos)

    # ── Mapa propiedad_id → PlantillaPropiedad ───────────────────────────────
    # Fuente de verdad para sección y orden de las propiedades de la PLANTILLA.
    # Las propiedades EXTRA leen su sección desde ResultadoAnalisis.seccion
    # (guardado por el admin) — no necesitan buscarse aquí.
    pp_map = {}
    if analisis.plantilla:
        for pp in (
            PlantillaPropiedad.objects
            .filter(plantilla=analisis.plantilla)
            .select_related('loinc_code')
            .order_by('orden_seccion', 'orden')
        ):
            pp_map[pp.propiedad_id] = pp

    # ── Construir lista de resultados con sección y orden ────────────────────
    resultados_raw = []

    for res in resultados_qs.select_related('propiedad', 'loinc_code'):
        nombre_prop = res.nombre_propiedad
        if not nombre_prop:
            try:
                nombre_prop = res.propiedad.nombre_propiedad if res.propiedad else None
            except Exception:
                nombre_prop = None

        # Limpiar prefijos de símbolo (#, %) para que el PDF muestre
        # el nombre sin el artificio de diferenciación interno.
        # Ej: '%MONOCITOS' → 'MONOCITOS'  (la unidad ya indica que es %)
        nombre_prop = _nombre_display(nombre_prop)

        if not nombre_prop:
            print(f"  [PDF] Resultado id={res.pk} sin nombre_propiedad — omitido del PDF")
            continue

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

        # ── Resolver sección y orden_seccion ─────────────────────────────────
        #
        # Prioridad:
        #   1. PlantillaPropiedad  → para props de la plantilla (fuente de verdad
        #      configurada por el admin con el picker).
        #   2. ResultadoAnalisis.seccion / .orden_seccion → para propiedades extra
        #      (guardadas por el admin desde el picker JS al crear el análisis)
        #      y también como respaldo para props de plantilla si el pp_map falla.
        #
        pp = pp_map.get(res.propiedad_id)
        if pp:
            seccion_nombre = pp.seccion       or ''
            orden_sec      = pp.orden_seccion
        else:
            # Propiedad extra: leer los valores guardados en ResultadoAnalisis
            seccion_nombre = res.seccion       or ''
            orden_sec      = res.orden_seccion  # default 9999 si no se asignó

        # Fallback por nombre cuando orden_seccion es 9999 (análisis antiguos
        # o propiedades extra sin orden explícito).
        if orden_sec >= 9999 and seccion_nombre:
            orden_sec = _prioridad_seccion_fallback(seccion_nombre)[0]

        resultados_raw.append({
            "nombre_propiedad":      nombre_prop,
            "valor":                 res.valor or "",
            "unidad":                res.unidad or "",
            "valor_min":             valor_min,
            "valor_max":             valor_max,
            "opciones_cualitativas": propiedad.opciones_cualitativas if propiedad else "",
            "seccion":               seccion_nombre,
            "orden_seccion":         orden_sec,
            "loinc_num":             res.loinc_code.loinc_num if res.loinc_code else "",
        })

    # ── Agrupar y ordenar secciones para el PDF ──────────────────────────────
    #
    # Orden primario : orden_seccion (campo numérico explícito).
    # Orden secundario: nombre de sección (alfabético, solo entre empates).
    #
    tiene_secciones = any(r["seccion"] for r in resultados_raw)

    if tiene_secciones:
        # Agrupar por nombre de sección, conservando el orden_seccion mínimo
        # del grupo (en caso de que haya inconsistencias entre filas).
        grupos = {}
        for r in resultados_raw:
            sec = r["seccion"] or ""
            if sec not in grupos:
                grupos[sec] = {
                    "seccion":       sec,
                    "orden_seccion": r["orden_seccion"],
                    "filas":         [],
                }
            else:
                # Tomar el orden_seccion más bajo del grupo
                if r["orden_seccion"] < grupos[sec]["orden_seccion"]:
                    grupos[sec]["orden_seccion"] = r["orden_seccion"]
            grupos[sec]["filas"].append(r)

        resultados_agrupados = sorted(
            grupos.values(),
            key=lambda g: (g["orden_seccion"], g["seccion"]),
        )
    else:
        resultados_agrupados = [{"seccion": "", "orden_seccion": 0, "filas": resultados_raw}]

    # Tipo de muestra y método: el análisis puede tener valores propios
    # (cuando el médico los modificó), si no, se usan los de la plantilla.
    tipo_muestra = (
        analisis.tipo_muestra
        or (analisis.plantilla.tipo_muestra if analisis.plantilla else '')
        or ''
    )
    metodo = (
        analisis.metodo
        or (analisis.plantilla.metodo if analisis.plantilla else '')
        or ''
    )

    return {
        "paciente":                    paciente.nombre_completo,
        "edad":                        paciente.edad,
        "sexo":                        paciente.sexo,
        "tipo":                        analisis.plantilla.titulo if analisis.plantilla else "",
        "tipo_formato_raw":            analisis.plantilla.tipo_formato if analisis.plantilla else "",
        "fecha_muestra":               analisis.fecha_muestra,
        "fecha_analisis":              analisis.fecha_analisis,
        "hora_toma":                   analisis.hora_toma,
        "resultados_agrupados":        resultados_agrupados,
        "laboratorio_nombre":          laboratorio.nombre_laboratorio if laboratorio else "",
        "laboratorio_logo":            logo_bytes,
        "imagen_blob1":                imagen_bytes1,
        "imagen_blob2":                imagen_bytes2,
        "tipo_muestra":                tipo_muestra,
        "metodo":                      metodo,
        "usuario_generador":           quimico.nombre                 if quimico else "",
        "quimico_puesto":              quimico.puesto                 if quimico else "",
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
def plantilla_tipo_muestra_metodo(request, plantilla_id):
    """
    Devuelve tipo_muestra y metodo de una plantilla para que el admin
    de Análisis los pre-llene automáticamente al seleccionar la plantilla.
    GET /admin_ext/plantilla/<id>/muestra-metodo/
    """
    try:
        plantilla = Plantilla.objects.only('tipo_muestra', 'metodo').get(pk=plantilla_id)
        return JsonResponse({
            'tipo_muestra': plantilla.tipo_muestra or '',
            'metodo':       plantilla.metodo       or '',
        })
    except Plantilla.DoesNotExist:
        return JsonResponse({'tipo_muestra': '', 'metodo': ''}, status=404)


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

    # Obtener propiedades ya ordenadas por orden_seccion/orden desde PlantillaPropiedad
    pp_list = list(
        PlantillaPropiedad.objects
        .filter(plantilla=plantilla)
        .select_related('propiedad', 'loinc_code')
        .order_by('orden_seccion', 'orden', 'propiedad__nombre_propiedad')
    )

    resultado = []

    for pp in pp_list:
        prop           = pp.propiedad
        seccion_nombre = pp.seccion       or ''
        orden_seccion  = pp.orden_seccion

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

            loinc_num  = (pp.loinc_code.loinc_num if pp.loinc_code else '')
            loinc_desc = (pp.loinc_code.shortname  if pp.loinc_code else '')
            resultado.append({
                'id':                    prop.id,
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             intervalo.valor_min if intervalo else None,
                'valor_max':             intervalo.valor_max if intervalo else None,
                'seccion_nombre':        seccion_nombre,
                'orden_seccion':         orden_seccion,
                'loinc_num':             loinc_num,
                'loinc_desc':            loinc_desc,
            })
        else:
            loinc_num  = (pp.loinc_code.loinc_num if pp.loinc_code else '')
            loinc_desc = (pp.loinc_code.shortname  if pp.loinc_code else '')
            resultado.append({
                'id':                    prop.id,
                'nombre_propiedad':      prop.nombre_propiedad,
                'tipo':                  prop.tipo,
                'opciones_cualitativas': prop.opciones_cualitativas or '',
                'unidad':                prop.unidad or '',
                'valor_min':             None,
                'valor_max':             None,
                'seccion_nombre':        seccion_nombre,
                'orden_seccion':         orden_seccion,
                'loinc_num':             loinc_num,
                'loinc_desc':            loinc_desc,
            })

    return JsonResponse({'propiedades': resultado})


@require_GET
def propiedades_disponibles(request):
    plantilla_id = request.GET.get('plantilla_id')
    paciente_id  = request.GET.get('paciente_id')

    if plantilla_id:
        try:
            plantilla        = Plantilla.objects.get(pk=plantilla_id)
            ids_en_plantilla = plantilla.propiedades.values_list('id', flat=True)
        except Plantilla.DoesNotExist:
            ids_en_plantilla = []
    else:
        ids_en_plantilla = []

    paciente = None
    if paciente_id:
        try:
            paciente = Paciente.objects.get(pk=paciente_id)
        except Paciente.DoesNotExist:
            paciente = None

    propiedades = (
        Propiedad.objects
        .exclude(id__in=ids_en_plantilla)
        .prefetch_related('intervalos')
        .order_by('nombre_propiedad')
    )

    resultado = []
    for prop in propiedades:
        valor_min = None
        valor_max = None

        if paciente:
            edad_meses = paciente.edad_en_meses
            intervalo  = prop.intervalos.filter(
                Q(sexo=paciente.sexo) | Q(sexo='AMBOS')
            ).filter(
                Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
            ).filter(
                Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
            ).first()

            if intervalo:
                valor_min = intervalo.valor_min
                valor_max = intervalo.valor_max

        resultado.append({
            'id':                    prop.id,
            'nombre_propiedad':      prop.nombre_propiedad,
            'tipo':                  prop.tipo,
            'unidad':                prop.unidad or '',
            'opciones_cualitativas': prop.opciones_cualitativas or '',
            'valor_min':             valor_min,
            'valor_max':             valor_max,
            # Las props extra no tienen LOINC ni sección predefinidos;
            # el picker JS los asigna al momento de agregar la propiedad.
            'loinc_num':             '',
            'loinc_desc':            '',
        })

    return JsonResponse({'propiedades': resultado})
