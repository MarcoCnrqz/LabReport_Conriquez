from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PlantillaPropiedad, SeccionPlantilla,
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
    Sin este serializer separado, la validacion exige propiedad=<id> aunque
    el cliente nunca lo manda, generando el error 400.
    """
    class Meta:
        model  = IntervaloReferencia
        exclude = ('propiedad',)
        read_only_fields = ('sincronizado', 'fecha_modificacion')


class PropiedadSerializer(serializers.ModelSerializer):
    intervalos = IntervaloNestedSerializer(many=True, required=False)

    loinc_num = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Código LOINC como string (ej. '2345-7'). Se resuelve a FK internamente.",
    )

    loinc_num_display = serializers.CharField(
        source='loinc_code.loinc_num',
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model  = Propiedad
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def _resolver_loinc(self, loinc_num_str):
        if not loinc_num_str or not loinc_num_str.strip():
            return None
        try:
            return LoincCode.objects.get(loinc_num=loinc_num_str.strip())
        except LoincCode.DoesNotExist:
            print(
                f"  [PropiedadSerializer] ADVERTENCIA: LOINC '{loinc_num_str}' "
                f"no encontrado en BD Django. Propiedad se guarda sin código LOINC."
            )
            return None

    def create(self, validated_data):
        intervalos_data = validated_data.pop('intervalos', [])
        loinc_num_str   = validated_data.pop('loinc_num', None)

        if loinc_num_str:
            validated_data['loinc_code'] = self._resolver_loinc(loinc_num_str)

        propiedad = Propiedad.objects.create(**validated_data)
        for int_data in intervalos_data:
            int_data.pop('propiedad', None)
            int_data.pop('id', None)
            IntervaloReferencia.objects.create(propiedad=propiedad, **int_data)
        return propiedad

    def update(self, instance, validated_data):
        intervalos_data = validated_data.pop('intervalos', None)
        loinc_num_str   = validated_data.pop('loinc_num', None)

        instance.nombre_propiedad      = validated_data.get('nombre_propiedad', instance.nombre_propiedad)
        instance.unidad                = validated_data.get('unidad', instance.unidad)
        instance.tipo                  = validated_data.get('tipo',   instance.tipo)
        instance.opciones_cualitativas = validated_data.get('opciones_cualitativas', instance.opciones_cualitativas)

        if loinc_num_str is not None:
            instance.loinc_code = self._resolver_loinc(loinc_num_str)
        else:
            instance.loinc_code = validated_data.get('loinc_code', instance.loinc_code)

        instance.save()

        if intervalos_data is not None:
            instance.intervalos.all().delete()
            for int_data in intervalos_data:
                int_data.pop('propiedad', None)
                int_data.pop('id', None)
                IntervaloReferencia.objects.create(propiedad=instance, **int_data)
        return instance


class SeccionPlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SeccionPlantilla
        fields = ['id', 'nombre', 'orden']


class PlantillaSerializer(serializers.ModelSerializer):
    # ✅ FIX Bug 1: propiedades ahora se lee desde PlantillaPropiedad (tabla
    # intermedia M2M) para exponer loinc_num y seccion_nombre correctos por
    # plantilla, en lugar del loinc de la Propiedad general.
    propiedades = serializers.SerializerMethodField()
    secciones   = SeccionPlantillaSerializer(many=True, read_only=True)

    # Expone el LOINC del panel como string para lectura
    loinc_panel_num = serializers.CharField(
        source='loinc_code.loinc_num',
        read_only=True,
        allow_null=True,
        default=None,
    )

    propiedades_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
        help_text="IDs remotos de Propiedad para asignar al M2M.",
    )

    secciones_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        default=list,
        help_text="Lista de secciones [{nombre: str, orden: int}] para crear junto con la plantilla.",
    )

    propiedades_loinc = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        write_only=True,
        required=False,
        default=dict,
        help_text="Mapa {remote_propiedad_id: loinc_num} que se guarda en PlantillaPropiedad.",
    )

    propiedades_secciones = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        write_only=True,
        required=False,
        default=dict,
        help_text="Mapa {remote_propiedad_id: seccion_nombre} que se guarda en PlantillaPropiedad.",
    )

    class Meta:
        model  = Plantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    # ✅ FIX Bug 1: Lee loinc_num y seccion_nombre desde PlantillaPropiedad,
    # no desde Propiedad directamente. Así la app local recibe los valores
    # específicos de la plantilla, no el LOINC genérico de la propiedad.
    def get_propiedades(self, obj):
        """
        Devuelve las propiedades enriquecidas con loinc_num_display y
        seccion_nombre leídos desde PlantillaPropiedad (tabla intermedia).

        Prioridad de loinc_num:
          1. pp.loinc_code  (asignado específicamente en esta plantilla)
          2. prop.loinc_code (loinc genérico de la propiedad)

        Campos extra expuestos (usados por _guardar_plantillas_nube en local):
          - loinc_num_display : str  ("2345-7" o "")
          - seccion_nombre    : str  ("FÓRMULA ROJA" o "")
          - seccion_orden     : int
          - orden             : int  (orden dentro de la sección)
        """
        result = []
        pp_qs = (
            PlantillaPropiedad.objects
            .filter(plantilla=obj)
            .select_related(
                'propiedad',
                'propiedad__loinc_code',
                'loinc_code',
                'seccion',
            )
            .order_by('seccion__orden', 'orden', 'propiedad__nombre_propiedad')
        )

        for pp in pp_qs:
            prop = pp.propiedad

            # Prioridad: LOINC de la tabla intermedia > LOINC de la propiedad
            if pp.loinc_code:
                loinc_num = pp.loinc_code.loinc_num or ""
            elif prop.loinc_code:
                loinc_num = prop.loinc_code.loinc_num or ""
            else:
                loinc_num = ""

            data = PropiedadSerializer(prop).data
            # Sobreescribir loinc_num_display con el valor de la tabla intermedia
            data['loinc_num_display'] = loinc_num
            data['seccion_nombre']    = pp.seccion.nombre if pp.seccion else ""
            data['seccion_orden']     = pp.seccion.orden  if pp.seccion else 9999
            data['orden']             = pp.orden or 0
            result.append(data)

        return result

    def validate_tipo_formato(self, value):
        choices_validos = [c[0] for c in Plantilla.FORMATOS]
        if value not in choices_validos:
            print(f"  [PlantillaSerializer] ADVERTENCIA: tipo_formato '{value}' no válido. Usando 'RESULTADOS'.")
            return 'RESULTADOS'
        return value

    def _aplicar_loinc_por_propiedad(self, plantilla, propiedades_loinc):
        """Asigna loinc_code_id en cada registro PlantillaPropiedad."""
        for prop_id_str, loinc_num in propiedades_loinc.items():
            if not loinc_num or not loinc_num.strip():
                continue
            try:
                prop_id = int(prop_id_str)
                pp = PlantillaPropiedad.objects.filter(
                    plantilla=plantilla, propiedad_id=prop_id
                ).first()
                if pp:
                    try:
                        lc = LoincCode.objects.get(loinc_num=loinc_num.strip())
                        pp.loinc_code = lc
                        pp.save()
                    except LoincCode.DoesNotExist:
                        print(f"  [PlantillaSerializer] LOINC '{loinc_num}' no encontrado para prop {prop_id}.")
            except (ValueError, TypeError):
                pass

    def _aplicar_seccion_por_propiedad(self, plantilla, propiedades_secciones):
        """Asigna seccion_id en cada registro PlantillaPropiedad a partir del nombre de sección."""
        for prop_id_str, seccion_nombre in propiedades_secciones.items():
            if not seccion_nombre or not seccion_nombre.strip():
                continue
            try:
                prop_id = int(prop_id_str)
                pp = PlantillaPropiedad.objects.filter(
                    plantilla=plantilla, propiedad_id=prop_id
                ).first()
                if pp:
                    try:
                        sec = SeccionPlantilla.objects.get(
                            plantilla=plantilla,
                            nombre=seccion_nombre.strip()
                        )
                        pp.seccion = sec
                        pp.save()
                    except SeccionPlantilla.DoesNotExist:
                        print(
                            f"  [PlantillaSerializer] Sección '{seccion_nombre}' "
                            f"no encontrada en plantilla {plantilla.id} para prop {prop_id}."
                        )
            except (ValueError, TypeError):
                pass

    def _sincronizar_secciones(self, plantilla, secciones_data):
        """
        Crea o actualiza SeccionPlantilla para la plantilla dada.
        Elimina las secciones que ya no vienen desde la nube,
        evitando acumulación de secciones fantasma.
        """
        nombres_recibidos = set()
        for sec in secciones_data:
            nombre = (sec.get('nombre') or '').strip()
            if not nombre:
                continue
            orden = sec.get('orden', 0) or 0
            obj, created = SeccionPlantilla.objects.get_or_create(
                plantilla=plantilla, nombre=nombre,
                defaults={'orden': orden}
            )
            if not created and obj.orden != orden:
                obj.orden = orden
                obj.save()
            nombres_recibidos.add(nombre)

        # Eliminar secciones que ya no existen en la fuente
        eliminadas = (
            SeccionPlantilla.objects
            .filter(plantilla=plantilla)
            .exclude(nombre__in=nombres_recibidos)
            .delete()
        )
        if eliminadas[0]:
            print(f"  [PlantillaSerializer] {eliminadas[0]} sección(es) obsoleta(s) eliminada(s).")

        return nombres_recibidos

    def create(self, validated_data):
        propiedades_ids       = validated_data.pop('propiedades_ids', [])
        secciones_data        = validated_data.pop('secciones_input', [])
        propiedades_loinc     = validated_data.pop('propiedades_loinc', {})
        propiedades_secciones = validated_data.pop('propiedades_secciones', {})

        plantilla = Plantilla.objects.create(**validated_data)

        if propiedades_ids:
            props = Propiedad.objects.filter(id__in=propiedades_ids)
            plantilla.propiedades.set(props)
            print(f"  [PlantillaSerializer] '{plantilla.titulo}' → {props.count()} propiedades asignadas.")
            encontrados    = set(props.values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] IDs no encontrados: {no_encontrados}")

        if secciones_data:
            self._sincronizar_secciones(plantilla, secciones_data)
            print(f"  [PlantillaSerializer] '{plantilla.titulo}' → {len(secciones_data)} secciones procesadas.")

        if propiedades_loinc:
            self._aplicar_loinc_por_propiedad(plantilla, propiedades_loinc)

        if propiedades_secciones:
            self._aplicar_seccion_por_propiedad(plantilla, propiedades_secciones)

        return plantilla

    def update(self, instance, validated_data):
        propiedades_ids       = validated_data.pop('propiedades_ids', None)
        secciones_data        = validated_data.pop('secciones_input', None)
        propiedades_loinc     = validated_data.pop('propiedades_loinc', None)
        propiedades_secciones = validated_data.pop('propiedades_secciones', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if propiedades_ids is not None:
            props = Propiedad.objects.filter(id__in=propiedades_ids)
            instance.propiedades.set(props)
            print(f"  [PlantillaSerializer] '{instance.titulo}' → M2M actualizado a {props.count()} propiedades.")
            encontrados    = set(props.values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] IDs no encontrados: {no_encontrados}")

        if secciones_data is not None:
            self._sincronizar_secciones(instance, secciones_data)

        if propiedades_loinc is not None:
            self._aplicar_loinc_por_propiedad(instance, propiedades_loinc)

        if propiedades_secciones is not None:
            self._aplicar_seccion_por_propiedad(instance, propiedades_secciones)

        return instance


# ======================================================
# SERIALIZERS DE ANÁLISIS
# ======================================================

class ResultadoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResultadoAnalisis
        fields = ['id', 'propiedad', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad']
        extra_kwargs = {
            'propiedad': {'read_only': True},
        }


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
      - Devuelve resultados con sus IDs reales de la nube para sincronización.
      - Incluye 'plantilla_titulo' para que la app local muestre el nombre
        sin AttributeError cuando plantilla es None.
    """
    resultados        = ResultadoSerializer(many=True, required=False)
    imagen_resultado1 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
    imagen_resultado2 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

    plantilla_titulo = serializers.CharField(
        source='plantilla.titulo',
        read_only=True,
        default='',
        allow_null=True,
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

    class Meta:
        model  = Analisis
        fields = '__all__'

    def create(self, validated_data):
        resultados_data   = validated_data.pop('resultados', [])
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', [])
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', [])

        analisis = Analisis(**validated_data)
        analisis._desde_api = True
        analisis.save()

        if nombres_extra:
            props_extra = Propiedad.objects.filter(nombre_propiedad__in=nombres_extra)
            analisis.propiedades_extra.set(props_extra)
            encontrados    = list(props_extra.values_list('nombre_propiedad', flat=True))
            no_encontrados = [n for n in nombres_extra if n not in encontrados]
            print(f"  [Serializer] propiedades_extra asignadas : {encontrados}")
            if no_encontrados:
                print(f"  [Serializer] propiedades_extra NO encontradas: {no_encontrados}")

        if nombres_excluidas:
            props_excluidas = Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
            analisis.propiedades_excluidas.set(props_excluidas)
            encontrados    = list(props_excluidas.values_list('nombre_propiedad', flat=True))
            no_encontrados = [n for n in nombres_excluidas if n not in encontrados]
            print(f"  [Serializer] propiedades_excluidas asignadas : {encontrados}")
            if no_encontrados:
                print(f"  [Serializer] propiedades_excluidas NO encontradas: {no_encontrados}")

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

            resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                analisis=analisis,
                propiedad=propiedad_obj,
                defaults={
                    'loinc_code':       propiedad_obj.loinc_code if hasattr(propiedad_obj, 'loinc_code') else None,
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