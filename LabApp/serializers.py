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
 
# FIX: IntervaloReferenciaSerializer — se quita 'propiedad' de read_only_fields
# porque en PropiedadSerializer.create/update se crea el intervalo pasando
# propiedad=instance directamente (no via payload), así que no hay conflicto.
# Pero sí debe estar excluido del campo 'fields' cuando se anida dentro de
# PropiedadSerializer, porque ya se asigna por código. Se deja '__all__' para
# que el endpoint /api/intervalos/ siga funcionando completo de forma independiente.
class IntervaloReferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = IntervaloReferencia
        fields = '__all__'
        # FIX: 'propiedad' se marca read_only para que cuando este serializer
        # llega ANIDADO dentro de PropiedadSerializer (sin el campo 'propiedad'
        # en el payload), la validación no falle con "Este campo es requerido."
        # En create/update de PropiedadSerializer se asigna propiedad=instance
        # directamente por código, por lo que no se necesita en el payload.
        # El endpoint independiente /api/intervalos/ sigue funcionando igual
        # porque al asignar vía PUT/PATCH directo la FK se pasa explícitamente.
        read_only_fields = ('sincronizado', 'fecha_modificacion', 'propiedad')
 
 
class PropiedadSerializer(serializers.ModelSerializer):
    # FIX: 'intervalos' anidado — required=False para que POST sin intervalos
    # (propiedades cualitativas) no falle validación.
    intervalos = IntervaloReferenciaSerializer(many=True, required=False)
 
    class Meta:
        model  = Propiedad
        fields = '__all__'
        read_only_fields = ('sincronizado', 'fecha_modificacion')
 
    def create(self, validated_data):
        intervalos_data = validated_data.pop('intervalos', [])
        propiedad = Propiedad.objects.create(**validated_data)
        for int_data in intervalos_data:
            # FIX: quitar 'propiedad' del dict si viene por error desde el cliente,
            # porque ya se asigna explícitamente abajo.
            int_data.pop('propiedad', None)
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
                # FIX: ídem — descartar 'propiedad' si viene en el payload.
                int_data.pop('propiedad', None)
                IntervaloReferencia.objects.create(propiedad=instance, **int_data)
        return instance
 
 
class PlantillaSerializer(serializers.ModelSerializer):
    # LECTURA: propiedades completas con tipo, opciones_cualitativas e intervalos.
    # Esto garantiza que la app local reciba todo lo necesario para sincronizar
    # propiedades cuantitativas Y cualitativas desde un solo endpoint.
    propiedades = PropiedadSerializer(many=True, read_only=True)
 
    # Campo write-only para asignar M2M desde POST/PATCH.
    # El controller local manda los remote_id (PKs de Django) de cada propiedad.
    # create() y update() lo procesan correctamente.
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
        # FIX: El modelo Plantilla en Django solo acepta 'RESULTADOS' e
        # 'IMAGENES_RESULTADOS'. Si la app local manda 'RECETA_JUSTIFICADA',
        # se convierte a 'RESULTADOS' en lugar de fallar con un 400 silencioso,
        # y se loguea para que el desarrollador lo detecte.
        # NOTA: si en el futuro se agrega RECETA_JUSTIFICADA al modelo Django,
        # simplemente se puede eliminar este método validate_.
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
            # Log de advertencia si algún ID no se encontró
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
        # Solo actualiza M2M si se envió el campo (permite PATCH parcial).
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
    """
    resultados        = ResultadoSerializer(many=True, required=False)
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
 