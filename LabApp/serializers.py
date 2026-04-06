# serializers.py

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
        model = IntervaloReferencia
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion', 'propiedad')


class PropiedadSerializer(serializers.ModelSerializer):
    intervalos = IntervaloReferenciaSerializer(many=True, required=False)

    class Meta:
        model = Propiedad
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def create(self, validated_data):
        intervalos_data = validated_data.pop('intervalos', [])
        propiedad = Propiedad.objects.create(**validated_data)
        for int_data in intervalos_data:
            IntervaloReferencia.objects.create(propiedad=propiedad, **int_data)
        return propiedad

    def update(self, instance, validated_data):
        intervalos_data = validated_data.pop('intervalos', None)
        instance.nombre_propiedad = validated_data.get(
            'nombre_propiedad', instance.nombre_propiedad
        )
        instance.unidad = validated_data.get('unidad', instance.unidad)
        instance.loinc_code = validated_data.get('loinc_code', instance.loinc_code)
        instance.tipo = validated_data.get('tipo', instance.tipo)
        instance.opciones_cualitativas = validated_data.get(
            'opciones_cualitativas', instance.opciones_cualitativas
        )
        instance.save()
        if intervalos_data is not None:
            instance.intervalos.all().delete()
            for int_data in intervalos_data:
                IntervaloReferencia.objects.create(propiedad=instance, **int_data)
        return instance


class PlantillaSerializer(serializers.ModelSerializer):
    propiedades = PropiedadSerializer(many=True, read_only=True)

    class Meta:
        model = Plantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')


# ======================================================
# SERIALIZERS DE ANÁLISIS
# ======================================================

