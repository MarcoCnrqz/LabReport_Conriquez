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

UNIDADES_SUGERIDAS = [
    'g/dL', '%',
    '×10⁶/µL', '×10⁶/mm³', '×10¹²/L',
    '×10³/µL', '/µL', '×10⁹/L',
    'mg/dL', 'U/L', 'mmol/L',
]

OPCIONES_CUALITATIVAS_SUGERIDAS = [
    'POSITIVO,NEGATIVO',
    'REACTIVO,NO REACTIVO',
    'PRESENTE,AUSENTE',
    'LEVE,MODERADO,SEVERO',
]


class UnidadConBotonWidget(forms.TextInput):
    def __init__(self, sugerencias, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sugerencias = sugerencias

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['autocomplete'] = 'off'
        attrs['placeholder'] = 'Ej: g/dL, mg/dL...'
        attrs['style'] = 'width: 220px;'

        input_html = super().render(name, value, attrs, renderer)

        opciones_html = ''.join(
            f'<div class="unidad-opcion" onclick="elegirUnidad(this, \'{name}\')" '
            f'style="padding:6px 12px;cursor:pointer;white-space:nowrap;color:#212529;background:#ffffff;">'
            f'{u}</div>'
            for u in self.sugerencias
        )

        html = f"""
        <span style="display:inline-flex;align-items:center;gap:4px;position:relative;">
            {input_html}
            <button type="button"
                title="Ver sugerencias rápidas"
                onclick="toggleUnidadDropdown(this)"
                style="
                    height:30px;padding:0 8px;cursor:pointer;
                    border:1px solid #ccc;border-radius:4px;
                    background:#f8f8f8;font-size:14px;
                    vertical-align:middle;
                ">📋</button>
            <div class="unidad-dropdown" style="
                display:none;position:absolute;top:100%;left:0;
                background:#ffffff;border:1px solid #ccc;border-radius:4px;color:#212529;
                box-shadow:0 4px 12px rgba(0,0,0,0.15);
                z-index:9999;min-width:160px;
            ">
                {opciones_html}
            </div>
        </span>
        <script>
        (function() {{
            if (window._unidadWidgetInit) return;
            window._unidadWidgetInit = true;

            function toggleUnidadDropdown(btn) {{
                var dropdown = btn.nextElementSibling;
                var isOpen = dropdown.style.display === 'block';
                document.querySelectorAll('.unidad-dropdown').forEach(function(d) {{
                    d.style.display = 'none';
                }});
                dropdown.style.display = isOpen ? 'none' : 'block';
            }}

            function elegirUnidad(opcion, fieldName) {{
                var dropdown = opcion.closest('.unidad-dropdown');
                var container = dropdown ? dropdown.parentElement : null;
                var input = container ? container.querySelector('input') : null;
                if (input) input.value = opcion.textContent.trim();
                if (dropdown) dropdown.style.display = 'none';
            }}

            document.addEventListener('click', function(e) {{
                if (!e.target.closest('.unidad-dropdown') && !e.target.closest('button[title="Ver sugerencias rápidas"]')) {{
                    document.querySelectorAll('.unidad-dropdown').forEach(function(d) {{
                        d.style.display = 'none';
                    }});
                }}
            }});

            document.addEventListener('mouseover', function(e) {{
                if (e.target.classList.contains('unidad-opcion')) {{
                    e.target.style.background = '#e8f0fe'; e.target.style.color = '#212529';
                }}
            }});
            document.addEventListener('mouseout', function(e) {{
                if (e.target.classList.contains('unidad-opcion')) {{
                    e.target.style.background = '#ffffff'; e.target.style.color = '#212529';
                }}
            }});

            window.toggleUnidadDropdown = toggleUnidadDropdown;
            window.elegirUnidad = elegirUnidad;
        }})();
        </script>
        """
        return mark_safe(html)


class OpcionesCualitativasWidget(forms.TextInput):
    def __init__(self, sugerencias, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sugerencias = sugerencias

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['autocomplete'] = 'off'
        attrs['placeholder'] = 'Ej: POSITIVO,NEGATIVO'
        attrs['style'] = 'width: 260px;'

        input_html = super().render(name, value, attrs, renderer)

        opciones_html = ''.join(
            f'<div class="cual-opcion" '
            f'onclick="elegirOpcionCualitativa(this, \'{name}\')" '
            f'style="padding:6px 12px;cursor:pointer;white-space:nowrap;color:#212529;background:#ffffff;">'
            f'{u}</div>'
            for u in self.sugerencias
        )

        html = f"""
        <span style="display:inline-flex;align-items:center;gap:4px;position:relative;">
            {input_html}
            <button type="button"
                title="Ver opciones predefinidas"
                onclick="toggleCualDropdown(this)"
                style="
                    height:30px;padding:0 8px;cursor:pointer;
                    border:1px solid #ccc;border-radius:4px;
                    background:#f8f8f8;font-size:14px;
                    vertical-align:middle;
                ">📋</button>
            <div class="cual-dropdown" style="
                display:none;position:absolute;top:100%;left:0;
                background:#ffffff;border:1px solid #ccc;border-radius:4px;color:#212529;
                box-shadow:0 4px 12px rgba(0,0,0,0.15);
                z-index:9999;min-width:220px;
            ">
                {opciones_html}
            </div>
        </span>
        <script>
        (function() {{
            if (window._cualWidgetInit) return;
            window._cualWidgetInit = true;

            function toggleCualDropdown(btn) {{
                var dropdown = btn.nextElementSibling;
                var isOpen = dropdown.style.display === 'block';
                document.querySelectorAll('.cual-dropdown').forEach(function(d) {{
                    d.style.display = 'none';
                }});
                dropdown.style.display = isOpen ? 'none' : 'block';
            }}

            function elegirOpcionCualitativa(opcion, fieldName) {{
                var dropdown = opcion.closest('.cual-dropdown');
                var container = dropdown ? dropdown.parentElement : null;
                var input = container ? container.querySelector('input') : null;
                if (input) input.value = opcion.textContent.trim();
                if (dropdown) dropdown.style.display = 'none';
            }}

            document.addEventListener('click', function(e) {{
                if (!e.target.closest('.cual-dropdown') && !e.target.closest('button[title="Ver opciones predefinidas"]')) {{
                    document.querySelectorAll('.cual-dropdown').forEach(function(d) {{
                        d.style.display = 'none';
                    }});
                }}
            }});

            document.addEventListener('mouseover', function(e) {{
                if (e.target.classList.contains('cual-opcion')) {{
                    e.target.style.background = '#e8f0fe';
                }}
            }});
            document.addEventListener('mouseout', function(e) {{
                if (e.target.classList.contains('cual-opcion')) {{
                    e.target.style.background = '#ffffff';
                }}
            }});

            window.toggleCualDropdown = toggleCualDropdown;
            window.elegirOpcionCualitativa = elegirOpcionCualitativa;
        }})();
        </script>
        """
        return mark_safe(html)


class PropiedadPlantillaForm(forms.ModelForm):
    unidad = forms.CharField(
        required=False,
        widget=UnidadConBotonWidget(sugerencias=UNIDADES_SUGERIDAS),
    )
    opciones_cualitativas = forms.CharField(
        required=False,
        widget=OpcionesCualitativasWidget(sugerencias=OPCIONES_CUALITATIVAS_SUGERIDAS),
        help_text='Opciones separadas por coma. Ej: POSITIVO,NEGATIVO',
    )

    class Meta:
        model = PropiedadPlantilla
        fields = '__all__'

    class Media:
        js = ('admin/js/propiedad_tipo_toggle.js',)


# ======================================================
# 2. FORMULARIO DE ANÁLISIS CON JS
# ======================================================

class AnalisisAdminForm(forms.ModelForm):
    class Meta:
        model = Analisis
        fields = '__all__'

    class Media:
        js = ('admin/js/analisis_imagenes_toggle.js',)


# ======================================================
# 3. FORMULARIO DINÁMICO PARA RESULTADO ANÁLISIS
# ======================================================

class ResultadoAnalisisForm(forms.ModelForm):
    """
    Formulario para ResultadoAnalisis dentro del inline de AnalisisAdmin.

    Comportamiento según el tipo de propiedad asociada:

    CUALITATIVO:
      - 'valor'  → <select> nativo con las opciones definidas en PropiedadPlantilla.
      - 'unidad' → campo deshabilitado (disabled + readonly), ya que los cualitativos
                   no tienen unidad de medida.

    CUANTITATIVO:
      - 'valor'  → input de texto libre normal.
      - 'unidad' → input de texto normal, editable.

    Como desde el admin siempre se editan análisis YA guardados (la señal
    post_save usa skip_signal=True y los ResultadoAnalisis se crean desde
    la API), _get_propiedad() siempre trabaja con instance.pk (Caso 1).
    """
    class Meta:
        model = ResultadoAnalisis
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        propiedad = self._get_propiedad()

        if propiedad and propiedad.tipo == 'CUALITATIVO':
            # --- Campo 'valor': convertir a ChoiceField con las opciones de la propiedad ---
            opciones = propiedad.get_opciones_lista()
            if opciones:
                choices = [('', '---------')] + [(op, op) for op in opciones]
                self.fields['valor'] = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label='Valor',
                )

            # --- Campo 'unidad': deshabilitar visualmente y mostrar "N/A" ---
            self.fields['unidad'].widget.attrs.update({
                'disabled': True,
                'readonly': True,
                'style': (
                    'background-color:#f0f0f0;'
                    'color:#999;'
                    'cursor:not-allowed;'
                    'border:1px solid #ddd;'
                    'border-radius:4px;'
                    'padding:2px 6px;'
                ),
                'title': 'No aplica para propiedades cualitativas',
            })
            # Mostrar "N/A" como valor visual (disabled no lo envía al servidor)
            self.initial['unidad'] = 'N/A'

    def _get_propiedad(self):
        """
        Resuelve la PropiedadPlantilla asociada a este resultado.
        Siempre trabaja desde la instancia guardada (instance.pk).
        """
        if self.instance and self.instance.pk:
            try:
                return self.instance.analisis.plantilla.propiedades.filter(
                    nombre_propiedad=self.instance.nombre_propiedad
                ).first()
            except Exception:
                return None
        return None


# ======================================================
# 4. INLINES
# ======================================================

class IntervaloReferenciaInline(admin.TabularInline):
    model = IntervaloReferencia
    extra = 1
    fields = ('edad_min_meses', 'edad_max_meses', 'sexo', 'valor_min', 'valor_max')


class PropiedadPlantillaInline(admin.TabularInline):
    model = PropiedadPlantilla
    form = PropiedadPlantillaForm
    fields = ('nombre_propiedad', 'tipo', 'unidad', 'opciones_cualitativas', 'loinc_code')
    autocomplete_fields = ('loinc_code',)
    extra = 1

    def get_extra(self, request, obj=None, **kwargs):
        if obj:
            return 0
        return 1

    def has_add_permission(self, request, obj=None):
        if obj is not None:
            return False
        return True

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            return False
        return True


class ResultadoAnalisisInline(admin.TabularInline):
    model = ResultadoAnalisis
    form = ResultadoAnalisisForm
    extra = 0
    can_delete = True
    max_num = 0

    fields = ('nombre_propiedad', 'valor', 'unidad', 'intervalo_referencia', 'valor_coloreado')
    readonly_fields = ('intervalo_referencia', 'valor_coloreado')

    def has_add_permission(self, request, obj=None):
        if obj is not None:
            return False
        return True

    def intervalo_referencia(self, obj):
        if not obj.pk or not obj.analisis or not obj.analisis.paciente:
            return "-"
        paciente   = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad  = obj.analisis.plantilla.propiedades.filter(
            nombre_propiedad=obj.nombre_propiedad
        ).first()
        if not propiedad:
            return "-"
        if propiedad.tipo == 'CUALITATIVO':
            opciones = propiedad.get_opciones_lista()
            return ', '.join(opciones) if opciones else "-"
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
    intervalo_referencia.short_description = "Referencia / Opciones"

    def valor_coloreado(self, obj):
        if not obj.pk or not obj.analisis or not obj.analisis.paciente or not obj.valor:
            return obj.valor or ""
        paciente   = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad  = obj.analisis.plantilla.propiedades.filter(
            nombre_propiedad=obj.nombre_propiedad
        ).first()
        if not propiedad:
            return obj.valor

        if propiedad.tipo == 'CUALITATIVO':
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
                    return format_html(
                        '<span style="color:red;font-weight:bold;">{} ⚠ Fuera de Rango</span>',
                        obj.valor
                    )
                return format_html('<span style="color:green;">✔ {}</span>', obj.valor)
            except ValueError:
                return obj.valor
        return obj.valor
    valor_coloreado.short_description = "Estado del Valor"


# ======================================================
# 5. REGISTRO DE MODELOS
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

    fieldsets = (
        ('Datos del Análisis', {
            'fields': ('paciente', 'plantilla', 'creado_por', 'status')
        }),
        ('Fechas y Horas', {
            'fields': ('fecha_muestra', 'hora_toma', 'hora_impresion')
        }),
        ('Imágenes del Análisis', {
            'fields': ('imagen_resultado1', 'imagen_resultado2'),
            'classes': ('seccion-imagenes-analisis',),
            'description': (
                '📷 Estas imágenes se incluirán en el reporte PDF. '
                'Solo disponibles para análisis de tipo "Imágenes y Resultados".'
            ),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('paciente', 'plantilla')
        return ()

    def save_model(self, request, obj, form, change):
        obj.skip_signal = True
        super().save_model(request, obj, form, change)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if add:
            self.message_user(
                request,
                'Atención: Una vez guardado el análisis, el Paciente y el Tipo de Análisis '
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
    list_display = ('nombre_propiedad', 'plantilla', 'tipo', 'unidad')
    autocomplete_fields = ('loinc_code', 'plantilla')
    inlines = [IntervaloReferenciaInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('tipo',)
        return ()

    class Media:
        js = ('admin/js/intervalo_toggle.js',)
