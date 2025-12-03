from rest_framework import serializers
from .models import (
    Paciente, Laboratorio, Analisis, ResultadoAnalisis,
    Plantilla, PropiedadPlantilla, IntervaloReferencia, LoincCode, Usuario
)
import base64
import uuid
from django.core.files.base import ContentFile

# ======================================================
# 🔧 UTILIDAD: CAMPO DE IMAGEN BASE64
# ======================================================
class Base64ImageField(serializers.ImageField):
    """
    Decodifica una imagen enviada en formato string Base64 (JSON)
    y la convierte en un archivo Django ImageField.
    """
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # Formato esperado: "data:image/jpeg;base64,....."
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1] # ej: jpeg
            id = uuid.uuid4()
            data = ContentFile(base64.b64decode(imgstr), name=f"{id}.{ext}")
        return super().to_internal_value(data)

# ======================================================
# 1. SERIALIZERS DE PLANTILLAS
# ======================================================

class IntervaloReferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntervaloReferencia
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion', 'propiedad')

class PropiedadPlantillaSerializer(serializers.ModelSerializer):
    intervalos = IntervaloReferenciaSerializer(many=True, required=False)
    class Meta:
        model = PropiedadPlantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

    def create(self, validated_data):
        intervalos_data = validated_data.pop('intervalos', [])
        propiedad = PropiedadPlantilla.objects.create(**validated_data)
        for intervalo_data in intervalos_data:
            IntervaloReferencia.objects.create(propiedad=propiedad, **intervalo_data)
        return propiedad
    
    def update(self, instance, validated_data):
        intervalos_data = validated_data.pop('intervalos', None)
        instance.nombre_propiedad = validated_data.get('nombre_propiedad', instance.nombre_propiedad)
        instance.unidad = validated_data.get('unidad', instance.unidad)
        instance.loinc_code = validated_data.get('loinc_code', instance.loinc_code)
        instance.save()

        if intervalos_data is not None:
            instance.intervalos.all().delete()
            for intervalo_data in intervalos_data:
                IntervaloReferencia.objects.create(propiedad=instance, **intervalo_data)
        return instance

class PlantillaSerializer(serializers.ModelSerializer):
    propiedades = PropiedadPlantillaSerializer(many=True, read_only=True)
    class Meta:
        model = Plantilla
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')

# ======================================================
# 2. SERIALIZERS DE ANÁLISIS (CORREGIDO)
# ======================================================

class ResultadoSerializer(serializers.ModelSerializer):
    valor_blob1 = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)
    valor_blob2 = Base64ImageField(max_length=None, use_url=True, required=False, allow_null=True)

    class Meta:
        model = ResultadoAnalisis
        # ⚠️ CORRECCIÓN IMPORTANTE: Se agregó 'id' a la lista de campos
        fields = ['id', 'loinc_code', 'nombre_propiedad', 'valor', 'unidad', 'valor_blob1', 'valor_blob2']

class AnalisisSerializer(serializers.ModelSerializer):
    resultados = ResultadoSerializer(many=True, required=False)

    class Meta:
        model = Analisis
        fields = '__all__'

    def create(self, validated_data):
        """
        Crea el análisis y gestiona los resultados evitando duplicados
        causados por la señal post_save.
        """
        resultados_data = validated_data.pop('resultados', [])
        
        # 1. Crear el Análisis (Esto dispara la señal en models.py que crea filas vacías)
        analisis = Analisis.objects.create(**validated_data)
        
        # 2. Procesar los resultados enviados
        for res_data in resultados_data:
            nombre_prop = res_data.get('nombre_propiedad')
            loinc = res_data.get('loinc_code')
            
            # Buscar si la señal YA creó esta fila (estará vacía)
            resultado_existente = None
            
            if loinc:
                resultado_existente = ResultadoAnalisis.objects.filter(analisis=analisis, loinc_code=loinc).first()
            
            if not resultado_existente and nombre_prop:
                resultado_existente = ResultadoAnalisis.objects.filter(analisis=analisis, nombre_propiedad=nombre_prop).first()

            # 3. Actualizar o Crear
            if resultado_existente:
                # Si existe, actualizamos los valores
                resultado_existente.valor = res_data.get('valor')
                resultado_existente.unidad = res_data.get('unidad')
                if res_data.get('valor_blob1'): resultado_existente.valor_blob1 = res_data.get('valor_blob1')
                if res_data.get('valor_blob2'): resultado_existente.valor_blob2 = res_data.get('valor_blob2')
                resultado_existente.save()
            else:
                # Si no existe, creamos una nueva
                ResultadoAnalisis.objects.create(analisis=analisis, **res_data)
            
        return analisis

# ======================================================
# 3. OTROS SERIALIZERS
# ======================================================
class LaboratorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Laboratorio
        fields = '__all__'

class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = '__all__'

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'correo_electronico', 'laboratorios']