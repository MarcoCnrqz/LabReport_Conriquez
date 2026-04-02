from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, Propiedad, IntervaloReferencia, LoincCode, Usuario
)
import base64
import uuid
from django.core.files.base import ContentFile

# ======================================================
# 🔧 UTILIDAD: CAMPO DE IMAGEN BASE64
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
# 1. SERIALIZERS DE PLANTILLAS
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
    # M2M — propiedades anidadas de solo lectura
    propiedades = PropiedadSerializer(many=True, read_only=True)

    class Meta:
        model = Plantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

# ======================================================
# 2. SERIALIZERS DE ANÁLISIS
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
                resultado_existente.valor = res_data.get('valor', resultado_existente.valor)
                resultado_existente.unidad = res_data.get('unidad', resultado_existente.unidad)
                resultado_existente.save()
            else:
                ResultadoAnalisis.objects.create(analisis=analisis, **res_data)

        return analisis

# ======================================================
# 3. OTROS SERIALIZERS
# ======================================================

class LaboratorioSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Laboratorio
        fields = '__all__'


class PacienteSerializer(serializers.ModelSerializer):
    edad            = serializers.ReadOnlyField()
    edad_en_meses   = serializers.ReadOnlyField()
    nombre_completo = serializers.ReadOnlyField()

    class Meta:
        model  = Paciente
        fields = '__all__'


class UsuarioSerializer(serializers.ModelSerializer):
    firma_digital = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model  = Usuario
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

# ======================================================
# 4. SERIALIZERS DE LOGIN (app de escritorio)
# ======================================================

class LoginSerializer(serializers.Serializer):
    """Valida el body del POST /api/login/"""
    correo   = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UsuarioLoginResponseSerializer(serializers.ModelSerializer):
    """
    Respuesta del endpoint /api/login/.
    Expone solo los campos que la app Python/Tkinter consume.
    'correo' se mapea desde correo_electronico para que el cliente
    lo lea como data.get("correo").
    """
    correo = serializers.EmailField(source='correo_electronico')

    class Meta:
        model  = Usuario
        fields = [
            'id',
            'nombre',
            'correo',           # ← mapeado desde correo_electronico
            'rol',
            'puesto',
            'titulo_abreviado',
            'cedula_profesional',
            'is_active',
        ]


class MiLaboratorioResponseSerializer(serializers.ModelSerializer):
    """
    Respuesta del endpoint GET /api/mi_laboratorio/?usuario_id=X
    Devuelve los datos del laboratorio al que pertenece el usuario,
    incluyendo la URL absoluta del logo para que la app pueda descargarlo.
    """
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model  = Laboratorio
        fields = [
            'id',
            'nombre_laboratorio',
            'ciudad',
            'estado',
            'logo_url',
        ]

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None
