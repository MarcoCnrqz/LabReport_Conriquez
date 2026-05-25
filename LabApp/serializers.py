from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PlantillaPropiedad,
    Propiedad, IntervaloReferencia, LoincCode, Usuario,
    AnalisisPropiedadExtra,          # ← FIX BUG #2: necesario para through model
)
import base64
import uuid
from django.core.files.base import ContentFile
from django.db import IntegrityError


# ======================================================
# UTILIDAD: CAMPO DE IMAGEN BASE64
# ======================================================

class Base64ImageField(serializers.ImageField):
    """
    Campo de imagen que acepta:
      - Escritura : data-URI base64 ("data:image/jpeg;base64,...")
      - Lectura   : URL absoluta de Cloudinary

    FIX BUG #3 — to_representation sobreescrito:
      Sin esta sobreescritura, DRF usaba FileField.to_representation que
      intenta value.url y captura SOLO AttributeError. Cloudinary y otros
      backends pueden lanzar excepciones distintas (cloudinary.exceptions.Error,
      ValueError, etc.) que se filtraban hacia Django como error 500.
      Ahora capturamos cualquier Exception y devolvemos None en vez de 500.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                format_part, imgstr = data.split(';base64,')
                ext  = format_part.split('/')[-1]
                uid  = uuid.uuid4()
                data = ContentFile(base64.b64decode(imgstr), name=f"{uid}.{ext}")
            except Exception as e:
                raise serializers.ValidationError(
                    f"Error decodificando imagen Base64: {str(e)}"
                )
        return super().to_internal_value(data)

    def to_representation(self, value):
        """
        FIX BUG #3:
          Antes : FileField.to_representation solo capturaba AttributeError en
                  value.url → Cloudinary podía lanzar otros errores → 500.
          Ahora : capturamos cualquier Exception y devolvemos None.

        Orden de prioridad:
          1. None / vacío           → None
          2. CloudinaryResource     → .url (Cloudinary SDK)
          3. String (public_id)     → construir URL de Cloudinary con cloudinary.utils
          4. ContentFile (fallback) → None (upload fallido; análisis guardado sin imagen)
        """
        if not value:
            return None

        # Caso 1: objeto CloudinaryResource (subida exitosa con sdk cloudinary)
        if hasattr(value, 'url'):
            try:
                url = value.url
                request = self.context.get('request')
                if request is not None:
                    return request.build_absolute_uri(url)
                return url
            except Exception:
                pass

        # Caso 2: string con public_id almacenado en BD (CharField de Cloudinary)
        if isinstance(value, str) and value:
            try:
                import cloudinary
                url = cloudinary.utils.cloudinary_url(value)[0]
                if url:
                    return url
            except Exception:
                pass
            # Fallback: devolver el public_id para que el cliente pueda construir la URL
            return value

        # Caso 3: ContentFile u objeto sin URL (upload fallido, ya capturado localmente)
        return None


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

class ResultadoSerializer(serializers.ModelSerializer):
    nombre_propiedad = serializers.SerializerMethodField()

    class Meta:
        model  = ResultadoAnalisis
        fields = ['id', 'propiedad', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad']
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
      - resultados anidados con nombre_propiedad, valor, unidad

    IMÁGENES (plantilla tipo IMAGENES_RESULTADOS):
      - imagen_resultado1/2 se declaran como Base64ImageField para que:
          ESCRITURA: el cliente envíe base64 data-URI → se sube a Cloudinary
          LECTURA:   se devuelva la URL de Cloudinary (use_url=True)

    FIXES APLICADOS:
      - BUG #1: imágenes extraídas antes de la transacción para evitar que
                Cloudinary falle DENTRO del atomic block. El upload ocurre
                FUERA, en try/except con reset de campo ante fallo.
      - BUG #2: propiedades_extra usa AnalisisPropiedadExtra.objects en lugar
                de .set() (Django prohíbe .set() en M2M con through model).
      - BUG #3: Base64ImageField.to_representation() sobreescrito para capturar
                cualquier excepción del SDK Cloudinary y evitar 500.
    """
    resultados = ResultadoSerializer(many=True, read_only=True)

    imagen_resultado1 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
    imagen_resultado2 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

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
        # NO usar source='resultados' — conflicto con el campo read-only
        # 'resultados = ResultadoSerializer(...)' que comparte el mismo accessor.
        # DRF lanza ImproperlyConfigured cuando dos campos apuntan al mismo source.
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

    def _subir_imagenes_cloudinary(self, analisis, imagen1, imagen2):
        """
        Sube imágenes a Cloudinary FUERA de la transacción usando
        cloudinary.uploader.upload() directamente.

        Por qué NO usamos save(update_fields=[campo]) con CloudinaryField:
          - CloudinaryField.pre_save() detecta si el campo cambió comparando
            el objeto actual con el valor guardado en BD. Con update_fields,
            a veces no detecta el cambio y omite el upload silenciosamente.
            El análisis queda guardado pero imagen_resultado1/2 = None en BD.

        Flujo correcto:
          1. Leer los bytes crudos del ContentFile (o archivo en memoria).
          2. Llamar cloudinary.uploader.upload(bytes, ...) — siempre sube.
          3. Guardar el public_id resultante en el campo del modelo.
          4. Llamar save(update_fields=[campo]) para persistir SOLO el public_id
             (un string), no el archivo — en este punto pre_save() no interfiere
             porque ya no hay un archivo pendiente, solo un string.
          5. Si falla en cualquier paso: resetear campo a None y continuar.
             El análisis queda guardado sin imagen; no se lanza excepción.

        Devuelve lista de campos subidos exitosamente (puede ser vacía).
        """
        import traceback as _tb
        import cloudinary.uploader

        campos_exitosos = []

        for campo, imagen in [('imagen_resultado1', imagen1), ('imagen_resultado2', imagen2)]:
            if not imagen:
                continue

            # ── Paso 1: Obtener bytes del archivo ──────────────────────────────
            try:
                # ContentFile y los archivos de Django exponen .read()
                # Algunos ya están al final del stream: seek(0) primero.
                if hasattr(imagen, 'seek'):
                    imagen.seek(0)
                file_bytes = imagen.read()
                if not file_bytes:
                    print(f"  [Serializer] ⚠️ {campo}: archivo vacío, se omite.")
                    continue
            except Exception as e:
                print(f"  [Serializer] ⚠️ {campo} — no se pudo leer el archivo: {type(e).__name__}: {e}")
                continue

            # ── Paso 2: Upload directo a Cloudinary ────────────────────────────
            try:
                resultado_cloudinary = cloudinary.uploader.upload(
                    file_bytes,
                    folder='resultados_imagenes',
                    resource_type='image',
                )
                public_id = resultado_cloudinary.get('public_id')
                if not public_id:
                    raise ValueError(
                        f"Cloudinary no devolvió public_id. Respuesta: {resultado_cloudinary}"
                    )
                print(f"  [Serializer] ✅ {campo} subido a Cloudinary — public_id: {public_id}")
            except Exception as e:
                _tb.print_exc()
                print(f"  [Serializer] ❌ cloudinary.uploader.upload falló en {campo}: {type(e).__name__}: {e}")
                # No asignamos nada al campo; queda None en BD (estado limpio).
                continue

            # ── Paso 3: Guardar el public_id en el modelo ──────────────────────
            # Asignamos el string directamente. CloudinaryField almacena public_id
            # como CharField interno; al hacer save() solo persiste el string,
            # pre_save() no intenta re-subir porque ya no hay ContentFile.
            try:
                setattr(analisis, campo, public_id)
                analisis.save(update_fields=[campo])
                campos_exitosos.append(campo)
            except Exception as e:
                _tb.print_exc()
                print(f"  [Serializer] ❌ No se pudo guardar public_id de {campo} en BD: {type(e).__name__}: {e}")
                # Resetear en memoria para que to_representation() no explote
                try:
                    setattr(analisis, campo, None)
                except Exception:
                    pass

        return campos_exitosos

    def _asignar_propiedades_extra(self, analisis, nombres_extra):
        """
        FIX BUG #2 — reemplaza analisis.propiedades_extra.set() que Django prohíbe
        en M2M con through model (AnalisisPropiedadExtra).

        Django lanza:
          AttributeError: Cannot use set() on a ManyToManyField which specifies
          an intermediary model. Use AnalisisPropiedadExtra's Manager instead.

        Solución: usar bulk_create con ignore_conflicts=True para ser idempotente
        y no duplicar si la señal post_save ya creó algún registro.
        """
        if not nombres_extra:
            return

        props_qs = Propiedad.objects.filter(nombre_propiedad__in=nombres_extra)
        if not props_qs.exists():
            return

        # IDs que ya existen para no violar UNIQUE (analisis, propiedad)
        ids_existentes = set(
            AnalisisPropiedadExtra.objects
            .filter(analisis=analisis)
            .values_list('propiedad_id', flat=True)
        )

        nuevos = [
            AnalisisPropiedadExtra(analisis=analisis, propiedad=prop)
            for prop in props_qs
            if prop.pk not in ids_existentes
        ]

        if nuevos:
            AnalisisPropiedadExtra.objects.bulk_create(nuevos, ignore_conflicts=True)
            print(f"  [Serializer] {len(nuevos)} propiedad(es) extra asignadas a análisis {analisis.pk}.")

    def create(self, validated_data):
        from django.db import transaction
        from django.db.utils import DataError as DjangoDataError
        import traceback

        # ── 1. Extraer campos especiales antes de la transacción ────────────────
        resultados_data   = validated_data.pop('resultados_input', [])
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', [])
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', [])

        # FIX BUG #1: extraer imágenes ANTES de la transacción.
        # Si se dejan dentro, Cloudinary falla DENTRO del atomic block y el
        # except convierte el error en ValidationError (400), pero la imagen
        # queda sin subir y sin registro de fallo visible al cliente.
        imagen1 = validated_data.pop('imagen_resultado1', None)
        imagen2 = validated_data.pop('imagen_resultado2', None)

        # Normalizar fecha_analisis (DateField): quitar componente hora si viene
        # como datetime completo "YYYY-MM-DD HH:MM:SS" desde el cliente.
        if 'fecha_analisis' in validated_data and validated_data['fecha_analisis']:
            fecha_val = validated_data['fecha_analisis']
            if hasattr(fecha_val, 'date'):
                validated_data['fecha_analisis'] = fecha_val.date()

        # ── 2. Guardar análisis y resultados en transacción ─────────────────────
        try:
            with transaction.atomic():
                # propiedades_excluidas es M2M sin through-model, DRF puede incluirla
                # en validated_data como lista vacía. Pasarla a Analisis(**validated_data)
                # falla con "Direct assignment to M2M is prohibited. Use .set()".
                excluidas_desde_payload = validated_data.pop('propiedades_excluidas', None)

                analisis = Analisis(**validated_data)
                analisis._desde_api = True
                analisis.save()  # ← SIN imágenes; Cloudinary no se invoca aquí

                # ── FIX BUG #2: usar método correcto para M2M con through model ──
                self._asignar_propiedades_extra(analisis, nombres_extra)

                # Propiedades excluidas (M2M simple, .set() SÍ está permitido)
                excluidas_qs = (
                    Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
                    if nombres_excluidas else None
                )
                if excluidas_desde_payload is not None:
                    analisis.propiedades_excluidas.set(excluidas_desde_payload)
                elif excluidas_qs is not None:
                    analisis.propiedades_excluidas.set(excluidas_qs)

                # ── Crear ResultadoAnalisis ──────────────────────────────────────
                for res_data in resultados_data:
                    nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
                    valor       = str(res_data.get('valor') or '')
                    unidad      = str(res_data.get('unidad') or '')

                    if not nombre_prop:
                        continue

                    # Truncar al max_length del modelo para evitar DataError
                    nombre_prop = nombre_prop[:100]
                    valor       = valor[:100]
                    unidad      = unidad[:20]

                    try:
                        propiedad_obj = Propiedad.objects.filter(
                            nombre_propiedad__iexact=nombre_prop
                        ).first()

                        if not propiedad_obj:
                            propiedad_obj = Propiedad.objects.create(
                                nombre_propiedad=nombre_prop,
                                unidad=(unidad or '')[:20],
                            )
                            print(f"  [Serializer] Propiedad on-the-fly: '{nombre_prop}'")

                    except (IntegrityError, DjangoDataError) as e:
                        propiedad_obj = Propiedad.objects.filter(
                            nombre_propiedad__iexact=nombre_prop
                        ).first()
                        if not propiedad_obj:
                            print(f"  [Serializer] ⚠️ Propiedad '{nombre_prop}' — skip: {e}")
                            continue

                    loinc_obj        = self._obtener_loinc_para_resultado(analisis, propiedad_obj)
                    unidad_resultado = (unidad or propiedad_obj.unidad or '')[:20]
                    nombre_guardar   = (nombre_prop or propiedad_obj.nombre_propiedad)[:100]

                    resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                        analisis=analisis,
                        propiedad=propiedad_obj,
                        defaults={
                            'loinc_code':       loinc_obj,
                            'nombre_propiedad': nombre_guardar,
                            'valor':            valor,
                            'unidad':           unidad_resultado,
                        }
                    )

                    if not created:
                        resultado_obj.valor = valor
                        if unidad:
                            resultado_obj.unidad = unidad_resultado
                        if nombre_guardar:
                            resultado_obj.nombre_propiedad = nombre_guardar
                        resultado_obj.save()

        except DjangoDataError as e:
            # Relanzar como 400 para que DRF no devuelva 500
            raise serializers.ValidationError({
                'error': f'Error de datos al guardar el análisis: {e}',
                'hint':  'Verifica el formato de fecha, hora, o longitud de los valores.',
            })
        except Exception as e:
            traceback.print_exc()
            raise serializers.ValidationError({
                'error': f'Error al guardar el análisis ({type(e).__name__}): {str(e)}',
            })

        # ── 3. Subir imágenes a Cloudinary FUERA de la transacción ─────────────
        # FIX BUG #1: upload aquí evita que un fallo de Cloudinary haga rollback
        # del análisis completo. Si falla, el análisis queda guardado sin imagen.
        # _subir_imagenes_cloudinary resetea el campo a None si falla, evitando
        # que el ContentFile llegue al serializer de respuesta y genere HTTP 500.
        self._subir_imagenes_cloudinary(analisis, imagen1, imagen2)

        return analisis

    def update(self, instance, validated_data):
        resultados_data   = validated_data.pop('resultados_input', None)
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', None)
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', None)

        # Extraer imágenes para subirlas correctamente después del save principal
        imagen1 = validated_data.pop('imagen_resultado1', None)
        imagen2 = validated_data.pop('imagen_resultado2', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # FIX BUG #2: usar método correcto para M2M con through model
        if nombres_extra is not None:
            self._asignar_propiedades_extra(instance, nombres_extra)

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

        # FIX BUG #1: subir imágenes con el mismo mecanismo seguro
        self._subir_imagenes_cloudinary(instance, imagen1, imagen2)

        return instance


# ======================================================
# LABORATORIO (serializer anidado liviano para búsqueda)
# ======================================================

class LaboratorioSimpleSerializer(serializers.ModelSerializer):
    # logo se expone como URL absoluta de Cloudinary para que el cliente
    # desktop pueda descargarla con _descargar_imagen_url() y guardarla
    # como BLOB en la BD local. use_url=True es el comportamiento por defecto
    # de ImageField en DRF cuando el archivo existe en un storage externo.
    logo = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Laboratorio
        fields = ['id', 'nombre_laboratorio', 'logo']


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
    # Se expone como URL de Cloudinary para que el cliente desktop
    # pueda descargarla y guardarla como BLOB en la BD local.
    firma_digital = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Usuario
        fields = [
            'id', 'nombre', 'correo', 'rol',
            'puesto', 'titulo_abreviado', 'cedula_profesional', 'is_active',
            'firma_digital',
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

class PlantillaSimpleSerializer(serializers.ModelSerializer):
    """
    Serializer ligero de Plantilla para anidar dentro de los análisis
    devueltos por la búsqueda en nube.
    Incluye 'titulo' y 'tipo_formato' para que el cliente local pueda
    resolver/crear la plantilla correcta sin depender del ID de la nube.
    """
    class Meta:
        model  = Plantilla
        fields = ['id', 'titulo', 'tipo_formato']


class ResultadoBusquedaSerializer(serializers.ModelSerializer):
    """
    Serializer ligero de ResultadoAnalisis para búsqueda en nube.
    Solo campos necesarios para la importación local; sin blobs.
    """
    nombre_propiedad = serializers.SerializerMethodField()

    class Meta:
        model  = ResultadoAnalisis
        fields = ['id', 'propiedad', 'nombre_propiedad', 'valor', 'unidad']

    def get_nombre_propiedad(self, obj):
        if obj.nombre_propiedad:
            return obj.nombre_propiedad
        try:
            if obj.propiedad:
                return obj.propiedad.nombre_propiedad
        except Exception:
            pass
        return ''


class AnalisisBusquedaSerializer(serializers.ModelSerializer):
    """
    Serializer de solo-lectura de Analisis para el endpoint buscar_nube.

    FIX: 'plantilla' se devuelve como objeto anidado {id, titulo, tipo_formato}
    en lugar del ID entero que genera AnalisisSerializer por defecto.
    El cliente local necesita el título para crear/encontrar la plantilla en su
    BD SQLite (los IDs de la nube y local no coinciden).
    """
    plantilla  = PlantillaSimpleSerializer(read_only=True)
    resultados = ResultadoBusquedaSerializer(many=True, read_only=True)

    class Meta:
        model  = Analisis
        fields = [
            'id', 'plantilla', 'fecha_muestra', 'fecha_analisis',
            'hora_toma', 'status', 'resultados',
        ]


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
        # FIX: usar AnalisisBusquedaSerializer en lugar de AnalisisSerializer para que
        # 'plantilla' se devuelva como objeto {id, titulo, tipo_formato} anidado.
        # Así el cliente local puede resolver la plantilla correcta por título.
        return AnalisisBusquedaSerializer(analisis_qs, many=True, context=self.context).data


# ======================================================
# PLANTILLA-PROPIEDAD (modelo intermedio)
# ======================================================

class PlantillaPropiedadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlantillaPropiedad
        fields = '__all__'