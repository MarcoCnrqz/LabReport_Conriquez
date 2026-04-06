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
    Expone los campos que necesita la app de escritorio para sincronizar.
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
      - NO manda 'propiedad_id' porque la app local no garantiza que los IDs
        sean los mismos que en el backend. Se resuelve por nombre.
      - Solo se crean los resultados que el cliente manda explícitamente.
        NO se auto-generan resultados desde la plantilla (eso causaba que
        aparecieran propiedades excluidas por el usuario).
 
    LECTURA (GET):
      - Devuelve los resultados creados con sus IDs reales de la nube,
        para que el cliente pueda sincronizar su BD local con INSERT OR REPLACE.
    """
    resultados        = ResultadoSerializer(many=True, required=False)
    imagen_resultado1 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
    imagen_resultado2 = Base64ImageField(
        max_length=None, use_url=True, required=False, allow_null=True
    )
 
    class Meta:
        model  = Analisis
        fields = '__all__'
 
    def create(self, validated_data):
        """
        Crea el análisis y sus resultados.
 
        Regla principal: SOLO se crean los ResultadoAnalisis que el cliente
        manda en 'resultados'. Nada más. Sin auto-completar desde la plantilla.
 
        Para cada resultado:
          1. Buscar la Propiedad por nombre_propiedad (case-insensitive).
          2. Si no existe, crearla on-the-fly para no perder el dato.
          3. Usar get_or_create para evitar duplicados si el cliente reintenta.
        """
        resultados_data = validated_data.pop('resultados', [])
 
        # Desactiva la señal post_save para que NO auto-genere resultados
        # desde la plantilla. El cliente ya manda los resultados exactos
        # (con sus exclusiones aplicadas), así que la señal solo causaría
        # que aparecieran propiedades que el usuario excluyó.
        analisis = Analisis(**validated_data)
        analisis._desde_api = True   # ← guard que lee la señal en models.py
        analisis.save()
 
        for res_data in resultados_data:
            nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
            valor       = res_data.get('valor', '')
            unidad      = res_data.get('unidad', '')
            loinc       = res_data.get('loinc_code')
 
            # ── Resolver la FK propiedad ───────────────────────────
            # Primero por loinc_code si viene, luego por nombre exacto,
            # luego por nombre case-insensitive, finalmente crear.
            propiedad_obj = None
 
            if loinc:
                try:
                    from .models import LoincCode as LC
                    lc = LC.objects.get(pk=loinc)
                    propiedad_obj = Propiedad.objects.filter(loinc_code=lc).first()
                except Exception:
                    pass
 
            if not propiedad_obj and nombre_prop:
                # Búsqueda exacta primero
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad=nombre_prop
                ).first()
 
            if not propiedad_obj and nombre_prop:
                # Búsqueda case-insensitive como fallback
                propiedad_obj = Propiedad.objects.filter(
                    nombre_propiedad__iexact=nombre_prop
                ).first()
 
            if not propiedad_obj and nombre_prop:
                # Crear la propiedad si no existe — mejor que perder el dato
                propiedad_obj, _ = Propiedad.objects.get_or_create(
                    nombre_propiedad=nombre_prop,
                    defaults={
                        'unidad': unidad,
                        'tipo':   'CUANTITATIVO',
                    }
                )
 
            if not propiedad_obj:
                # nombre_prop vacío y sin loinc → saltar este resultado
                print(
                    f"[AnalisisSerializer] Resultado sin nombre_propiedad ni loinc "
                    f"en analisis {analisis.id} — omitido."
                )
                continue
 
            # ── Crear o actualizar el ResultadoAnalisis ────────────
            # get_or_create evita duplicados si el cliente reintenta la petición
            resultado_obj, created = ResultadoAnalisis.objects.get_or_create(
                analisis=analisis,
                propiedad=propiedad_obj,
                defaults={
                    'loinc_code':       propiedad_obj.loinc_code,
                    'nombre_propiedad': nombre_prop or propiedad_obj.nombre_propiedad,
                    'valor':            valor,
                    'unidad':           unidad or propiedad_obj.unidad or '',
                }
            )
 
            if not created:
                # Si ya existía (reintento), actualizar valor y unidad
                resultado_obj.valor = valor
                if unidad:
                    resultado_obj.unidad = unidad
                if nombre_prop:
                    resultado_obj.nombre_propiedad = nombre_prop
                resultado_obj.save()
 
        return analisis
 
    def update(self, instance, validated_data):
        """
        Actualización parcial: si vienen resultados, los actualiza.
        No borra los existentes a menos que se envíe una lista vacía explícita.
        """
        resultados_data = validated_data.pop('resultados', None)
 
        # Actualizar campos del análisis
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
 
        if resultados_data is not None:
            for res_data in resultados_data:
                nombre_prop = (res_data.get('nombre_propiedad') or '').strip()
                loinc       = res_data.get('loinc_code')
 
                # Buscar resultado existente
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