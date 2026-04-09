from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, Propiedad, IntervaloReferencia, LoincCode, Usuario
)
import base64
import uuid
from django.core.files.base import ContentFile


# ======================================================
# UTILIDAD: CAMPO DE IMAGEN BASE64
# ======================================================
class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                format, imgstr = data.split(';base64,')
                ext = format.split('/')[-1]
                id = uuid.uuid4()
                data = ContentFile(base64.b64decode(imgstr), name=f"{id}.{ext}")
            except Exception as e:
                raise serializers.ValidationError(
                    f"Error decodificando imagen Base64: {str(e)}"
                )
        return super().to_internal_value(data)


# ======================================================
# SERIALIZERS DE PLANTILLAS
# ======================================================

class IntervaloReferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = IntervaloReferencia
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion', 'propiedad')


class PropiedadSerializer(serializers.ModelSerializer):
    intervalos = IntervaloReferenciaSerializer(many=True, required=False)

    # Campo de ESCRITURA: la app local envía el string "2345-7" y el
    # serializer resuelve internamente la FK LoincCode correspondiente.
    # Si no existe en la BD Django, se guarda sin LOINC y se loguea.
    loinc_num = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Código LOINC como string (ej. '2345-7'). Se resuelve a FK internamente.",
    )

    # Campo de LECTURA: devuelve el string del código LOINC asignado.
    # La app local lo usa para mostrar el código al editar una propiedad
    # y para verificar que la sincronización fue correcta.
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
        """
        Recibe un string como '2345-7' y devuelve el objeto LoincCode
        correspondiente, o None si no existe en la BD Django.
        """
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
        loinc_num_str = validated_data.pop('loinc_num', None)

        if loinc_num_str:
            validated_data['loinc_code'] = self._resolver_loinc(loinc_num_str)

        propiedad = Propiedad.objects.create(**validated_data)
        for int_data in intervalos_data:
            int_data.pop('propiedad', None)
            IntervaloReferencia.objects.create(propiedad=propiedad, **int_data)
        return propiedad

    def update(self, instance, validated_data):
        intervalos_data = validated_data.pop('intervalos', None)
        loinc_num_str = validated_data.pop('loinc_num', None)

        instance.nombre_propiedad = validated_data.get(
            'nombre_propiedad', instance.nombre_propiedad
        )
        instance.unidad = validated_data.get('unidad', instance.unidad)
        instance.tipo   = validated_data.get('tipo',   instance.tipo)
        instance.opciones_cualitativas = validated_data.get(
            'opciones_cualitativas', instance.opciones_cualitativas
        )

        if loinc_num_str is not None:
            instance.loinc_code = self._resolver_loinc(loinc_num_str)
        else:
            instance.loinc_code = validated_data.get('loinc_code', instance.loinc_code)

        instance.save()
        if intervalos_data is not None:
            instance.intervalos.all().delete()
            for int_data in intervalos_data:
                int_data.pop('propiedad', None)
                IntervaloReferencia.objects.create(propiedad=instance, **int_data)
        return instance


