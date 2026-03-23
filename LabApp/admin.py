from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.db.models import Q
from django.utils.safestring import mark_safe
from .models import (
    Usuario, Laboratorio, Paciente, LoincCode, Analisis,
    ResultadoAnalisis, Plantilla, PropiedadPlantilla, IntervaloReferencia
)

# ======================================================
# 1. CONFIGURACIÓN DE FORMULARIOS Y UNIDADES
# ======================================================

UNIDADES_CHOICES = [
    ('', '--- Seleccione una unidad ---'),
    ('Hemoglobina', (('g/dL', 'g/dL'),)),
    ('Hematocrito', (('%', '%'),)),
    ('Eritrocitos (RBC)', (
        ('×10⁶/µL', '×10⁶/µL'),
        ('×10⁶/mm³', '×10⁶/mm³'),
        ('×10¹²/L', '×10¹²/L'),
    )),
    ('Leucocitos (WBC)', (
        ('×10³/µL', '×10³/µL'),
        ('/µL', '/µL'),
        ('×10⁹/L', '×10⁹/L'),
    )),
    ('Plaquetas (PLT)', (
        ('×10³/µL', '×10³/µL'),
        ('×10⁹/L', '×10⁹/L'),
    )),
    ('Química / Otros', (
        ('mg/dL', 'mg/dL'),
        ('U/L', 'U/L'),
        ('mmol/L', 'mmol/L'),
    )),
]

class PropiedadPlantillaForm(forms.ModelForm):
    unidad = forms.ChoiceField(
        choices=UNIDADES_CHOICES, required=False,
        widget=forms.Select(attrs={'style': 'width: 250px;'})
    )
    class Meta:
        model = PropiedadPlantilla
        fields = '__all__'


# ======================================================
# 2. FORMULARIO DE ANÁLISIS CON JS PARA IMÁGENES
# ======================================================

class AnalisisAdminForm(forms.ModelForm):
    class Meta:
        model = Analisis
        fields = '__all__'

    class Media:
        # ✅ JS inline: muestra/oculta el bloque de imágenes según tipo de plantilla
        js = ('admin/js/analisis_imagenes_toggle.js',)


# ======================================================
# 3. INLINES
# ======================================================

class IntervaloReferenciaInline(admin.TabularInline):
    model = IntervaloReferencia
    extra = 1
    fields = ('edad_min_meses', 'edad_max_meses', 'sexo', 'valor_min', 'valor_max')

class PropiedadPlantillaInline(admin.TabularInline):
    model = PropiedadPlantilla
    form = PropiedadPlantillaForm
    fields = ('nombre_propiedad', 'unidad', 'loinc_code')
    autocomplete_fields = ('loinc_code',)
    extra = 1

class ResultadoAnalisisInline(admin.TabularInline):
    model = ResultadoAnalisis
    extra = 0
    autocomplete_fields = ['loinc_code']
    # ✅ Sin columnas de imagen — las imágenes ahora están en el Analisis principal
    fields = ('nombre_propiedad', 'valor', 'unidad', 'intervalo_referencia', 'valor_coloreado')
    readonly_fields = ('intervalo_referencia', 'valor_coloreado')

    def intervalo_referencia(self, obj):
        if not obj.analisis or not obj.analisis.paciente:
            return "-"
        paciente = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad = obj.analisis.plantilla.propiedades.filter(nombre_propiedad=obj.nombre_propiedad).first()
        if not propiedad:
            return "-"
        intervalo = propiedad.intervalos.filter(
            Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
        ).filter(
            Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
        ).filter(
            Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
        ).first()
        if intervalo:
            return f"{intervalo.valor_min} - {intervalo.valor_max} {obj.unidad or ''}"
        return "-"
    intervalo_referencia.short_description = "Intervalo de Referencia"

    def valor_coloreado(self, obj):
        if not obj.analisis or not obj.analisis.paciente or not obj.valor:
            return obj.valor or ""
        paciente = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad = obj.analisis.plantilla.propiedades.filter(nombre_propiedad=obj.nombre_propiedad).first()
        if not propiedad:
            return obj.valor
        intervalo = propiedad.intervalos.filter(
            Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
        ).filter(
            Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
        ).filter(
            Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
        ).first()
        if intervalo and obj.valor:
            try:
                valor = float(obj.valor)
                if valor < intervalo.valor_min or valor > intervalo.valor_max:
                    return format_html('<span style="color:red;font-weight:bold;">{} ⚠ Fuera de Rango</span>', obj.valor)
                return format_html('<span style="color:green;">✔ {}</span>', obj.valor)
            except ValueError:
                return obj.valor
        return obj.valor
    valor_coloreado.short_description = "Estado del Valor"


