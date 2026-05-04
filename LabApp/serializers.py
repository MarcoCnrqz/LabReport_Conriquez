from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PlantillaPropiedad,
    Propiedad, IntervaloReferencia, LoincCode, Usuario,
)
import base64
import uuid
from django.core.files.base import ContentFile
from django.db import IntegrityError


# ======================================================
# UTILIDAD: CAMPO DE IMAGEN BASE64
# ======================================================

class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                format, imgstr = data.split(';base64,')
                ext  = format.split('/')[-1]
                uid  = uuid.uuid4()
                data = ContentFile(base64.b64decode(imgstr), name=f"{uid}.{ext}")
            except Exception as e:
                raise serializers.ValidationError(
                    f"Error decodificando imagen Base64: {str(e)}"
                )
        return super().to_internal_value(data)


# ======================================================
# SERIALIZERS DE PLANTILLAS
# ======================================================

class IntervaloReferenciaSerializer(serializers.ModelSerializer):
    """Serializer completo — usado por IntervaloReferenciaViewSet (CRUD directo)."""
    class Meta:
        model  = IntervaloReferencia
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')


class IntervaloNestedSerializer(serializers.ModelSerializer):
    """
    Serializer ligero para intervalos ANIDADOS dentro de PropiedadSerializer.
    Excluye 'propiedad' porque el padre la asigna en .create()/.update().
    """
    class Meta:
        model   = IntervaloReferencia
        exclude = ('propiedad',)
        read_only_fields = ('sincronizado', 'fecha_modificacion')


class PropiedadSerializer(serializers.ModelSerializer):
    """
    Serializer de Propiedad.

    ALINEACIÓN CON DJANGO: Propiedad NO tiene FK a LoincCode.
    El loinc_code pertenece a PlantillaPropiedad (tabla intermedia).
    Por eso loinc_num_display se inyecta manualmente desde PlantillaSerializer
    y NO se lee desde propiedad.loinc_code (que no existe en el modelo).

    loinc_num (write_only) solo se acepta en entrada para que el cliente
    local pueda informar qué LOINC quiere asignar en la relación intermedia.
    El serializer lo extrae pero NO lo guarda en Propiedad.
    """
    intervalos = IntervaloNestedSerializer(many=True, required=False)

    loinc_num = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text=(
            "Código LOINC como string (ej. '2345-7'). "
            "Usado para asignarlo en PlantillaPropiedad, NO se guarda en Propiedad."
        ),
    )

    # loinc_num_display se inyecta externamente desde PlantillaSerializer.get_propiedades().
    # Se declara aquí para que aparezca en la representación serializada cuando
    # PlantillaSerializer lo añade manualmente a data[].
    loinc_num_display = serializers.CharField(read_only=True, default="", allow_null=True)

    class Meta:
        model  = Propiedad
        fields = [
            'id', 'nombre_propiedad', 'tipo', 'unidad',
            'opciones_cualitativas', 'sincronizado', 'fecha_modificacion',
            'intervalos', 'loinc_num', 'loinc_num_display',
        ]
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def create(self, validated_data):
        intervalos_data = validated_data.pop('intervalos', [])
        validated_data.pop('loinc_num', None)  # No pertenece a Propiedad

        propiedad = Propiedad.objects.create(**validated_data)
        for int_data in intervalos_data:
            int_data.pop('propiedad', None)
            int_data.pop('id', None)
            IntervaloReferencia.objects.create(propiedad=propiedad, **int_data)
        return propiedad

    def update(self, instance, validated_data):
        intervalos_data = validated_data.pop('intervalos', None)
        validated_data.pop('loinc_num', None)  # No pertenece a Propiedad

        instance.nombre_propiedad      = validated_data.get('nombre_propiedad', instance.nombre_propiedad)
        instance.unidad                = validated_data.get('unidad', instance.unidad)
        instance.tipo                  = validated_data.get('tipo',   instance.tipo)
        instance.opciones_cualitativas = validated_data.get('opciones_cualitativas', instance.opciones_cualitativas)
        instance.save()

        if intervalos_data is not None:
            instance.intervalos.all().delete()
            for int_data in intervalos_data:
                int_data.pop('propiedad', None)
                int_data.pop('id', None)
                IntervaloReferencia.objects.create(propiedad=instance, **int_data)
        return instance