class PlantillaSerializer(serializers.ModelSerializer):
    propiedades = PropiedadSerializer(many=True, read_only=True)

    propiedades_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
        help_text="IDs de Propiedad (PK en esta BD Django) para asignar al M2M.",
    )

    class Meta:
        model  = Plantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def validate_tipo_formato(self, value):
        choices_validos = [c[0] for c in Plantilla.FORMATOS]
        if value not in choices_validos:
            print(f"  [PlantillaSerializer] ADVERTENCIA: tipo_formato '{value}' no existe "
                  f"en el modelo Django. Se usará 'RESULTADOS' como fallback.")
            return 'RESULTADOS'
        return value

    def create(self, validated_data):
        propiedades_ids = validated_data.pop('propiedades_ids', [])
        plantilla = Plantilla.objects.create(**validated_data)
        if propiedades_ids:
            props = Propiedad.objects.filter(id__in=propiedades_ids)
            plantilla.propiedades.set(props)
            print(f"  [PlantillaSerializer] Plantilla '{plantilla.titulo}' → "
                  f"{props.count()} propiedades asignadas (de {len(propiedades_ids)} IDs recibidos).")
            encontrados = set(props.values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] ADVERTENCIA: IDs de propiedades no encontrados "
                      f"en la BD Django: {no_encontrados}")
        return plantilla

    def update(self, instance, validated_data):
        propiedades_ids = validated_data.pop('propiedades_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if propiedades_ids is not None:
            props = Propiedad.objects.filter(id__in=propiedades_ids)
            instance.propiedades.set(props)
            print(f"  [PlantillaSerializer] Plantilla '{instance.titulo}' → "
                  f"M2M actualizado a {props.count()} propiedades.")
            encontrados = set(props.values_list('id', flat=True))
            no_encontrados = [pid for pid in propiedades_ids if pid not in encontrados]
            if no_encontrados:
                print(f"  [PlantillaSerializer] ADVERTENCIA: IDs no encontrados: {no_encontrados}")
        return instance


# ======================================================
# SERIALIZERS DE ANÁLISIS
# ======================================================

class ResultadoSerializer(serializers.ModelSerializer):
    """
    Serializer de LECTURA para ResultadoAnalisis.

    nombre_propiedad es un campo real en la BD, se lee y escribe
    directamente. Se incluye explícitamente para garantizar que
    siempre viaja en la respuesta.
    """
    class Meta:
        model  = ResultadoAnalisis
        fields = ['id', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad']


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
      - FIX: Incluye 'plantilla_titulo' para que la app local pueda mostrar
        el nombre de la plantilla sin necesidad de un JOIN adicional.
        La app usaba analisis.get('plantilla', 'ESTUDIO') pero 'plantilla'
        es una FK (int o None), nunca un string, causando AttributeError al
        llamar .upper() sobre None.
    """
    resultados        = ResultadoSerializer(many=True, required=False)
    imagen_resultado1 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
    imagen_resultado2 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

    # FIX: campo de solo lectura que expone el título de la plantilla como
    # string en cada respuesta GET, resolviendo el AttributeError en la app
    # cuando plantilla es None o un entero.
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
        help_text="Nombres de propiedades añadidas manualmente en este análisis.",
    )
    nombres_propiedades_excluidas = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        default=list,
        help_text="Nombres de propiedades de la plantilla excluidas en este análisis.",
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

            propiedad_obj = None
            if nombre_prop:
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad__iexact=nombre_prop
                ).first()

                if not propiedad_obj:
                    propiedad_obj = Propiedad.objects.create(
                        nombre_propiedad=nombre_prop,
                        unidad=unidad or '',
                    )
                    print(f"  [Serializer] Propiedad on-the-fly: '{nombre_prop}'")

            if not propiedad_obj:
                continue

            nombre_para_guardar = nombre_prop or propiedad_obj.nombre_propiedad

            resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                analisis=analisis,
                propiedad=propiedad_obj,
                defaults={
                    'loinc_code':       propiedad_obj.loinc_code,
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
                    resultado_existente.valor = res_data.get(
                        'valor', resultado_existente.valor
                    )
                    resultado_existente.unidad = res_data.get(
                        'unidad', resultado_existente.unidad
                    )
                    if nombre_prop:
                        resultado_existente.nombre_propiedad = nombre_prop
                    resultado_existente.save()

        return instance


# ======================================================
# LABORATORIO (serializer anidado liviano para búsqueda)
# ======================================================

class LaboratorioSimpleSerializer(serializers.ModelSerializer):
    """
    FIX: Serializer liviano que devuelve el laboratorio como objeto
    {id, nombre_laboratorio} en la respuesta de búsqueda de pacientes.
    La app local necesita el nombre real para guardarlo en la BD local,
    no solo el ID (que era lo que devolvía PacienteSerializer antes).
    """
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

    # FIX: laboratorio como objeto completo para que la app local
    # pueda obtener el nombre del laboratorio al crear/editar pacientes.
    laboratorio = LaboratorioSimpleSerializer(read_only=True)

    # Campo de escritura separado para aceptar el ID al crear/actualizar
    laboratorio_id = serializers.PrimaryKeyRelatedField(
        queryset=Laboratorio.objects.all(),
        source='laboratorio',
        write_only=True,
        required=False,
    )

    class Meta:
        model  = Paciente
        fields = [
            'id',
            'nombre',
            'apellido_paterno',
            'apellido_materno',
            'fecha_nacimiento',
            'sexo',
            'telefono',
            'correo_electronico',
            'laboratorio',
            'laboratorio_id',
            'edad',
            'edad_en_meses',
            'nombre_completo',
        ]


# ======================================================
# LABORATORIO
# ======================================================

class LaboratorioSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

    class Meta:
        model  = Laboratorio
        fields = '__all__'


# ======================================================
# USUARIO
# ======================================================

class UsuarioSerializer(serializers.ModelSerializer):
    firma_digital = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

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

    # FIX: laboratorio como objeto completo para que importar_paciente_desde_nube
    # en el cliente pueda extraer tanto el id como el nombre_laboratorio real,
    # en lugar de guardarlo siempre como 'Lab Sincronizado'.
    laboratorio = LaboratorioSimpleSerializer(read_only=True)

    class Meta:
        model  = Paciente
        fields = [
            'id',
            'nombre',
            'apellido_paterno',
            'apellido_materno',
            'fecha_nacimiento',
            'sexo',
            'telefono',
            'correo_electronico',
            'laboratorio',
            'edad',
            'nombre_completo',
            'analisis',
        ]

    def get_analisis(self, obj):
        from .models import Analisis as AnalisisModel
        analisis_qs = AnalisisModel.objects.filter(
            paciente=obj
        ).order_by('-fecha_analisis')
        return AnalisisSerializer(
            analisis_qs, many=True, context=self.context
        ).data