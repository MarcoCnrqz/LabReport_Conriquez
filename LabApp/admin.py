from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.db.models import Q
from django.utils.safestring import mark_safe
 
from .models import (
    Usuario, Laboratorio, Paciente, LoincCode,
    Propiedad, IntervaloReferencia, Plantilla,
    Analisis, ResultadoAnalisis,
)
 
 
# =============================================================================
# 1. LISTAS DE SUGERENCIAS
# =============================================================================
 
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
 
TIPOS_MUESTRA_SUGERIDOS = [
    'Sangre total con EDTA',
    'Suero',
    'Plasma con citrato',
    'Orina de 24h',
    'Orina aleatoria',
    'Líquido cefalorraquídeo',
    'Heces',
    'Exudado faríngeo',
]
 
METODOS_SUGERIDOS = [
    'Impedancia eléctrica y microscópica',
    'Espectrofotometría',
    'Aglutinación',
    'Inmunoturbidimetría',
    'Electroquimioluminiscencia',
    'Fluorescencia',
    'Cultivo microbiológico',
    'PCR',
]
 
 
# =============================================================================
# 2. WIDGET BASE CON DROPDOWN DE SUGERENCIAS
# =============================================================================
 
class SugerenciasDropdownWidget(forms.TextInput):
    """
    Widget TextInput con un botón 📋 que despliega un dropdown de sugerencias.
    Al hacer clic en una sugerencia, se escribe en el input automáticamente.
    """
 
    def __init__(self, sugerencias, placeholder='', input_width='240px', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sugerencias   = sugerencias
        self.placeholder   = placeholder
        self.input_width   = input_width
 
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['autocomplete'] = 'off'
        attrs['placeholder']  = self.placeholder
        attrs['style']        = f'width:{self.input_width};vertical-align:middle;'
 
        dropdown_id = f'dd_{name}'
        input_html  = super().render(name, value, attrs, renderer)
 
        items_html = ''.join(
            f'<div class="sdw-item" onclick="sdwElegir(\'{dropdown_id}\', this)">'
            f'{item}'
            f'</div>'
            for item in self.sugerencias
        )
 
        html = f"""
<style id="sdw-style" data-sdw-once>
  .sdw-wrap {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    vertical-align: middle;
  }}
  .sdw-btn {{
    height: 30px;
    padding: 0 8px;
    font-size: 15px;
    cursor: pointer;
    border: 1px solid #bbb;
    border-radius: 4px;
    background: #f5f5f5;
    vertical-align: middle;
    line-height: 1;
    transition: background 0.15s, border-color 0.15s;
    user-select: none;
  }}
  .sdw-btn:hover {{
    background: #e0e8ff;
    border-color: #7a9fe0;
  }}
  .sdw-menu {{
    display: none;
    position: fixed;
    z-index: 999999;
    background: #fff;
    border: 1px solid #bbb;
    border-radius: 6px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.22);
    min-width: 210px;
    max-height: 260px;
    overflow-y: auto;
  }}
  .sdw-item {{
    padding: 8px 14px;
    font-size: 13px;
    cursor: pointer;
    color: #222;
    white-space: nowrap;
    transition: background 0.1s;
  }}
  .sdw-item:hover {{
    background: #e8f0fe;
  }}
</style>
 
<script>
(function() {{
  if (window._sdwReady) return;
  window._sdwReady = true;
 
  window.sdwToggle = function(btn, menuId) {{
    var menu = document.getElementById(menuId);
    if (!menu) return;
    var isOpen = menu.style.display === 'block';
 
    document.querySelectorAll('.sdw-menu').forEach(function(m) {{
      m.style.display = 'none';
    }});
 
    if (!isOpen) {{
      var rect       = btn.getBoundingClientRect();
      var menuHeight = 260;
      var spaceBelow = window.innerHeight - rect.bottom;
      var spaceAbove = rect.top;
 
      menu.style.display = 'block';
      var realHeight = Math.min(menu.scrollHeight, menuHeight);
      menu.style.display = 'none';
 
      if (spaceAbove >= realHeight || spaceAbove > spaceBelow) {{
        menu.style.top = (rect.top - realHeight - 4) + 'px';
      }} else {{
        menu.style.top = (rect.bottom + 4) + 'px';
      }}
      menu.style.left   = rect.left + 'px';
      menu.style.width  = Math.max(rect.width + 36, 210) + 'px';
      menu.style.display = 'block';
    }}
  }};
 
  ['scroll','resize'].forEach(function(ev) {{
    window.addEventListener(ev, function() {{
      document.querySelectorAll('.sdw-menu').forEach(function(m) {{
        m.style.display = 'none';
      }});
    }}, true);
  }});
 
  window.sdwElegir = function(menuId, item) {{
    var menu = document.getElementById(menuId);
    if (!menu) return;
    var inputId = menu.dataset.for;
    var input   = inputId ? document.getElementById(inputId) : null;
    if (input) {{
      input.value = item.textContent.trim();
      input.dispatchEvent(new Event('input',  {{bubbles: true}}));
      input.dispatchEvent(new Event('change', {{bubbles: true}}));
    }}
    menu.style.display = 'none';
  }};
 
  document.addEventListener('click', function(e) {{
    if (!e.target.closest('.sdw-btn') && !e.target.closest('.sdw-menu')) {{
      document.querySelectorAll('.sdw-menu').forEach(function(m) {{
        m.style.display = 'none';
      }});
    }}
  }});
}})();
</script>
 
<span class="sdw-wrap">
  {input_html}
  <button type="button"
          class="sdw-btn"
          title="Ver sugerencias"
          onclick="sdwToggle(this, '{dropdown_id}')">📋</button>
</span>
<div id="{dropdown_id}" class="sdw-menu" data-for="id_{name}">
  {items_html}
</div>
"""
        return mark_safe(html)
 
 
# =============================================================================
# 3. FORMULARIOS
# =============================================================================
 
class PropiedadForm(forms.ModelForm):
    unidad = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=UNIDADES_SUGERIDAS,
            placeholder='Ej: g/dL, mg/dL...',
            input_width='220px',
        ),
    )
    opciones_cualitativas = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=OPCIONES_CUALITATIVAS_SUGERIDAS,
            placeholder='Ej: POSITIVO,NEGATIVO',
            input_width='260px',
        ),
        help_text='Opciones separadas por coma. Ej: POSITIVO,NEGATIVO',
    )
 
    class Meta:
        model  = Propiedad
        fields = '__all__'
 
    class Media:
        js = ('admin/js/propiedad_tipo_toggle.js',)
 
 
