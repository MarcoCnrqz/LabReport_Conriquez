# serializers.py  (solo las partes que cambian respecto al original)
# El resto de serializers (Plantilla, Analisis, Laboratorio, etc.) permanecen igual.

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
                raise serializers.ValidationError(f"Error decodificando imagen Base64: {str(e)}")
        return super().to_internal_value(data)


# ======================================================
# SERIALIZERS DE PLANTILLAS (sin cambios)
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
        instance.nombre_propiedad = validated_data.get('nombre_propiedad', instance.nombre_propiedad)
        instance.unidad           = validated_data.get('unidad', instance.unidad)
        instance.loinc_code       = validated_data.get('loinc_code', instance.loinc_code)
        instance.tipo             = validated_data.get('tipo', instance.tipo)
        instance.opciones_cualitativas = validated_data.get('opciones_cualitativas', instance.opciones_cualitativas)
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
# SERIALIZERS DE ANÁLISIS (sin cambios)
# ======================================================

class ResultadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultadoAnalisis
        fields = ['id', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad']


class AnalisisSerializer(serializers.ModelSerializer):
    resultados        = ResultadoSerializer(many=True, required=False)
    imagen_resultado1 = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)
    imagen_resultado2 = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Analisis
        fields = '__all__'

    def create(self, validated_data):
        resultados_data = validated_data.pop('resultados', [])
        analisis = Analisis.objects.create(**validated_data)
        for res_data in resultados_data:
            nombre_prop = res_data.get('nombre_propiedad')
            loinc       = res_data.get('loinc_code')
            resultado_existente = None
            if loinc:
                resultado_existente = ResultadoAnalisis.objects.filter(
                    analisis=analisis, loinc_code=loinc
                ).first()
            if not resultado_existente and nombre_prop:
                resultado_existente = ResultadoAnalisis.objects.filter(
                    analisis=analisis, propiedad__nombre_propiedad=nombre_prop
                ).first()
            if resultado_existente:
                resultado_existente.valor  = res_data.get('valor', resultado_existente.valor)
                resultado_existente.unidad = res_data.get('unidad', resultado_existente.unidad)
                resultado_existente.save()
            else:
                ResultadoAnalisis.objects.create(analisis=analisis, **res_data)
        return analisis


# ======================================================
# PACIENTE  ← ACTUALIZADO
# ======================================================

class PacienteSerializer(serializers.ModelSerializer):
    """
    Ahora expone apellido_paterno y apellido_materno como campos propios
    del modelo, además de edad y nombre_completo calculados.
    """
    edad            = serializers.ReadOnlyField()   # property en el modelo
    edad_en_meses   = serializers.ReadOnlyField()   # property en el modelo
    nombre_completo = serializers.ReadOnlyField()   # property en el modelo

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
# LABORATORIO (sin cambios)
# ======================================================

class LaboratorioSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Laboratorio
        fields = '__all__'


# ======================================================
# USUARIO (sin cambios)
# ======================================================

class UsuarioSerializer(serializers.ModelSerializer):
    firma_digital = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Usuario
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}


# ======================================================
# LOGIN (sin cambios)
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
# BÚSQUEDA EN NUBE  ← NUEVO
# Serializer de respuesta para el endpoint buscar_nube
# ======================================================

class PacienteBusquedaNubeSerializer(serializers.ModelSerializer):
    """
    Respuesta enriquecida para búsqueda desde la app de escritorio.
    Incluye los análisis del paciente para poder importarlos junto con él.
    """
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
            'analisis',          # lista de análisis con resultados
        ]

    def get_analisis(self, obj):
        """Devuelve los análisis del paciente con sus resultados."""
        from .models import Analisis as AnalisisModel
        analisis_qs = AnalisisModel.objects.filter(paciente=obj).order_by('-fecha_analisis')
        return AnalisisSerializer(analisis_qs, many=True, context=self.context).data