# ======================================================
# 4. REGISTRO DE MODELOS
# ======================================================

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'correo_electronico', 'rol', 'puesto', 'cedula_profesional', 'is_active')
    list_filter = ('rol', 'is_active')
    search_fields = ('nombre', 'correo_electronico', 'cedula_profesional')
    filter_horizontal = ('laboratorios',)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['password'].widget = forms.PasswordInput(render_value=True)
        return form

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('password') and ('password' in form.changed_data or not change):
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ('nombre_laboratorio', 'ciudad', 'responsable_sanitario_principal')
    search_fields = ('nombre_laboratorio', 'ciudad')


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'apellido_paterno', 'apellido_materno')
    list_display = ('id', 'nombre_completo', 'sexo', 'get_edad', 'laboratorio')
    list_filter = ('sexo', 'laboratorio')
    
    def get_edad(self, obj):
        años = obj.edad
        meses = obj.edad_en_meses
        if años < 2:
            return f"{meses} meses"
        return f"{años} años"
    get_edad.short_description = "Edad"


@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    form = AnalisisAdminForm
    list_display = ('id', 'get_paciente', 'get_plantilla', 'status', 'creado_por', 'fecha_analisis', 'link_pdf')
    list_filter = ('status', 'plantilla', 'fecha_analisis')
    search_fields = ('paciente__nombre', 'paciente__apellido_paterno', 'plantilla__titulo')
    autocomplete_fields = ('paciente', 'plantilla', 'creado_por')
    inlines = [ResultadoAnalisisInline]

    # ✅ Campos organizados en secciones — imágenes en sección propia con id para el JS
    fieldsets = (
        ('Datos del Análisis', {
            'fields': ('paciente', 'plantilla', 'creado_por', 'status')
        }),
        ('Fechas y Horas', {
            'fields': ('fecha_muestra', 'hora_toma', 'hora_impresion')
        }),
        # ✅ Sección de imágenes — el JS la muestra u oculta según tipo de plantilla
        ('Imágenes del Análisis', {
            'fields': ('imagen_resultado1', 'imagen_resultado2'),
            'classes': ('seccion-imagenes-analisis',),
            'description': (
                '📷 Estas imágenes se incluirán en el reporte PDF. '
                'Solo disponibles para análisis de tipo "Imágenes y Resultados".'
            ),
        }),
    )

    # ✅ Bloquear paciente y plantilla una vez guardado el análisis
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Edición
            return ('paciente', 'plantilla')
        return ()

    # ✅ Mensaje de advertencia visible al crear un nuevo análisis
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if add:
            self.message_user(
                request,
                '⚠️ Atención: Una vez guardado el análisis, el Paciente y el Tipo de Análisis '
                '(Plantilla) no podrán modificarse. Verifique bien antes de guardar.',
                level='warning'
            )
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def get_paciente(self, obj):
        return obj.paciente.nombre_completo
    get_paciente.short_description = "Paciente"

    def get_plantilla(self, obj):
        return obj.plantilla.titulo if obj.plantilla else "-"
    get_plantilla.short_description = "Plantilla"

    def link_pdf(self, obj):
        if obj.id:
            return format_html(
                '<a class="button" style="background-color:#2ecc71;color:white;padding:5px 10px;'
                'border-radius:5px;text-decoration:none;" '
                'href="/admin_ext/analisis/{}/generar_pdf/" target="_blank">📄 Ver PDF</a>',
                obj.id
            )
        return "-"
    link_pdf.short_description = "Reporte"


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    search_fields = ('titulo',)
    list_display = ('titulo', 'tipo_formato', 'fecha_modificacion')
    inlines = [PropiedadPlantillaInline]


@admin.register(LoincCode)
class LoincCodeAdmin(admin.ModelAdmin):
    search_fields = ('loinc_num', 'shortname', 'component')
    list_display = ('loinc_num', 'shortname', 'component', 'system')


@admin.register(PropiedadPlantilla)
class PropiedadPlantillaAdmin(admin.ModelAdmin):
    form = PropiedadPlantillaForm
    list_display = ('nombre_propiedad', 'plantilla', 'unidad')
    autocomplete_fields = ('loinc_code', 'plantilla')
    inlines = [IntervaloReferenciaInline]