class AnalisisAdminForm(forms.ModelForm):
    tipo_muestra = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=TIPOS_MUESTRA_SUGERIDOS,
            placeholder='Ej: Sangre total con EDTA, Suero...',
            input_width='260px',
        ),
        label='Tipo de muestra',
        help_text='Ej: Sangre total con EDTA, Suero, Orina de 24h',
    )
    metodo = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=METODOS_SUGERIDOS,
            placeholder='Ej: Impedancia eléctrica, Aglutinación...',
            input_width='260px',
        ),
        label='Método',
        help_text='Ej: Impedancia eléctrica y microscópica, Espectrofotometría',
    )
 
    class Meta:
        model  = Analisis
        fields = '__all__'
 
    class Media:
        js = ('admin/js/analisis_imagenes_toggle.js',)
 
 
class ResultadoAnalisisForm(forms.ModelForm):
    class Meta:
        model  = ResultadoAnalisis
        fields = '__all__'
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        propiedad = self._get_propiedad()
 
        if propiedad and propiedad.tipo == 'CUALITATIVO':
            opciones = propiedad.get_opciones_lista()
            if opciones:
                choices = [('', '---------')] + [(op, op) for op in opciones]
                self.fields['valor'] = forms.ChoiceField(
                    choices=choices, required=False, label='Valor',
                )
            self.fields['unidad'].widget.attrs.update({
                'disabled': True,
                'readonly': True,
                'style': (
                    'background-color:#f0f0f0;color:#999;cursor:not-allowed;'
                    'border:1px solid #ddd;border-radius:4px;padding:2px 6px;'
                ),
                'title': 'No aplica para propiedades cualitativas',
            })
            self.initial['unidad'] = 'N/A'
 
    def _get_propiedad(self):
        if self.instance and self.instance.pk:
            try:
                return self.instance.propiedad
            except Exception:
                return None
        return None
 
 
# =============================================================================
# 4. INLINES
# =============================================================================
 
class IntervaloReferenciaInline(admin.TabularInline):
    model  = IntervaloReferencia
    extra  = 1
    fields = ('edad_min_meses', 'edad_max_meses', 'sexo', 'valor_min', 'valor_max')
 
 
