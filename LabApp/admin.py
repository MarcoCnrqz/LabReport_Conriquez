# admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.db import models
from .models import (
    Usuario, Laboratorio, Paciente, Pago, LoincCode, Analisis,
    ResultadoAnalisis, Plantilla, PropiedadPlantilla, IntervaloReferencia, Reporte
)
# Definimos las opciones agrupadas para que se vean ordenadas en el Admin
UNIDADES_CHOICES = [
    ('', '--- Seleccione una unidad ---'), # Opción vacía por defecto
    ('Hemoglobina', (
        ('g/dL', 'g/dL'),
    )),
    ('Hematocrito', (
        ('%', '%'),
    )),
    ('Eritrocitos (RBC)', (
        ('×10⁶/µL', '×10⁶/µL'),
        ('×10⁶/mm³', '×10⁶/mm³ (equivalente)'),
        ('×10¹²/L', '×10¹²/L'),
    )),
    ('Leucocitos (WBC)', (
        ('×10³/µL', '×10³/µL'),
        ('/µL', '/µL'),
        ('/mm³', '/mm³'),
        ('×10⁹/L', '×10⁹/L'),
    )),
    ('Plaquetas (PLT)', (
        ('×10³/µL', '×10³/µL'),
        ('/µL', '/µL'),
        ('×10⁹/L', '×10⁹/L'),
    )),
    ('Índices eritrocitarios', (
        ('fL', 'fL (VCM)'),
        ('pg', 'pg (HCM)'),
        ('g/dL', 'g/dL (CHCM)'),
        ('%', '% (RDW)'),
    )),
    ('Fórmula diferencial', (
        ('%', '%'),
        ('cél/µL', 'cél/µL (absolutos)'),
    )),
    ('Química / Otros', (
        ('mg/dL', 'mg/dL'),
        ('U/L', 'U/L'),
        ('mmol/L', 'mmol/L'),
    )),
]

class PropiedadPlantillaForm(forms.ModelForm):
    """Formulario para forzar el Dropdown en el Admin sin tocar models.py"""
    unidad = forms.ChoiceField(choices=UNIDADES_CHOICES, required=False, widget=forms.Select(attrs={'style': 'width: 200px;'}))
    
    class Meta:
        model = PropiedadPlantilla
        fields = '__all__'

# ==============================================================================
# 2. INLINES (Tablas dentro de otras tablas)
# ==============================================================================

class IntervaloReferenciaInline(admin.TabularInline):
    model = IntervaloReferencia
    extra = 1

class PropiedadPlantillaInline(admin.TabularInline):
    model = PropiedadPlantilla
    form = PropiedadPlantillaForm  # <--- AQUI APLICAMOS EL DROPDOWN
    fields = ('nombre_propiedad', 'unidad', 'loinc_code')
    autocomplete_fields = ('loinc_code',)
    extra = 1

class ResultadoAnalisisInline(admin.TabularInline):
    model = ResultadoAnalisis
    extra = 0
    autocomplete_fields = ['loinc_code']
    # Agregamos las vistas previas de las imágenes aquí
    fields = ('nombre_propiedad', 'valor', 'unidad', 'valor_blob1', 'preview_img1', 'valor_blob2', 'preview_img2', 'intervalo_referencia', 'valor_coloreado')
    readonly_fields = ('intervalo_referencia', 'valor_coloreado', 'preview_img1', 'preview_img2')

    def preview_img1(self, obj):
        if obj.valor_blob1:
            return format_html('<img src="{}" style="height: 50px; border-radius: 5px;" />', obj.valor_blob1.url)
        return "-"
    preview_img1.short_description = "Img 1"

    def preview_img2(self, obj):
        if obj.valor_blob2:
            return format_html('<img src="{}" style="height: 50px; border-radius: 5px;" />', obj.valor_blob2.url)
        return "-"
    preview_img2.short_description = "Img 2"

    def intervalo_referencia(self, obj):
        """Muestra el rango de referencia según paciente"""
        if not obj.analisis or not obj.analisis.paciente: return "-"
        paciente = obj.analisis.paciente
        
        # Lógica simplificada de edad
        if paciente.edad <= 18: grupo_edad = "NINO"
        elif paciente.edad <= 59: grupo_edad = "ADULTO"
        else: grupo_edad = "ADULTO_MAYOR"

        propiedad = obj.analisis.plantilla.propiedades.filter(nombre_propiedad=obj.nombre_propiedad).first()
        if not propiedad: return "-"
        
        intervalo = propiedad.intervalos.filter(grupo_edad=grupo_edad).filter(
            models.Q(sexo=paciente.sexo) | models.Q(sexo="AMBOS")
        ).first()

        if intervalo:
            return f"{intervalo.valor_min} - {intervalo.valor_max} {obj.unidad or ''}"
        return "-"
    intervalo_referencia.short_description = "Rango Ref."

    def valor_coloreado(self, obj):
        """Muestra el valor con color según esté dentro o fuera del rango"""
        paciente = obj.analisis.paciente
        if paciente.edad <= 18: grupo_edad = "NINO"
        elif paciente.edad <= 59: grupo_edad = "ADULTO"
        else: grupo_edad = "ADULTO_MAYOR"

        propiedad = obj.analisis.plantilla.propiedades.filter(nombre_propiedad=obj.nombre_propiedad).first()
        if not propiedad: return obj.valor or ""

        intervalo = propiedad.intervalos.filter(grupo_edad=grupo_edad).filter(
            models.Q(sexo=paciente.sexo) | models.Q(sexo="AMBOS")
        ).first()

        if intervalo and obj.valor:
            try:
                valor = float(obj.valor)
                if valor < intervalo.valor_min or valor > intervalo.valor_max:
                    color = "red"
                    weight = "bold"
                else:
                    color = "green"
                    weight = "normal"
                return format_html('<span style="color:{}; font-weight:{};">{}</span>', color, weight, obj.valor)
            except ValueError:
                return obj.valor 
        return obj.valor
    valor_coloreado.short_description = "Estado"


