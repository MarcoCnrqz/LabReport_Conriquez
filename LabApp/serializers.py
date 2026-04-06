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
 
    nombre_propiedad es un campo real en la BD, se lee y escribe
    directamente. Se incluye explícitamente para garantizar que
    siempre viaja en la respuesta.
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
      - nombres_propiedades_extra     : ["Glucosa", ...]  — nombres de propiedades añadidas
      - nombres_propiedades_excluidas : ["Hemoglobina", ...]  — nombres de propiedades excluidas
 
      Se usan NOMBRES en lugar de IDs porque los IDs de la BD local SQLite
      no necesariamente coinciden con los IDs de la BD en la nube. Los nombres
      son únicos (unique_together en Propiedad.nombre_propiedad) y siempre
      coinciden entre ambas BDs ya que se sincronizan desde la nube.
 
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
 
    # ─── FIX: campos write-only con NOMBRES en lugar de IDs ──────────────────
    # Los IDs de SQLite local no coinciden con los IDs de Django en la nube.
    # Al usar nombres (que son únicos) el lookup siempre funciona
    # independientemente de si los IDs coinciden o no.
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
          4. Guardar nombre_propiedad en el campo real de la BD.
        """
        resultados_data = validated_data.pop('resultados', [])
 
        # ─── FIX: extraer nombres (no IDs) de los M2M ────────────────────────
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', [])
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', [])
        # ─────────────────────────────────────────────────────────────────────
 
        # Desactiva la señal post_save para que NO auto-genere resultados
        # desde la plantilla. El cliente ya manda los resultados exactos.
        analisis = Analisis(**validated_data)
        analisis._desde_api = True
        analisis.save()
 
        # ─── FIX: asignar M2M buscando por nombre_propiedad ──────────────────
        if nombres_extra:
            props_extra = Propiedad.objects.filter(nombre_propiedad__in=nombres_extra)
            analisis.propiedades_extra.set(props_extra)
            encontrados = list(props_extra.values_list('nombre_propiedad', flat=True))
            no_encontrados = [n for n in nombres_extra if n not in encontrados]
            print(f"  [Serializer] propiedades_extra asignadas : {encontrados}")
            if no_encontrados:
                print(f"  [Serializer] propiedades_extra NO encontradas: {no_encontrados}")
 
        if nombres_excluidas:
            props_excluidas = Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
            analisis.propiedades_excluidas.set(props_excluidas)
            encontrados = list(props_excluidas.values_list('nombre_propiedad', flat=True))
            no_encontrados = [n for n in nombres_excluidas if n not in encontrados]
            print(f"  [Serializer] propiedades_excluidas asignadas : {encontrados}")
            if no_encontrados:
                print(f"  [Serializer] propiedades_excluidas NO encontradas: {no_encontrados}")
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
        """
        Actualización parcial: si vienen resultados o M2M, los actualiza.
        No borra los resultados existentes a menos que se envíe lista vacía.
        """
        resultados_data = validated_data.pop('resultados', None)
 
        # ─── FIX: actualizar M2M por nombre si vienen en el PATCH ────────────
        nombres_extra     = validated_data.pop('nombres_propiedades_extra', None)
        nombres_excluidas = validated_data.pop('nombres_propiedades_excluidas', None)
        # ─────────────────────────────────────────────────────────────────────
 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
 
        # Actualizar M2M solo si se enviaron en el payload
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