class ResultadoSerializer(serializers.ModelSerializer):
    """
    Serializer de LECTURA para ResultadoAnalisis.

    CORRECCIÓN BUG 1: nombre_propiedad ahora es un campo real en la BD,
    así que se puede leer y escribir directamente sin depender de @property.
    El campo se incluye explícitamente para garantizar que siempre viaja
    en la respuesta aunque sea null en registros muy antiguos.
    """
    class Meta:
        model = ResultadoAnalisis
        fields = ['id', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad']


class AnalisisSerializer(serializers.ModelSerializer):
    """
    Serializer principal de Analisis.

    ESCRITURA (POST desde la app de escritorio):
      - El cliente manda 'resultados' como lista de dicts con:
          { "nombre_propiedad": "...", "valor": "...", "unidad": "..." }
      - ids_propiedades_extra     : [int, ...]  — IDs de propiedades añadidas
      - ids_propiedades_excluidas : [int, ...]  — IDs de propiedades excluidas
      - Solo se crean los resultados que el cliente manda explícitamente.
        NO se auto-generan desde la plantilla.

    LECTURA (GET):
      - Devuelve resultados con sus IDs reales de la nube para sincronización.
    """
    resultados        = ResultadoSerializer(many=True, required=False)
    imagen_resultado1 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
    imagen_resultado2 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )

    # ─── CORRECCIÓN BUG 2 ────────────────────────────────────────────────────
    # Campos write-only para recibir IDs de propiedades extra y excluidas.
    # Son write_only porque no tienen sentido en la respuesta (ya están en los
    # M2M propiedades_extra y propiedades_excluidas del modelo).
    ids_propiedades_extra = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
        help_text="IDs de propiedades añadidas manualmente en este análisis.",
    )
    ids_propiedades_excluidas = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
        help_text="IDs de propiedades de la plantilla excluidas en este análisis.",
    )
    # ─────────────────────────────────────────────────────────────────────────

    class Meta:
        model  = Analisis
        fields = '__all__'

    def create(self, validated_data):
        """
        Crea el análisis, sus resultados y asigna los M2M de extra/excluidas.

        Regla principal: SOLO se crean los ResultadoAnalisis que el cliente
        manda en 'resultados'. Nada más. Sin auto-completar desde la plantilla.

        Para cada resultado:
          1. Buscar la Propiedad por nombre_propiedad (case-insensitive).
          2. Si no existe, crearla on-the-fly para no perder el dato.
          3. Usar get_or_create para evitar duplicados si el cliente reintenta.
          4. Guardar nombre_propiedad en el campo real de la BD (BUG 1 fix).
        """
        resultados_data       = validated_data.pop('resultados', [])

        # ─── CORRECCIÓN BUG 2: extraer los IDs de los M2M ────────────────────
        ids_extra             = validated_data.pop('ids_propiedades_extra', [])
        ids_excluidas         = validated_data.pop('ids_propiedades_excluidas', [])
        # ─────────────────────────────────────────────────────────────────────

        # Desactiva la señal post_save para que NO auto-genere resultados
        # desde la plantilla. El cliente ya manda los resultados exactos
        # (con sus exclusiones aplicadas).
        analisis = Analisis(**validated_data)
        analisis._desde_api = True
        analisis.save()

        # ─── CORRECCIÓN BUG 2: asignar M2M extra y excluidas ─────────────────
        if ids_extra:
            props_extra = Propiedad.objects.filter(id__in=ids_extra)
            analisis.propiedades_extra.set(props_extra)
            print(f"  [Serializer] propiedades_extra asignadas: {list(props_extra.values_list('id', flat=True))}")

        if ids_excluidas:
            props_excluidas = Propiedad.objects.filter(id__in=ids_excluidas)
            analisis.propiedades_excluidas.set(props_excluidas)
            print(f"  [Serializer] propiedades_excluidas asignadas: {list(props_excluidas.values_list('id', flat=True))}")
        # ─────────────────────────────────────────────────────────────────────

        for res_data in resultados_data:
            nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
            valor       = res_data.get('valor', '')
            unidad      = res_data.get('unidad', '')
            loinc       = res_data.get('loinc_code')

            # ── Resolver la FK propiedad ───────────────────────────────────
            propiedad_obj = None

            if loinc:
                try:
                    from .models import LoincCode as LC
                    lc = LC.objects.get(pk=loinc)
                    propiedad_obj = Propiedad.objects.filter(loinc_code=lc).first()
                except Exception:
                    pass

            if not propiedad_obj and nombre_prop:
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad=nombre_prop
                ).first()

            if not propiedad_obj and nombre_prop:
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad__iexact=nombre_prop
                ).first()

            if not propiedad_obj and nombre_prop:
                propiedad_obj, _ = Propiedad.objects.get_or_create(
                    nombre_propiedad=nombre_prop,
                    defaults={
                        'unidad': unidad,
                        'tipo':   'CUANTITATIVO',
                    }
                )

            if not propiedad_obj:
                print(
                    f"[AnalisisSerializer] Resultado sin nombre_propiedad ni loinc "
                    f"en analisis {analisis.id} — omitido."
                )
                continue

            # ── CORRECCIÓN BUG 1: guardar nombre en campo real de BD ──────
            nombre_para_guardar = nombre_prop or propiedad_obj.nombre_propiedad

            resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                analisis=analisis,
                propiedad=propiedad_obj,
                defaults={
                    'loinc_code':       propiedad_obj.loinc_code,
                    'nombre_propiedad': nombre_para_guardar,       # ← campo real
                    'valor':            valor,
                    'unidad':           unidad or propiedad_obj.unidad or '',
                }
            )

            if not created:
                # Reintento: actualizar valor, unidad y nombre
                resultado_obj.valor = valor
                if unidad:
                    resultado_obj.unidad = unidad
                if nombre_para_guardar:
                    resultado_obj.nombre_propiedad = nombre_para_guardar   # ← campo real
                resultado_obj.save()
            # ─────────────────────────────────────────────────────────────

        return analisis

    def update(self, instance, validated_data):
        """
        Actualización parcial: si vienen resultados o M2M, los actualiza.
        No borra los resultados existentes a menos que se envíe lista vacía.
        """
        resultados_data   = validated_data.pop('resultados', None)

        # ─── CORRECCIÓN BUG 2: actualizar M2M si vienen en el PATCH ──────────
        ids_extra     = validated_data.pop('ids_propiedades_extra', None)
        ids_excluidas = validated_data.pop('ids_propiedades_excluidas', None)
        # ─────────────────────────────────────────────────────────────────────

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Actualizar M2M solo si se enviaron en el payload
        if ids_extra is not None:
            instance.propiedades_extra.set(
                Propiedad.objects.filter(id__in=ids_extra)
            )
        if ids_excluidas is not None:
            instance.propiedades_excluidas.set(
                Propiedad.objects.filter(id__in=ids_excluidas)
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
                    # ── CORRECCIÓN BUG 1: mantener nombre sincronizado ────
                    if nombre_prop:
                        resultado_existente.nombre_propiedad = nombre_prop
                    # ─────────────────────────────────────────────────────
                    resultado_existente.save()

        return instance


# ======================================================
# PACIENTE
# ======================================================

class PacienteSerializer(serializers.ModelSerializer):
    edad            = serializers.ReadOnlyField()
    edad_en_meses   = serializers.ReadOnlyField()
    nombre_completo = serializers.ReadOnlyField()

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