class PlantillaSerializer(serializers.ModelSerializer):
    """
    Serializer de Plantilla.

    ALINEACIÓN CON DJANGO:
    - loinc_code (FK en Plantilla) representa el panel completo.
      Se excluye de fields automáticos y se maneja via loinc_num (write) /
      loinc_panel_num (read) para evitar error 500 cuando el cliente manda
      el código LOINC como string.
    - El loinc_code de cada propiedad dentro de la plantilla vive en
      PlantillaPropiedad.loinc_code, NO en Propiedad. Se expone como
      loinc_num_display en get_propiedades().
    - seccion es un CharField simple en PlantillaPropiedad (texto libre).
    - orden_seccion controla el orden de las secciones en el reporte PDF.
    """
    propiedades = serializers.SerializerMethodField()

    loinc_panel_num = serializers.CharField(
        source='loinc_code.loinc_num',
        read_only=True,
        allow_null=True,
        default=None,
    )

    # Campo de escritura: el cliente manda el código LOINC del panel como string
    loinc_num = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Código LOINC del panel completo (ej. '58410-2'). Se resuelve a FK internamente.",
    )

    propiedades_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
        help_text="IDs remotos de Propiedad para asignar al M2M.",
    )

    propiedades_loinc = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        write_only=True,
        required=False,
        default=dict,
        help_text="Mapa {remote_propiedad_id: loinc_num} para PlantillaPropiedad.loinc_code.",
    )

    propiedades_secciones = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        write_only=True,
        required=False,
        default=dict,
        help_text=(
            "Mapa {remote_propiedad_id: seccion_nombre} que se guarda directamente "
            "en PlantillaPropiedad.seccion (string, sin tabla auxiliar)."
        ),
    )

    propiedades_ordenes = serializers.DictField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=dict,
        help_text="Mapa {remote_propiedad_id: orden} para PlantillaPropiedad.orden.",
    )

    propiedades_ordenes_seccion = serializers.DictField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=dict,
        help_text=(
            "Mapa {remote_propiedad_id: orden_seccion} para controlar el orden "
            "de aparición de las secciones en el PDF. "
            "Ej: todas las propiedades de FÓRMULA ROJA → 1, de FÓRMULA BLANCA → 2."
        ),
    )

    class Meta:
        model   = Plantilla
        # loinc_code se excluye porque se maneja manualmente via loinc_num/loinc_panel_num.
        # Exponerlo como FK entera junto con loinc_num causaba ValidationError 500.
        exclude = ('loinc_code',)
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def _resolver_loinc_panel(self, loinc_num_str):
        """Resuelve un código LOINC string a instancia LoincCode (o None)."""
        if not loinc_num_str or not str(loinc_num_str).strip():
            return None
        try:
            return LoincCode.objects.get(loinc_num=str(loinc_num_str).strip())
        except LoincCode.DoesNotExist:
            print(
                f"  [PlantillaSerializer] ADVERTENCIA: LOINC panel '{loinc_num_str}' "
                f"no encontrado. Plantilla se guarda sin loinc_code."
            )
            return None

    def get_propiedades(self, obj):
        """
        Devuelve las propiedades enriquecidas con datos de PlantillaPropiedad.

        ALINEACIÓN CON DJANGO: el loinc_num_display se lee desde
        PlantillaPropiedad.loinc_code (la tabla intermedia), NO desde
        Propiedad.loinc_code (que no existe en el modelo).

        Campos extra inyectados:
          - loinc_num_display : str  — LOINC de la tabla intermedia PlantillaPropiedad
          - seccion_nombre    : str  — CharField libre de PlantillaPropiedad
          - orden             : int  — orden dentro de la sección
          - orden_seccion     : int  — orden de la sección en el reporte PDF
        """
        base_qs = (
            PlantillaPropiedad.objects
            .filter(plantilla=obj)
            .select_related(
                'propiedad',
                'loinc_code',   # loinc_code de PlantillaPropiedad, no de Propiedad
            )
        )

        # Guard: si la migración de orden_seccion aún no se ejecutó en el servidor,
        # el ORDER BY falla con OperationalError/ProgrammingError → fallback sin ese campo.
        try:
            pp_list = list(
                base_qs.order_by('orden_seccion', 'orden', 'propiedad__nombre_propiedad')
            )
        except Exception:
            print(
                "[PlantillaSerializer] ADVERTENCIA: order_by 'orden_seccion' falló. "
                "¿Migración pendiente? Usando orden de fallback."
            )
            pp_list = list(
                base_qs.order_by('orden', 'propiedad__nombre_propiedad')
            )

        result = []
        for pp in pp_list:
            prop = pp.propiedad

            # El loinc_num viene ÚNICAMENTE de PlantillaPropiedad.loinc_code.
            # Propiedad no tiene FK a LoincCode en el modelo Django.
            loinc_num = pp.loinc_code.loinc_num if pp.loinc_code else ""

            data = PropiedadSerializer(prop).data
            data['loinc_num_display'] = loinc_num
            data['seccion_nombre']    = pp.seccion or ""
            data['orden']             = pp.orden or 0
            data['orden_seccion']     = getattr(pp, 'orden_seccion', None) or 0
            result.append(data)

        return result

    def validate_tipo_formato(self, value):
        choices_validos = [c[0] for c in Plantilla.FORMATOS]
        if value not in choices_validos:
            print(f"  [PlantillaSerializer] ADVERTENCIA: tipo_formato '{value}' no válido. Usando 'RESULTADOS'.")
            return 'RESULTADOS'
        return value

    def _aplicar_loinc_por_propiedad(self, plantilla, propiedades_loinc):
        """Asigna loinc_code_id en cada registro PlantillaPropiedad (bulk_update)."""
        if not propiedades_loinc:
            return
        prop_ids = []
        for k in propiedades_loinc:
            try:
                prop_ids.append(int(k))
            except (ValueError, TypeError):
                pass
        pp_map = {
            pp.propiedad_id: pp
            for pp in PlantillaPropiedad.objects.filter(
                plantilla=plantilla, propiedad_id__in=prop_ids
            )
        }
        # Pre-cargar todos los LoincCode necesarios de una sola query
        loinc_nums = [v.strip() for v in propiedades_loinc.values() if v and v.strip()]
        loinc_map  = {lc.loinc_num: lc for lc in LoincCode.objects.filter(loinc_num__in=loinc_nums)}

        to_update = []
        for prop_id_str, loinc_num in propiedades_loinc.items():
            if not loinc_num or not loinc_num.strip():
                continue
            try:
                prop_id = int(prop_id_str)
                pp = pp_map.get(prop_id)
                lc = loinc_map.get(loinc_num.strip())
                if pp and lc:
                    pp.loinc_code = lc
                    to_update.append(pp)
                elif pp and not lc:
                    print(f"  [PlantillaSerializer] LOINC '{loinc_num}' no encontrado para prop {prop_id}.")
            except (ValueError, TypeError):
                pass
        if to_update:
            PlantillaPropiedad.objects.bulk_update(to_update, ['loinc_code'])

    def _aplicar_seccion_por_propiedad(self, plantilla, propiedades_secciones):
        """
        Asigna la sección directamente como string en PlantillaPropiedad.seccion (bulk_update).
        """
        if not propiedades_secciones:
            return
        prop_ids = []
        for k in propiedades_secciones:
            try:
                prop_ids.append(int(k))
            except (ValueError, TypeError):
                pass
        pp_map = {
            pp.propiedad_id: pp
            for pp in PlantillaPropiedad.objects.filter(
                plantilla=plantilla, propiedad_id__in=prop_ids
            )
        }
        to_update = []
        for prop_id_str, seccion_nombre in propiedades_secciones.items():
            try:
                prop_id = int(prop_id_str)
                pp = pp_map.get(prop_id)
                if pp:
                    pp.seccion = seccion_nombre.strip() if seccion_nombre else None
                    to_update.append(pp)
            except (ValueError, TypeError):
                pass
        if to_update:
            PlantillaPropiedad.objects.bulk_update(to_update, ['seccion'])

    def _aplicar_ordenes_por_propiedad(self, plantilla, propiedades_ordenes):
        """Asigna el orden dentro de la sección en PlantillaPropiedad (bulk_update)."""
        if not propiedades_ordenes:
            return
        prop_ids = []
        for k in propiedades_ordenes:
            try:
                prop_ids.append(int(k))
            except (ValueError, TypeError):
                pass
        pp_map = {
            pp.propiedad_id: pp
            for pp in PlantillaPropiedad.objects.filter(
                plantilla=plantilla, propiedad_id__in=prop_ids
            )
        }
        to_update = []
        for prop_id_str, orden in propiedades_ordenes.items():
            try:
                prop_id = int(prop_id_str)
                pp = pp_map.get(prop_id)
                if pp:
                    pp.orden = orden
                    to_update.append(pp)
            except (ValueError, TypeError):
                pass
        if to_update:
            PlantillaPropiedad.objects.bulk_update(to_update, ['orden'])

    def _aplicar_ordenes_seccion_por_propiedad(self, plantilla, propiedades_ordenes_seccion):
        """Asigna el orden_seccion en PlantillaPropiedad (bulk_update)."""
        if not propiedades_ordenes_seccion:
            return
        prop_ids = []
        for k in propiedades_ordenes_seccion:
            try:
                prop_ids.append(int(k))
            except (ValueError, TypeError):
                pass
        pp_map = {
            pp.propiedad_id: pp
            for pp in PlantillaPropiedad.objects.filter(
                plantilla=plantilla, propiedad_id__in=prop_ids
            )
        }
        to_update = []
        for prop_id_str, orden_seccion in propiedades_ordenes_seccion.items():
            try:
                prop_id = int(prop_id_str)
                pp = pp_map.get(prop_id)
                if pp:
                    pp.orden_seccion = orden_seccion
                    to_update.append(pp)
            except (ValueError, TypeError):
                pass
        if to_update:
            PlantillaPropiedad.objects.bulk_update(to_update, ['orden_seccion'])

    def create(self, validated_data):
        propiedades_ids             = validated_data.pop('propiedades_ids', [])
        propiedades_loinc           = validated_data.pop('propiedades_loinc', {})
        propiedades_secciones       = validated_data.pop('propiedades_secciones', {})
        propiedades_ordenes         = validated_data.pop('propiedades_ordenes', {})
        propiedades_ordenes_seccion = validated_data.pop('propiedades_ordenes_seccion', {})
        loinc_num_str               = validated_data.pop('loinc_num', None)

        # Resolver loinc_code FK desde el string recibido del cliente local
        if loinc_num_str:
            validated_data['loinc_code'] = self._resolver_loinc_panel(loinc_num_str)

        plantilla = Plantilla.objects.create(**validated_data)

        if propiedades_ids:
            props = Propiedad.objects.filter(id__in=propiedades_ids)
            plantilla.propiedades.set(props)
            print(f"  [PlantillaSerializer] '{plantilla.titulo}' → {props.count()} propiedades asignadas.")
            encontrados    = set(props.values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] IDs no encontrados: {no_encontrados}")

        if propiedades_loinc:
            self._aplicar_loinc_por_propiedad(plantilla, propiedades_loinc)
        if propiedades_secciones:
            self._aplicar_seccion_por_propiedad(plantilla, propiedades_secciones)
        if propiedades_ordenes:
            self._aplicar_ordenes_por_propiedad(plantilla, propiedades_ordenes)
        if propiedades_ordenes_seccion:
            self._aplicar_ordenes_seccion_por_propiedad(plantilla, propiedades_ordenes_seccion)

        return plantilla

    def update(self, instance, validated_data):
        propiedades_ids             = validated_data.pop('propiedades_ids', None)
        propiedades_loinc           = validated_data.pop('propiedades_loinc', None)
        propiedades_secciones       = validated_data.pop('propiedades_secciones', None)
        propiedades_ordenes         = validated_data.pop('propiedades_ordenes', None)
        propiedades_ordenes_seccion = validated_data.pop('propiedades_ordenes_seccion', None)
        loinc_num_str               = validated_data.pop('loinc_num', None)

        # Resolver loinc_code FK desde el string recibido del cliente local
        if loinc_num_str is not None:
            validated_data['loinc_code'] = self._resolver_loinc_panel(loinc_num_str)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if propiedades_ids is not None:
            ids_nuevos     = set(propiedades_ids)
            ids_existentes = set(
                PlantillaPropiedad.objects
                .filter(plantilla=instance)
                .values_list('propiedad_id', flat=True)
            )

            # Agregar solo los nuevos, preservando seccion/orden de los existentes
            ids_a_agregar = ids_nuevos - ids_existentes
            for pid in ids_a_agregar:
                PlantillaPropiedad.objects.get_or_create(
                    plantilla=instance,
                    propiedad_id=pid,
                )

            # Quitar los que ya no están en la lista
            ids_a_quitar = ids_existentes - ids_nuevos
            if ids_a_quitar:
                PlantillaPropiedad.objects.filter(
                    plantilla=instance,
                    propiedad_id__in=ids_a_quitar,
                ).delete()

            encontrados    = set(Propiedad.objects.filter(id__in=ids_nuevos).values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] IDs no encontrados: {no_encontrados}")
            print(f"  [PlantillaSerializer] '{instance.titulo}' → M2M actualizado (sin borrar secciones).")

        if propiedades_loinc is not None:
            self._aplicar_loinc_por_propiedad(instance, propiedades_loinc)
        if propiedades_secciones is not None:
            self._aplicar_seccion_por_propiedad(instance, propiedades_secciones)
        if propiedades_ordenes is not None:
            self._aplicar_ordenes_por_propiedad(instance, propiedades_ordenes)
        if propiedades_ordenes_seccion is not None:
            self._aplicar_ordenes_seccion_por_propiedad(instance, propiedades_ordenes_seccion)

        return instance