class ResultadoAnalisisInline(admin.TabularInline):
    model      = ResultadoAnalisis
    form       = ResultadoAnalisisForm
    extra      = 0
    can_delete = True
 
    fields          = ('propiedad', 'nombre_propiedad', 'valor', 'unidad',
                       'col_intervalo_referencia', 'col_valor_coloreado')
    readonly_fields = ('propiedad', 'nombre_propiedad',
                       'col_intervalo_referencia', 'col_valor_coloreado')
 
    def get_max_num(self, request, obj=None, **kwargs):
        if obj is None:
            return None
        return obj.resultados.count()
 
    def has_add_permission(self, request, obj=None):
        return obj is None
 
    def _esta_excluida(self, obj):
        """Devuelve True si la propiedad de este resultado está en propiedades_excluidas."""
        if not obj.pk or not obj.analisis:
            return False
        return obj.analisis.propiedades_excluidas.filter(pk=obj.propiedad_id).exists()
 
    def col_intervalo_referencia(self, obj):
        # Si está excluida mostramos indicador gris en lugar de la referencia
        if self._esta_excluida(obj):
            return format_html(
                '<span style="color:#aaa;font-style:italic;">— Excluida —</span>'
            )
        if not obj.pk or not obj.analisis or not obj.analisis.paciente:
            return "-"
        paciente   = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad  = obj.propiedad
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
    col_intervalo_referencia.short_description = "Referencia / Opciones"
 
    def col_valor_coloreado(self, obj):
        # Si está excluida: badge gris con candado, no aparecerá en el PDF
        if self._esta_excluida(obj):
            return format_html(
                '<span style="'
                'background:#e0e0e0;color:#999;padding:2px 8px;border-radius:4px;'
                'font-size:11px;font-style:italic;border:1px solid #ccc;'
                '">🚫 Propiedad excluida — no aparecerá en el PDF</span>'
            )
        if not obj.pk or not obj.analisis or not obj.analisis.paciente or not obj.valor:
            return obj.valor or ""
        paciente   = obj.analisis.paciente
        edad_meses = paciente.edad_en_meses
        propiedad  = obj.propiedad
        if not propiedad or propiedad.tipo == 'CUALITATIVO':
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
            except (ValueError, TypeError):
                return obj.valor
        return obj.valor
    col_valor_coloreado.short_description = "Estado del Valor"
 
 
# =============================================================================
# 5. REGISTRO DE MODELOS
# =============================================================================
 
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display      = ('id', 'nombre', 'correo_electronico', 'rol', 'puesto', 'cedula_profesional', 'is_active')
    list_filter       = ('rol', 'is_active')
    search_fields     = ('nombre', 'correo_electronico', 'cedula_profesional')
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
    list_display  = ('nombre_laboratorio', 'ciudad', 'responsable_sanitario_principal')
    search_fields = ('nombre_laboratorio', 'ciudad')
 
 
@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'apellido_paterno', 'apellido_materno')
    list_display  = ('id', 'nombre_completo', 'sexo', 'get_edad', 'laboratorio')
    list_filter   = ('sexo', 'laboratorio')
 
    def get_edad(self, obj):
        años  = obj.edad
        meses = obj.edad_en_meses
        return f"{meses} meses" if años < 2 else f"{años} años"
    get_edad.short_description = "Edad"
 
 
@admin.register(Propiedad)
class PropiedadAdmin(admin.ModelAdmin):
    form                = PropiedadForm
    list_display        = ('nombre_propiedad', 'tipo', 'unidad', 'get_plantillas')
    list_filter         = ('tipo',)
    search_fields       = ('nombre_propiedad',)
    autocomplete_fields = ('loinc_code',)
    inlines             = [IntervaloReferenciaInline]
 
    def get_readonly_fields(self, request, obj=None):
        return ('tipo',) if obj else ()
 
    def get_plantillas(self, obj):
        nombres = obj.plantillas.values_list('titulo', flat=True)
        return ', '.join(nombres) if nombres else '—'
    get_plantillas.short_description = "Usada en plantillas"
 
    class Media:
        js = ('admin/js/propiedad_tipo_toggle.js', 'admin/js/intervalo_toggle.js')
 
 
@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    search_fields     = ('titulo',)
    list_display      = ('titulo', 'tipo_formato', 'get_num_propiedades', 'fecha_modificacion')
    filter_horizontal = ('propiedades',)
 
    def get_num_propiedades(self, obj):
        return obj.propiedades.count()
    get_num_propiedades.short_description = "N° Propiedades"
 
 