# ==============================================================================
# 3. ADMINS PRINCIPALES
# ==============================================================================

@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_formato')
    search_fields = ('titulo',)
    list_filter = ('tipo_formato',)
    inlines = [PropiedadPlantillaInline]
    
    # --- CAMBIO REALIZADO: Eliminada la pestaña de Receta Justificada ---
    # Solo mostramos los campos generales
    fieldsets = (
        (None, {'fields': ('titulo', 'tipo_formato')}),
    )
    # Excluimos explícitamente el campo por seguridad visual
    exclude = ('texto_justificado_default',)

@admin.register(PropiedadPlantilla)
class PropiedadPlantillaAdmin(admin.ModelAdmin):
    form = PropiedadPlantillaForm # <--- AQUI TAMBIÉN APLICAMOS EL DROPDOWN
    list_display = ('nombre_propiedad', 'plantilla', 'unidad')
    search_fields = ('nombre_propiedad', 'plantilla__titulo')
    list_filter = ('plantilla', 'unidad') # Ahora se puede filtrar por unidad
    autocomplete_fields = ('loinc_code',)
    inlines = [IntervaloReferenciaInline]

@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'plantilla', 'fecha_analisis')
    search_fields = ('paciente__nombre', 'plantilla__titulo')
    list_filter = ('plantilla', 'fecha_analisis')
    inlines = [ResultadoAnalisisInline]
    raw_id_fields = ('paciente', 'plantilla')

# ==============================================================================
# 4. GESTIÓN DE USUARIOS
# ==============================================================================
class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = '__all__'
        widgets = {'password': forms.PasswordInput(render_value=True)}

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    form = UsuarioForm
    list_display = ('id', 'nombre', 'correo_electronico', 'num_telefono', 'is_active')
    search_fields = ('nombre', 'correo_electronico', 'laboratorios__nombre_laboratorio')
    filter_horizontal = ('laboratorios',)

    def save_model(self, request, obj, form, change):
        # Encriptar contraseña si se cambió desde el formulario
        if form.cleaned_data.get('password') and ('password' in form.changed_data or not change):
             obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)

@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_laboratorio', 'ciudad', 'logo_thumbnail')
    search_fields = ('nombre_laboratorio', 'ciudad')

    def logo_thumbnail(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 50%;" />', obj.logo.url)
        return "-"
    logo_thumbnail.short_description = 'Logo'

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'edad', 'sexo', 'laboratorio', 'telefono')
    search_fields = ('nombre', 'laboratorio__nombre_laboratorio')
    list_filter = ('sexo', 'laboratorio')

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'fecha_pago', 'fecha_vencimiento', 'estado')
    list_filter = ('estado', 'fecha_pago')
    search_fields = ('usuario__nombre',)

@admin.register(LoincCode)
class LoincCodeAdmin(admin.ModelAdmin):
    list_display = ('loinc_num', 'shortname', 'component')
    search_fields = ('loinc_num', 'shortname', 'component')
    ordering = ('loinc_num',)

# ==============================================================================
# 5. REPORTE
# ==============================================================================
@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("id", "analisis", "paciente_info", "generado_por", "fecha_generacion", "ver_pdf")
    list_filter = ("fecha_generacion",)
    search_fields = ("analisis__paciente__nombre", "generado_por__nombre")
    
    def paciente_info(self, obj):
        return obj.analisis.paciente.nombre if obj.analisis and obj.analisis.paciente else "-"
    paciente_info.short_description = "Paciente"

    def ver_pdf(self, obj):
        if obj.analisis:
            return format_html(
                '<a class="button" style="background-color:#2ecc71;color:white;padding:3px 8px;border-radius:4px;text-decoration:none;" '
                'href="/reporte/{}/pdf/" target="_blank">🖨️ Ver PDF</a>', obj.analisis.id
            )
        return "-"
    ver_pdf.short_description = "Acción"