# ======================================================
# SERIALIZERS DE ANÁLISIS
# ======================================================

class PlantillaLightSerializer(serializers.ModelSerializer):
    """
    Serializer ligero de Plantilla para anidar en AnalisisSerializer (GET).
    Expone titulo y tipo_formato para que el cliente local pueda:
      1. Resolver el plantilla_id correcto buscando por título (evita desajuste de IDs).
      2. Saber el tipo_formato sin una segunda petición.
    """
    class Meta:
        model  = Plantilla
        fields = ['id', 'titulo', 'tipo_formato']


class ResultadoSerializer(serializers.ModelSerializer):
    nombre_propiedad = serializers.SerializerMethodField()

    class Meta:
        model  = ResultadoAnalisis
        fields = ['id', 'propiedad', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad', 'valor_blob1', 'valor_blob2']
        extra_kwargs = {
            'propiedad': {'read_only': True},
        }

    def get_nombre_propiedad(self, obj):
        """
        Retorna el nombre_propiedad guardado en el resultado.
        Si está vacío (p. ej. análisis creado desde el admin Django sin llenar
        ese campo), cae al nombre de la Propiedad relacionada.
        Esto garantiza que los análisis de la nube siempre lleguen con nombre
        al cliente de escritorio y se importen correctamente.
        """
        if obj.nombre_propiedad:
            return obj.nombre_propiedad
        try:
            if obj.propiedad:
                return obj.propiedad.nombre_propiedad
        except Exception:
            pass
        return ''


class AnalisisSerializer(serializers.ModelSerializer):
    """
    Serializer principal de Analisis.

    ESCRITURA (POST desde la app de escritorio):
      - El cliente manda 'resultados' como lista de dicts con:
          { "nombre_propiedad": "...", "valor": "...", "unidad": "..." }
      - nombres_propiedades_extra     : ["Glucosa", ...]
      - nombres_propiedades_excluidas : ["Hemoglobina", ...]
      Se usan NOMBRES en lugar de IDs porque los IDs de la BD local SQLite
      no necesariamente coinciden con los IDs de la BD en la nube.

    LECTURA (GET):
      - plantilla anidada con {id, titulo, tipo_formato} — el cliente usa
        el título para resolver el plantilla_id local sin depender del ID
        de la nube (que puede no coincidir con el local).
      - resultados anidados con nombre_propiedad, valor, unidad, blobs.

    ALINEACIÓN CON DJANGO:
      - loinc_code en ResultadoAnalisis se obtiene de PlantillaPropiedad,
        NO de Propiedad (que no tiene esa FK en el modelo).
    """
    resultados = ResultadoSerializer(many=True, read_only=True)

    # FIX: plantilla como objeto anidado en lectura → el cliente obtiene
    # titulo y tipo_formato para resolver correctamente el plantilla_id local.
    # NOTA: NO se declara plantilla_id aquí porque fields='__all__' ya lo
    # incluye automáticamente como columna entera escribible del modelo.
    plantilla = PlantillaLightSerializer(read_only=True)

    nombres_propiedades_extra = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        default=list,
    )

    nombres_propiedades_excluidas = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        default=list,
    )

    resultados_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        default=list,
        source='resultados',
    )

    class Meta:
        model  = Analisis
        fields = '__all__'

    def _obtener_loinc_para_resultado(self, analisis, propiedad_obj):
        """
        Busca el loinc_code correcto en PlantillaPropiedad.
        Propiedad no tiene FK a LoincCode en el modelo Django.
        """
        if not analisis.plantilla_id:
            return None
        try:
            pp = PlantillaPropiedad.objects.get(
                plantilla_id=analisis.plantilla_id,
                propiedad=propiedad_obj,
            )
            return pp.loinc_code
        except PlantillaPropiedad.DoesNotExist:
            return None

    def create(self, validated_data):
        resultados_data   = validated_data.pop('resultados', [])
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', [])
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', [])

        # _desde_api se asigna DESPUÉS de construir el objeto, no como kwarg
        # (pasarlo en validated_data causaría TypeError en el constructor de Django)
        analisis = Analisis(**validated_data)
        analisis._desde_api = True
        analisis.save()

        if nombres_extra:
            analisis.propiedades_extra.set(
                Propiedad.objects.filter(nombre_propiedad__in=nombres_extra)
            )
        if nombres_excluidas:
            analisis.propiedades_excluidas.set(
                Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
            )

        for res_data in resultados_data:
            nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
            valor       = res_data.get('valor', '')
            unidad      = res_data.get('unidad', '')

            if not nombre_prop:
                continue

            try:
                propiedad_obj, creada = Propiedad.objects.get_or_create(
                    nombre_propiedad__iexact=nombre_prop,
                    defaults={
                        'nombre_propiedad': nombre_prop,
                        'unidad':           unidad or '',
                    }
                )
            except IntegrityError:
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad__iexact=nombre_prop
                ).first()
                if not propiedad_obj:
                    continue
                creada = False

            if creada:
                print(f"  [Serializer] Propiedad on-the-fly: '{nombre_prop}'")

            nombre_para_guardar = nombre_prop or propiedad_obj.nombre_propiedad

            # loinc_code viene de PlantillaPropiedad, no de Propiedad
            loinc_obj = self._obtener_loinc_para_resultado(analisis, propiedad_obj)

            resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                analisis=analisis,
                propiedad=propiedad_obj,
                defaults={
                    'loinc_code':       loinc_obj,
                    'nombre_propiedad': nombre_para_guardar,
                    'valor':            valor,
                    'unidad':           unidad or propiedad_obj.unidad or '',
                }
            )

            if not created:
                resultado_obj.valor = valor
                if unidad:
                    resultado_obj.unidad = unidad
                if nombre_para_guardar:
                    resultado_obj.nombre_propiedad = nombre_para_guardar
                resultado_obj.save()

        return analisis

    def update(self, instance, validated_data):
        resultados_data   = validated_data.pop('resultados', None)
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', None)
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if nombres_extra is not None:
            instance.propiedades_extra.set(
                Propiedad.objects.filter(nombre_propiedad__in=nombres_extra)
            )
        if nombres_excluidas is not None:
            instance.propiedades_excluidas.set(
                Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
            )

        if resultados_data is not None:
            for res_data in resultados_data:
                nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
                loinc       = res_data.get('loinc_code')

                resultado_existente = None
                if loinc:
                    resultado_existente = ResultadoAnalisis.objects.filter(
                        analisis=instance, loinc_code=loinc
                    ).first()
                if not resultado_existente and nombre_prop:
                    resultado_existente = ResultadoAnalisis.objects.filter(
                        analisis=instance,
                        propiedad__nombre_propiedad__iexact=nombre_prop
                    ).first()

                if resultado_existente:
                    resultado_existente.valor = res_data.get('valor', resultado_existente.valor)
                    resultado_existente.unidad = res_data.get('unidad', resultado_existente.unidad)
                    if nombre_prop:
                        resultado_existente.nombre_propiedad = nombre_prop
                    resultado_existente.save()

        return instance