@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    form          = AnalisisAdminForm
    list_display  = ('id', 'get_paciente', 'get_plantilla', 'status', 'creado_por',
                     'fecha_analisis', 'get_resumen_propiedades', 'link_pdf')
    list_filter   = ('status', 'plantilla', 'fecha_analisis')
    search_fields = ('paciente__nombre', 'paciente__apellido_paterno', 'plantilla__titulo')
    autocomplete_fields = ('paciente', 'plantilla', 'creado_por')
    inlines       = [ResultadoAnalisisInline]
 
    # ─── Fieldsets sin "Personalización de propiedades" ───────────────────────
    fieldsets = (
        ('Datos del Análisis', {
            'fields': ('paciente', 'plantilla', 'creado_por', 'status',
                       'tipo_muestra', 'metodo'),
        }),
        ('Fechas y Horas', {
            'fields': ('fecha_muestra', 'hora_toma', 'hora_impresion'),
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
    # ─────────────────────────────────────────────────────────────────────────
 
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                'paciente',
                'plantilla',
                'propiedades_excluidas',
                'propiedades_extra',
            )
        return ()
 
    def save_model(self, request, obj, form, change):
        obj.skip_signal = True
        super().save_model(request, obj, form, change)
 
        if not change:
            ids_extra_raw = request.POST.get('_propiedades_extra_ids', '')
            ids_extra = [
                int(i) for i in ids_extra_raw.split(',')
                if i.strip().isdigit()
            ]
 
            nombres_excluidas_raw = request.POST.get('_propiedades_excluidas_nombres', '')
            nombres_excluidas = [
                n.strip() for n in nombres_excluidas_raw.split(',')
                if n.strip()
            ]
 
            if ids_extra:
                obj.propiedades_extra.set(
                    Propiedad.objects.filter(id__in=ids_extra)
                )
 
            if nombres_excluidas:
                obj.propiedades_excluidas.set(
                    Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
                )
 
            paciente   = obj.paciente
            edad_meses = paciente.edad_en_meses
 
            for propiedad in obj.get_propiedades_efectivas():
                total_intervalos = propiedad.intervalos.count()
                if total_intervalos == 0:
                    crear = True
                else:
                    crear = propiedad.intervalos.filter(
                        Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
                    ).filter(
                        Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
                    ).filter(
                        Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
                    ).exists()
 
                if crear:
                    ResultadoAnalisis.objects.get_or_create(
                        analisis=obj,
                        propiedad=propiedad,
                        defaults={
                            'loinc_code':        propiedad.loinc_code,
                            'nombre_propiedad':  propiedad.nombre_propiedad,
                            'valor':             '',
                            'unidad':            propiedad.unidad,
                        }
                    )
 
    def save_formset(self, request, form, formset, change):
        if formset.model.__name__ == 'ResultadoAnalisis' and not change:
            analisis    = form.instance
            total_forms = int(request.POST.get('resultados-TOTAL_FORMS', 0))
 
            for i in range(total_forms):
                prefix = f'resultados-{i}'
 
                propiedad_id_raw = request.POST.get(f'{prefix}-propiedad', '').strip()
                if not propiedad_id_raw or not propiedad_id_raw.isdigit():
                    continue
 
                propiedad_id = int(propiedad_id_raw)
                raw_valor    = request.POST.get(f'{prefix}-valor', '').strip()
                unidad       = request.POST.get(f'{prefix}-unidad', '').strip()
 
                try:
                    propiedad_obj = Propiedad.objects.get(pk=propiedad_id)
                except Propiedad.DoesNotExist:
                    continue
 
                instancia, _ = ResultadoAnalisis.objects.get_or_create(
                    analisis=analisis,
                    propiedad=propiedad_obj,
                    defaults={
                        'loinc_code':        propiedad_obj.loinc_code,
                        'nombre_propiedad':  propiedad_obj.nombre_propiedad,
                        'valor':             raw_valor,
                        'unidad':            unidad if unidad and unidad != 'N/A' else propiedad_obj.unidad,
                    }
                )
 
                instancia.valor = raw_valor
                if unidad and unidad != 'N/A':
                    instancia.unidad = unidad
                if not instancia.nombre_propiedad:
                    instancia.nombre_propiedad = propiedad_obj.nombre_propiedad
                instancia.save()
 
            formset.new_objects     = []
            formset.changed_objects = []
            formset.deleted_objects = []
            return
 
        super().save_formset(request, form, formset, change)
 
    def response_add(self, request, obj, post_url_continue=None):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse('admin:LabApp_analisis_change', args=[obj.pk])
        )
 
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if add:
            self.message_user(
                request,
                'Atención: Una vez guardado el análisis, el Paciente y la Plantilla '
                'no podrán modificarse. Verifique bien antes de guardar.',
                level='warning'
            )
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )
 
    def get_paciente(self, obj):
        return obj.paciente.nombre_completo
    get_paciente.short_description = "Paciente"
 
    def get_plantilla(self, obj):
        return obj.plantilla.titulo if obj.plantilla else "-"
    get_plantilla.short_description = "Plantilla"
 
    def get_resumen_propiedades(self, obj):
        extra     = obj.propiedades_extra.count()
        excluidas = obj.propiedades_excluidas.count()
        partes = []
        if extra:
            partes.append(
                format_html('<span style="color:#1a7a3c;">+{} extra</span>', extra)
            )
        if excluidas:
            partes.append(
                format_html('<span style="color:#c0392b;">-{} excluidas</span>', excluidas)
            )
        return format_html(' | '.join(str(p) for p in partes)) if partes else "—"
    get_resumen_propiedades.short_description = "Props. personalizadas"
 
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
 
 
@admin.register(LoincCode)
class LoincCodeAdmin(admin.ModelAdmin):
    search_fields = ('loinc_num', 'shortname', 'component')
    list_display  = ('loinc_num', 'shortname', 'component', 'system')
 