# ======================================================
# LABORATORIO (serializer anidado liviano para búsqueda)
# ======================================================

class LaboratorioSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Laboratorio
        fields = ['id', 'nombre_laboratorio']


# ======================================================
# PACIENTE
# ======================================================

class PacienteSerializer(serializers.ModelSerializer):
    edad            = serializers.ReadOnlyField()
    edad_en_meses   = serializers.ReadOnlyField()
    nombre_completo = serializers.ReadOnlyField()

    laboratorio = LaboratorioSimpleSerializer(read_only=True)

    laboratorio_id = serializers.PrimaryKeyRelatedField(
        queryset=Laboratorio.objects.all(),
        source='laboratorio',
        write_only=True,
        required=False,
    )

    class Meta:
        model  = Paciente
        fields = [
            'id', 'nombre', 'apellido_paterno', 'apellido_materno',
            'fecha_nacimiento', 'sexo', 'telefono', 'correo_electronico',
            'laboratorio', 'laboratorio_id',
            'edad', 'edad_en_meses', 'nombre_completo',
        ]


# ======================================================
# LABORATORIO
# ======================================================

class LaboratorioSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    # El cliente local SQLite guarda esta FK como `responsable_sanitario_id`.
    # Django la llama `responsable_sanitario_principal_id` internamente.
    # Exponemos ambos nombres para máxima compatibilidad.
    responsable_sanitario_id = serializers.IntegerField(
        source='responsable_sanitario_principal_id',
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model  = Laboratorio
        fields = '__all__'


# ======================================================
# USUARIO
# ======================================================

class UsuarioSerializer(serializers.ModelSerializer):
    firma_digital = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Usuario
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}


# ======================================================
# LOGIN
# ======================================================

class LoginSerializer(serializers.Serializer):
    correo   = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UsuarioLoginResponseSerializer(serializers.ModelSerializer):
    correo = serializers.EmailField(source='correo_electronico')

    class Meta:
        model  = Usuario
        fields = [
            'id', 'nombre', 'correo', 'rol',
            'puesto', 'titulo_abreviado', 'cedula_profesional', 'is_active',
        ]


class MiLaboratorioResponseSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model  = Laboratorio
        fields = ['id', 'nombre_laboratorio', 'ciudad', 'estado', 'logo_url']

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None


# ======================================================
# BÚSQUEDA EN NUBE
# ======================================================

class PacienteBusquedaNubeSerializer(serializers.ModelSerializer):
    edad            = serializers.ReadOnlyField()
    nombre_completo = serializers.ReadOnlyField()
    analisis        = serializers.SerializerMethodField()
    laboratorio     = LaboratorioSimpleSerializer(read_only=True)

    class Meta:
        model  = Paciente
        fields = [
            'id', 'nombre', 'apellido_paterno', 'apellido_materno',
            'fecha_nacimiento', 'sexo', 'telefono', 'correo_electronico',
            'laboratorio', 'edad', 'nombre_completo', 'analisis',
        ]

    def get_analisis(self, obj):
        from .models import Analisis as AnalisisModel
        analisis_qs = AnalisisModel.objects.filter(paciente=obj).order_by('-fecha_analisis')
        return AnalisisSerializer(analisis_qs, many=True, context=self.context).data


# ======================================================
# PLANTILLA-PROPIEDAD (modelo intermedio)
# ======================================================

class PlantillaPropiedadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlantillaPropiedad
        fields = '__all__'