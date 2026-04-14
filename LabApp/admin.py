import json

from django.contrib import admin
from django import forms
from django.http import JsonResponse
from django.utils.html import format_html
from django.db.models import Q
from django.utils.safestring import mark_safe

from .models import (
    Usuario, Laboratorio, Paciente, LoincCode,
    Propiedad, IntervaloReferencia, Plantilla, PlantillaPropiedad,
    Analisis, ResultadoAnalisis,
)
from .loinc_mappings import system_terms_for, method_terms_for, component_terms_for, attrs_for


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

# Secciones/Series más comunes en laboratorios clínicos mexicanos.
# Aparecen como sugerencias en el dropdown al asignar una propiedad a una
# plantilla, eliminando la necesidad de gestionar una tabla separada.
SECCIONES_SUGERIDAS = [
    'FÓRMULA ROJA',
    'FÓRMULA BLANCA',
    'SERIE PLAQUETARIA',
    'SERIE TROMBOCÍTICA',
    'BIOQUÍMICA SANGUÍNEA',
    'QUÍMICA SANGUÍNEA',
    'PERFIL LIPÍDICO',
    'PRUEBAS DE FUNCIÓN HEPÁTICA',
    'PRUEBAS DE FUNCIÓN RENAL',
    'ELECTRÓLITOS SÉRICOS',
    'HORMONAS TIROIDEAS',
    'HORMONAS REPRODUCTIVAS',
    'MARCADORES TUMORALES',
    'URIANÁLISIS',
    'INMUNOLOGÍA / SEROLOGÍA',
    'COAGULACIÓN',
    'MICROBIOLOGÍA',
    'GASOMETRÍA',
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
        self.sugerencias = sugerencias
        self.placeholder = placeholder
        self.input_width = input_width

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
        js = ('admin/js/intervalo_toggle.js',)


class PlantillaAdminForm(forms.ModelForm):
    """
    Formulario para Plantilla con dropdowns de sugerencias en
    tipo_muestra y metodo. Estos campos en la plantilla sirven como
    predeterminados para los análisis y ayudan a identificar el código
    LOINC correcto según el espécimen y método analítico.
    """
    tipo_muestra = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=TIPOS_MUESTRA_SUGERIDOS,
            placeholder='Ej: Sangre total con EDTA, Suero...',
            input_width='280px',
        ),
        label='Tipo de muestra (predeterminado)',
        help_text=(
            'Tipo de muestra habitual para esta plantilla. '
            'El médico podrá modificarlo en cada análisis individual.'
        ),
    )
    metodo = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=METODOS_SUGERIDOS,
            placeholder='Ej: Impedancia eléctrica, Aglutinación...',
            input_width='280px',
        ),
        label='Método analítico (predeterminado)',
        help_text=(
            'Método analítico habitual de esta plantilla. '
            'Junto con el tipo de muestra, determina el código LOINC correcto '
            'para cada propiedad (ej. Hemoglobina tiene distintos LOINCs según el espécimen).'
        ),
    )

    class Meta:
        model  = Plantilla
        fields = '__all__'

    class Media:
        js = ('admin/js/analisis_imagenes_toggle.js',)


class AnalisisAdminForm(forms.ModelForm):
    tipo_muestra = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=TIPOS_MUESTRA_SUGERIDOS,
            placeholder='Ej: Sangre total con EDTA, Suero...',
            input_width='260px',
        ),
        label='Tipo de muestra',
        help_text='Sobreescribe el tipo de muestra predeterminado de la plantilla.',
    )
    metodo = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=METODOS_SUGERIDOS,
            placeholder='Ej: Impedancia eléctrica, Aglutinación...',
            input_width='260px',
        ),
        label='Método',
        help_text='Sobreescribe el método predeterminado de la plantilla.',
    )

    class Meta:
        model  = Analisis
        fields = '__all__'

    class Media:
        js = ('admin/js/analisis_imagenes_toggle.js',)


class PlantillaPropiedadForm(forms.ModelForm):
    """
    Formulario para la tabla intermedia Plantilla ↔ Propiedad.
    El campo 'seccion' usa un dropdown de sugerencias — no hay tabla auxiliar.
    El administrador escribe libremente o elige una de las series sugeridas.
    """
    seccion = forms.CharField(
        required=False,
        widget=SugerenciasDropdownWidget(
            sugerencias=SECCIONES_SUGERIDAS,
            placeholder='Ej: FÓRMULA ROJA, SERIE PLAQUETARIA...',
            input_width='230px',
        ),
        label='Serie / Sección',
        help_text='Agrupación visual en el reporte PDF. Opcional.',
    )

    class Meta:
        model  = PlantillaPropiedad
        fields = '__all__'


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

    fields          = ('propiedad', 'col_loinc_code',
                       'valor', 'unidad',
                       'col_intervalo_referencia', 'col_valor_coloreado')
    readonly_fields = ('propiedad', 'col_loinc_code',
                       'col_intervalo_referencia', 'col_valor_coloreado')

    def get_max_num(self, request, obj=None, **kwargs):
        if obj is None:
            return None
        return obj.resultados.count()

    def has_add_permission(self, request, obj=None):
        return obj is None

    def _esta_excluida(self, obj):
        if not obj.pk or not obj.analisis:
            return False
        return obj.analisis.propiedades_excluidas.filter(pk=obj.propiedad_id).exists()

    def col_loinc_code(self, obj):
        if not obj.pk:
            return "-"
        if obj.loinc_code:
            return format_html(
                '<span style="font-family:monospace;font-size:12px;'
                'background:#e8f4fd;border:1px solid #aac8e8;border-radius:3px;'
                'padding:2px 7px;color:#1a5276;">'
                '🔬 {}</span> <span style="font-size:11px;color:#555;">{}</span>',
                obj.loinc_code.loinc_num,
                obj.loinc_code.shortname or '',
            )
        return format_html('<span style="color:#aaa;font-size:11px;">— sin LOINC —</span>')
    col_loinc_code.short_description = "Código LOINC"

    def col_intervalo_referencia(self, obj):
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


class PlantillaPropiedadInline(admin.TabularInline):
    """
    Inline de propiedades en Plantilla.

    El campo 'seccion' es ahora un CharField con dropdown de sugerencias.
    Ya no requiere gestionar una tabla separada de secciones — el
    administrador simplemente escribe o elige la serie directamente aquí.

    NOTA: El guardado real se hace desde el picker JS (via save_model),
    no desde este inline (save_formset lo omite). Este inline es de lectura
    para ver el estado actual de las propiedades asignadas.
    """
    model               = PlantillaPropiedad
    form                = PlantillaPropiedadForm
    extra               = 1
    autocomplete_fields = ('propiedad', 'loinc_code')
    fields              = ('propiedad', 'loinc_code', 'seccion', 'orden')


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
    form          = PropiedadForm
    list_display  = ('nombre_propiedad', 'tipo', 'unidad', 'get_plantillas')
    list_filter   = ('tipo',)
    search_fields = ('nombre_propiedad',)
    inlines       = [IntervaloReferenciaInline]

    def get_readonly_fields(self, request, obj=None):
        return ('tipo',) if obj else ()

    def get_plantillas(self, obj):
        nombres = obj.plantillas.values_list('titulo', flat=True)
        return ', '.join(nombres) if nombres else '—'
    get_plantillas.short_description = "Usada en plantillas"

    class Media:
        js = ('admin/js/propiedad_tipo_toggle.js', 'admin/js/intervalo_toggle.js')


@admin.register(PlantillaPropiedad)
class PlantillaPropiedadAdmin(admin.ModelAdmin):
    form          = PlantillaPropiedadForm
    list_display  = ('plantilla', 'propiedad', 'loinc_code', 'seccion', 'orden')
    list_filter   = ('plantilla', 'seccion')
    search_fields = ('plantilla__titulo', 'propiedad__nombre_propiedad', 'loinc_code__loinc_num', 'seccion')
    autocomplete_fields = ('plantilla', 'propiedad', 'loinc_code')


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    form          = PlantillaAdminForm
    search_fields = ('titulo',)
    list_display  = ('titulo', 'tipo_formato', 'tipo_muestra', 'metodo',
                     'loinc_code', 'get_num_propiedades', 'fecha_modificacion')
    autocomplete_fields = ('loinc_code',)
    inlines       = [PlantillaPropiedadInline]

    def get_num_propiedades(self, obj):
        return obj.propiedades.count()
    get_num_propiedades.short_description = "N° Propiedades"

    # ── Endpoints AJAX ────────────────────────────────────────────────────────
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                'loinc-buscar/',
                self.admin_site.admin_view(self._loinc_buscar),
                name='plantilla_loinc_buscar',
            ),
            path(
                '<int:plantilla_id>/secciones/',
                self.admin_site.admin_view(self._secciones_json),
                name='plantilla_secciones_json',
            ),
        ]
        return custom + urls

    def _loinc_buscar(self, request):
        """
        GET /admin/LabApp/plantilla/loinc-buscar/
            ?q=hemoglobina              ← nombre de la propiedad (español o inglés)
            &muestra=Suero              ← tipo_muestra del formulario (opcional)
            &metodo=Espectrofotometría  ← metodo del formulario (opcional)

        Lógica de filtrado en 4 niveles (de más a menos estricto):

        PASO 1 — Filtro base por texto (siempre activo)
            Traduce `q` al inglés usando component_terms_for() y busca
            en loinc_num, shortname y component con OR entre variantes.

        PASO 2 — Filtro por property + scale_typ (semántico)
            Si la propiedad tiene atributos definidos en NOMBRE_A_LOINC_ATTRS,
            filtra por los valores de `property` y `scale_typ` esperados.
            Esto descarta LOINCs semánticamente incorrectos (ej. NFr cuando
            se busca una enzima con CCnc). Si este filtro deja 0 resultados
            se omite (fallback), no se aborta.

        PASO 3 — Filtro por system (tipo de muestra)
            Traduce `muestra` y filtra por el campo `system`.
            Si queda vacío, se relaja.

        PASO 4 — Filtro por method_typ (método analítico)
            A diferencia de la versión anterior, aquí SOLO se incluyen
            LOINCs que tienen method_typ definido Y coincidente.
            Los LOINCs sin method_typ se excluyen en la pasada estricta.
            Si esa pasada queda vacía, se hace una segunda pasada que
            incluye los nulls (relax), exactamente igual que antes pero
            solo como fallback, no como comportamiento por defecto.

        ORDEN DE RESULTADOS
            Los resultados se ordenan por relevancia de coincidencia:
              0 — coincide system Y method  (más específico)
              1 — coincide solo system      (correcto para la muestra)
              2 — coincide solo method      (método ok, muestra distinta)
              3 — ninguno                   (fallback texto/semántica)
            Dentro de cada grupo, loinc_num ASC: números bajos = códigos
            canónicos más antiguos (ej. 718-7 Hemoglobin/Bld de 1995)
            que son los más apropiados para uso clínico general.

        Se devuelven máximo 20 resultados.
        """
        q       = request.GET.get('q',      '').strip()
        muestra = request.GET.get('muestra', '').strip()
        metodo  = request.GET.get('metodo',  '').strip()

        if not q:
            return JsonResponse({'results': [], 'filtrado': False})

        # ── PASO 1: Filtro base por texto ────────────────────────────────────
        # Traduce el nombre español al inglés y busca en los campos de texto.
        terminos_q = component_terms_for(q)
        q_text = Q()
        for termino in terminos_q:
            q_text |= (
                Q(loinc_num__icontains=termino) |
                Q(shortname__icontains=termino)  |
                Q(component__icontains=termino)
            )
        qs_base = LoincCode.objects.filter(q_text)

        # ── PASO 2: Filtro semántico por property + scale_typ ────────────────
        # Consultar los atributos LOINC esperados para esta propiedad.
        # Si no hay mapeo definido, attrs queda vacío y se omite este filtro.
        attrs        = attrs_for(q)
        prop_terms   = attrs.get('property', [])
        scale_terms  = attrs.get('scale',    [])

        qs_con_attrs = qs_base
        attrs_activos = False

        if prop_terms:
            q_prop = Q()
            for p in prop_terms:
                q_prop |= Q(property__iexact=p)
            qs_con_attrs = qs_con_attrs.filter(q_prop)
            attrs_activos = True

        if scale_terms and qs_con_attrs.exists():
            q_scale = Q()
            for s in scale_terms:
                q_scale |= Q(scale_typ__iexact=s)
            qs_con_attrs = qs_con_attrs.filter(q_scale)

        # Si el filtro semántico dejó resultados, trabajamos con él;
        # si no, volvemos al base (no abortar por un mapeo incompleto).
        qs_semantico = qs_con_attrs if (attrs_activos and qs_con_attrs.exists()) else qs_base

        # ── PASO 3 y 4: Filtros de contexto (system + method) ────────────────
        system_terms = system_terms_for(muestra) if muestra else []
        method_terms = method_terms_for(metodo)  if metodo  else []

        def _q_system(terms):
            q = Q()
            for t in terms:
                q |= Q(system__icontains=t)
            return q

        def _q_method_estricto(terms):
            """Solo LOINCs con method_typ definido Y que coincida."""
            q = Q()
            for t in terms:
                q |= Q(method_typ__icontains=t)
            return q

        def _q_method_relax(terms):
            """LOINCs con method_typ coincidente O sin method definido (fallback)."""
            q = Q(method_typ__isnull=True) | Q(method_typ='')
            for t in terms:
                q |= Q(method_typ__icontains=t)
            return q

        # Intentar las combinaciones de más a menos estrictas:
        #   A) system estricto + method estricto
        #   B) system estricto + method relax (method_typ nulo permitido)
        #   C) solo system estricto (sin filtro de method)
        #   D) sin filtros de contexto (solo semántico + texto)
        nivel_filtrado = 'ninguno'
        qs = qs_semantico

        if system_terms and method_terms:
            # A — más estricto
            qs_a = qs_semantico.filter(_q_system(system_terms)).filter(
                _q_method_estricto(method_terms)
            )
            if qs_a.exists():
                qs = qs_a
                nivel_filtrado = 'system+method_estricto'
            else:
                # B — method con relax (incluye sin method)
                qs_b = qs_semantico.filter(_q_system(system_terms)).filter(
                    _q_method_relax(method_terms)
                )
                if qs_b.exists():
                    qs = qs_b
                    nivel_filtrado = 'system+method_relax'
                else:
                    # C — solo system
                    qs_c = qs_semantico.filter(_q_system(system_terms))
                    if qs_c.exists():
                        qs = qs_c
                        nivel_filtrado = 'solo_system'
                    # D — sin contexto: qs queda como qs_semantico

        elif system_terms:
            qs_c = qs_semantico.filter(_q_system(system_terms))
            if qs_c.exists():
                qs = qs_c
                nivel_filtrado = 'solo_system'

        elif method_terms:
            qs_a = qs_semantico.filter(_q_method_estricto(method_terms))
            if qs_a.exists():
                qs = qs_a
                nivel_filtrado = 'solo_method_estricto'
            else:
                qs_b = qs_semantico.filter(_q_method_relax(method_terms))
                if qs_b.exists():
                    qs = qs_b
                    nivel_filtrado = 'solo_method_relax'

        # ── Ordenación por relevancia de coincidencia ────────────────────────
        #
        # El criterio de orden es RELEVANCIA, no presencia de método.
        # El error anterior priorizaba LOINCs con method_typ definido, lo que
        # empujaba al fondo los códigos canónicos sin método (ej. 718-7
        # Hemoglobin/Bld), que son precisamente los más correctos para la
        # mayoría de analitos de biometría hemática.
        #
        # Nueva prioridad (menor número = aparece primero):
        #   0 — coincide system Y method  (más específico)
        #   1 — coincide solo system      (correcto para la muestra)
        #   2 — coincide solo method      (método correcto, muestra distinta)
        #   3 — ninguno                   (fallback por texto/semántica)
        #
        # Dentro de cada grupo, loinc_num ASC: los números bajos en LOINC
        # son códigos más antiguos y generalmente más canónicos (718-7
        # es de 1995, los de 5 dígitos son más recientes y específicos).
        from django.db.models import Case, When, Value, IntegerField
        from django.db.models.functions import Length

        # Construir los Q de coincidencia para la anotación
        if system_terms:
            q_sys_match = Q()
            for t in system_terms:
                q_sys_match |= Q(system__icontains=t)
        else:
            q_sys_match = Q(pk__isnull=True)  # nunca coincide si no hay términos

        if method_terms:
            q_met_match = Q()
            for t in method_terms:
                q_met_match |= Q(method_typ__icontains=t)
        else:
            q_met_match = Q(pk__isnull=True)  # nunca coincide si no hay términos

        qs = qs.annotate(
            relevancia=Case(
                When(q_sys_match & q_met_match, then=Value(0)),
                When(q_sys_match,               then=Value(1)),
                When(q_met_match,               then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        # FIX: loinc_num es CharField. '20570-8' < '718-7' en string sort
        # porque '2'<'7'. Ordenar por longitud primero pone el código canónico
        # más corto (718-7, len=5) antes que los de 5 dígitos (20570-8, len=7).
        ).order_by('relevancia', Length('loinc_num'), 'loinc_num')

        # ── Indicador de filtrado para el JS ─────────────────────────────────
        filtrado = nivel_filtrado not in ('ninguno',)

        resultados = list(qs[:20])

        results = [
            {
                'id':          lc.pk,
                'loinc_num':   lc.loinc_num,
                'shortname':   lc.shortname  or '',
                'component':   lc.component  or '',
                'system':      lc.system     or '',
                'property':    lc.property   or '',
                'scale_typ':   lc.scale_typ  or '',
                'method_typ':  lc.method_typ or '',
                'tiene_method': bool(lc.method_typ),
            }
            for lc in resultados
        ]

        return JsonResponse({
            'results':         results,
            'filtrado':        filtrado,
            'nivel_filtrado':  nivel_filtrado,
            'muestra':         muestra or '',
            'metodo':          metodo  or '',
        })

    def _secciones_json(self, request, plantilla_id):
        """
        Devuelve las secciones únicas ya asignadas en esta plantilla.
        El picker JS las usa para poblar el dropdown de serie/sección.
        Formato compatible con el JS anterior: lista de {id, nombre}.
        Aquí 'id' y 'nombre' son ambos el texto de la sección (ya no hay FK).

        GET /admin/LabApp/plantilla/<id>/secciones/
        """
        secciones_qs = (
            PlantillaPropiedad.objects
            .filter(plantilla_id=plantilla_id)
            .exclude(seccion__isnull=True)
            .exclude(seccion='')
            .values_list('seccion', flat=True)
            .distinct()
            .order_by('seccion')
        )
        # Incluir también las sugerencias globales para que el picker tenga
        # siempre las series estándar disponibles aunque no estén en la BD aún.
        existentes = set(secciones_qs)
        todas = list(existentes) + [s for s in SECCIONES_SUGERIDAS if s not in existentes]
        return JsonResponse({
            'secciones': [
                {'id': s, 'nombre': s}
                for s in todas
            ]
        })

    # ── JSON para el picker ───────────────────────────────────────────────────
    def _build_json_scripts(self, obj):
        all_props = list(
            Propiedad.objects
            .all()
            .order_by('nombre_propiedad')
            .values('id', 'nombre_propiedad', 'tipo')
        )
        props_data = [
            {'id': p['id'], 'nombre': p['nombre_propiedad'], 'tipo': p['tipo']}
            for p in all_props
        ]

        existing_data  = []
        secciones_data = []

        if obj and obj.pk:
            # Secciones únicas ya guardadas en esta plantilla
            secciones_guardadas = set(
                PlantillaPropiedad.objects
                .filter(plantilla=obj)
                .exclude(seccion__isnull=True)
                .exclude(seccion='')
                .values_list('seccion', flat=True)
                .distinct()
            )
            todas_secciones = list(secciones_guardadas) + [
                s for s in SECCIONES_SUGERIDAS if s not in secciones_guardadas
            ]
            secciones_data = [{'id': s, 'nombre': s} for s in todas_secciones]

            for pp in (
                PlantillaPropiedad.objects
                .filter(plantilla=obj)
                .select_related('propiedad', 'loinc_code')
                .order_by('seccion', 'orden', 'propiedad__nombre_propiedad')
            ):
                existing_data.append({
                    'propId':        pp.propiedad_id,
                    'nombre':        pp.propiedad.nombre_propiedad,
                    'loincId':       pp.loinc_code_id or '',
                    'loincNum':      pp.loinc_code.loinc_num  if pp.loinc_code else '',
                    'loincDesc':     pp.loinc_code.shortname  if pp.loinc_code else '',
                    'orden':         pp.orden,
                    'seccionNombre': pp.seccion or '',
                    'seccionId':     pp.seccion or '',
                })
        else:
            # Plantilla nueva: mostrar todas las sugerencias en el picker
            secciones_data = [{'id': s, 'nombre': s} for s in SECCIONES_SUGERIDAS]

        return mark_safe(
            '<script id="pp-props-data" type="application/json">'
            + json.dumps(props_data, ensure_ascii=False) +
            '</script>'
            '<script id="pp-existing-data" type="application/json">'
            + json.dumps(existing_data, ensure_ascii=False) +
            '</script>'
            '<script id="pp-secciones-data" type="application/json">'
            + json.dumps(secciones_data, ensure_ascii=False) +
            '</script>'
        )

    def get_fieldsets(self, request, obj=None):
        base = [
            (None, {
                'fields': ('titulo', 'tipo_formato', 'loinc_code', 'texto_justificado_default'),
            }),
            ('Muestra y Método', {
                'fields': ('tipo_muestra', 'metodo'),
                'description': (
                    '📋 Estos valores son los predeterminados para todos los análisis '
                    'creados con esta plantilla. Definirlos correctamente ayuda a '
                    'identificar el código LOINC correcto para cada propiedad '
                    '(una misma magnitud, p. ej. Hemoglobina, puede tener distintos '
                    'LOINCs según el espécimen o el método analítico). '
                    'El médico podrá modificarlos en cada análisis individual si es necesario.'
                ),
            }),
        ]
        base.append((
            None,
            {
                'fields':      (),
                'description': self._build_json_scripts(obj),
            }
        ))
        return base

    # ── Guardar desde el picker ───────────────────────────────────────────────
    # El picker JS envía cuatro campos ocultos:
    #   pp_picker_ids        = "3,7,12"       → IDs de Propiedad
    #   pp_picker_loinc_ids  = "5,,8"         → IDs de LoincCode (vacío = sin LOINC)
    #   pp_picker_ordenes    = "1,2,3"        → Orden de cada propiedad
    #   pp_picker_secciones  = "FÓRMULA ROJA,,FÓRMULA ROJA"
    #                                         → Nombre de serie (string, no ID)
    #
    # NOTA PARA EL JS (plantilla_propiedades_picker.js):
    #   - El campo oculto de sección debe llamarse 'pp_picker_secciones'
    #     (antes era 'pp_picker_seccion_ids' con IDs enteros).
    #   - Ahora envía el NOMBRE de la sección como texto, ej. "FÓRMULA ROJA".
    #   - El campo 'seccionId' en pp-existing-data ya NO es un entero,
    #     es el mismo texto que 'seccionNombre'.

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        ids_raw       = request.POST.get('pp_picker_ids',       '').strip()
        loinc_ids_raw = request.POST.get('pp_picker_loinc_ids', '').strip()
        ordenes_raw   = request.POST.get('pp_picker_ordenes',   '').strip()
        secciones_raw = request.POST.get('pp_picker_secciones', '').strip()
        # Compatibilidad con el nombre anterior (por si el JS aún lo manda)
        if not secciones_raw:
            secciones_raw = request.POST.get('pp_picker_seccion_ids', '').strip()

        if not ids_raw:
            return

        ids_list       = [i.strip() for i in ids_raw.split(',')       if i.strip()]
        loinc_ids_list = [l.strip() for l in loinc_ids_raw.split(',')]
        ordenes_list   = [o.strip() for o in ordenes_raw.split(',')]
        secciones_list = [s.strip() for s in secciones_raw.split(',')]

        while len(loinc_ids_list) < len(ids_list): loinc_ids_list.append('')
        while len(ordenes_list)   < len(ids_list): ordenes_list.append('')
        while len(secciones_list) < len(ids_list): secciones_list.append('')

        PlantillaPropiedad.objects.filter(plantilla=obj).delete()

        for idx, prop_id_str in enumerate(ids_list):
            if not prop_id_str.isdigit():
                continue
            try:
                propiedad = Propiedad.objects.get(pk=int(prop_id_str))
            except Propiedad.DoesNotExist:
                continue

            loinc_id_str = loinc_ids_list[idx] if idx < len(loinc_ids_list) else ''
            orden_str    = ordenes_list[idx]    if idx < len(ordenes_list)   else ''
            seccion_str  = secciones_list[idx]  if idx < len(secciones_list) else ''

            orden = int(orden_str) if orden_str.isdigit() else (idx + 1)

            loinc_obj = None
            if loinc_id_str.isdigit():
                loinc_obj = LoincCode.objects.filter(pk=int(loinc_id_str)).first()

            PlantillaPropiedad.objects.create(
                plantilla  = obj,
                propiedad  = propiedad,
                loinc_code = loinc_obj,
                seccion    = seccion_str or None,
                orden      = orden,
            )

    def save_formset(self, request, form, formset, change):
        if formset.model == PlantillaPropiedad:
            formset.new_objects     = []
            formset.changed_objects = []
            formset.deleted_objects = []
            return
        super().save_formset(request, form, formset, change)

    class Media:
        js  = ('admin/js/plantilla_propiedades_picker.js',)
        css = {'all': ('admin/css/plantilla_propiedades_picker.css',)}


@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    form          = AnalisisAdminForm
    list_display  = ('id', 'get_paciente', 'get_plantilla', 'status', 'creado_por',
                     'fecha_analisis', 'get_resumen_propiedades', 'link_pdf')
    list_filter   = ('status', 'plantilla', 'fecha_analisis')
    search_fields = ('paciente__nombre', 'paciente__apellido_paterno', 'plantilla__titulo')
    autocomplete_fields = ('paciente', 'plantilla', 'creado_por')
    inlines       = [ResultadoAnalisisInline]

    fieldsets = (
        ('Datos del Análisis', {
            'fields': ('paciente', 'plantilla', 'creado_por', 'status'),
        }),
        ('Muestra y Método', {
            'fields': ('tipo_muestra', 'metodo'),
            'description': (
                '📋 Se pre-llenan desde los valores predeterminados de la plantilla. '
                'Modifíquelos aquí si para este análisis en particular se usó '
                'un espécimen o método diferente.'
            ),
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

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('paciente', 'plantilla', 'propiedades_excluidas', 'propiedades_extra')
        return ()

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                'loinc-buscar/',
                self.admin_site.admin_view(self._loinc_buscar),
                name='analisis_loinc_buscar',
            ),
        ]
        return custom + urls

    def _loinc_buscar(self, request):
        """
        Endpoint LOINC para el picker de propiedades extra en Analisis.
        Misma lógica que PlantillaAdmin._loinc_buscar.
        URL: /admin/LabApp/analisis/loinc-buscar/?q=...&muestra=...&metodo=...
        """
        from django.db.models import Case, When, Value, IntegerField
        from django.db.models.functions import Length

        q       = request.GET.get('q',      '').strip()
        muestra = request.GET.get('muestra', '').strip()
        metodo  = request.GET.get('metodo',  '').strip()

        if not q:
            return JsonResponse({'results': [], 'filtrado': False})

        terminos_q = component_terms_for(q)
        q_text = Q()
        for termino in terminos_q:
            q_text |= (
                Q(loinc_num__icontains=termino) |
                Q(shortname__icontains=termino)  |
                Q(component__icontains=termino)
            )
        qs_base = LoincCode.objects.filter(q_text)

        attrs        = attrs_for(q)
        prop_terms   = attrs.get('property', [])
        scale_terms  = attrs.get('scale',    [])

        qs_con_attrs  = qs_base
        attrs_activos = False

        if prop_terms:
            q_prop = Q()
            for p in prop_terms:
                q_prop |= Q(property__iexact=p)
            qs_con_attrs  = qs_con_attrs.filter(q_prop)
            attrs_activos = True

        if scale_terms and qs_con_attrs.exists():
            q_scale = Q()
            for s in scale_terms:
                q_scale |= Q(scale_typ__iexact=s)
            qs_con_attrs = qs_con_attrs.filter(q_scale)

        qs_semantico = qs_con_attrs if (attrs_activos and qs_con_attrs.exists()) else qs_base

        system_terms = system_terms_for(muestra) if muestra else []
        method_terms = method_terms_for(metodo)  if metodo  else []

        def _q_system(terms):
            q = Q()
            for t in terms:
                q |= Q(system__icontains=t)
            return q

        def _q_method_estricto(terms):
            q = Q()
            for t in terms:
                q |= Q(method_typ__icontains=t)
            return q

        def _q_method_relax(terms):
            q = Q(method_typ__isnull=True) | Q(method_typ='')
            for t in terms:
                q |= Q(method_typ__icontains=t)
            return q

        nivel_filtrado = 'ninguno'
        qs = qs_semantico

        if system_terms and method_terms:
            qs_a = qs_semantico.filter(_q_system(system_terms)).filter(_q_method_estricto(method_terms))
            if qs_a.exists():
                qs = qs_a; nivel_filtrado = 'system+method_estricto'
            else:
                qs_b = qs_semantico.filter(_q_system(system_terms)).filter(_q_method_relax(method_terms))
                if qs_b.exists():
                    qs = qs_b; nivel_filtrado = 'system+method_relax'
                else:
                    qs_c = qs_semantico.filter(_q_system(system_terms))
                    if qs_c.exists():
                        qs = qs_c; nivel_filtrado = 'solo_system'
        elif system_terms:
            qs_c = qs_semantico.filter(_q_system(system_terms))
            if qs_c.exists():
                qs = qs_c; nivel_filtrado = 'solo_system'
        elif method_terms:
            qs_a = qs_semantico.filter(_q_method_estricto(method_terms))
            if qs_a.exists():
                qs = qs_a; nivel_filtrado = 'solo_method_estricto'
            else:
                qs_b = qs_semantico.filter(_q_method_relax(method_terms))
                if qs_b.exists():
                    qs = qs_b; nivel_filtrado = 'solo_method_relax'

        if system_terms:
            q_sys_match = Q()
            for t in system_terms:
                q_sys_match |= Q(system__icontains=t)
        else:
            q_sys_match = Q(pk__isnull=True)

        if method_terms:
            q_met_match = Q()
            for t in method_terms:
                q_met_match |= Q(method_typ__icontains=t)
        else:
            q_met_match = Q(pk__isnull=True)

        qs = qs.annotate(
            relevancia=Case(
                When(q_sys_match & q_met_match, then=Value(0)),
                When(q_sys_match,               then=Value(1)),
                When(q_met_match,               then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        ).order_by('relevancia', Length('loinc_num'), 'loinc_num')

        filtrado   = nivel_filtrado not in ('ninguno',)
        resultados = list(qs[:20])

        results = [
            {
                'id':           lc.pk,
                'loinc_num':    lc.loinc_num,
                'shortname':    lc.shortname  or '',
                'component':    lc.component  or '',
                'system':       lc.system     or '',
                'property':     lc.property   or '',
                'scale_typ':    lc.scale_typ  or '',
                'method_typ':   lc.method_typ or '',
                'tiene_method': bool(lc.method_typ),
            }
            for lc in resultados
        ]

        return JsonResponse({
            'results':        results,
            'filtrado':       filtrado,
            'nivel_filtrado': nivel_filtrado,
            'muestra':        muestra or '',
            'metodo':         metodo  or '',
        })

    def save_model(self, request, obj, form, change):
        if not change and obj.plantilla:
            if not obj.tipo_muestra and obj.plantilla.tipo_muestra:
                obj.tipo_muestra = obj.plantilla.tipo_muestra
            if not obj.metodo and obj.plantilla.metodo:
                obj.metodo = obj.plantilla.metodo

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

            # LOINCs asignados a las propiedades extra desde el picker JS
            loinc_extra_raw = request.POST.get('_propiedades_extra_loinc_ids', '')
            loinc_extra_list = [l.strip() for l in loinc_extra_raw.split(',')]
            # Construir dict propId → loincId para usarlo al crear ResultadoAnalisis
            extra_loinc_map = {}
            for i, prop_id in enumerate(ids_extra):
                loinc_str = loinc_extra_list[i] if i < len(loinc_extra_list) else ''
                if loinc_str.isdigit():
                    extra_loinc_map[prop_id] = int(loinc_str)

            if ids_extra:
                obj.propiedades_extra.set(Propiedad.objects.filter(id__in=ids_extra))

            if nombres_excluidas:
                obj.propiedades_excluidas.set(
                    Propiedad.objects.filter(nombre_propiedad__in=nombres_excluidas)
                )

            paciente      = obj.paciente
            edad_meses    = paciente.edad_en_meses
            ids_extra_set = set(ids_extra)  # props añadidas explícitamente por el usuario

            for propiedad in obj.get_propiedades_efectivas():
                es_extra         = propiedad.pk in ids_extra_set
                total_intervalos = propiedad.intervalos.count()

                if total_intervalos == 0:
                    crear = True
                else:
                    intervalo_match = propiedad.intervalos.filter(
                        Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
                    ).filter(
                        Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
                    ).filter(
                        Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
                    ).exists()
                    # Las propiedades extra se crean SIEMPRE aunque no haya intervalo
                    # para este paciente: el usuario las agregó de forma explícita.
                    crear = intervalo_match or es_extra

                if crear:
                    try:
                        pp    = PlantillaPropiedad.objects.get(plantilla=obj.plantilla, propiedad=propiedad)
                        loinc = pp.loinc_code
                    except (PlantillaPropiedad.DoesNotExist, AttributeError):
                        # Propiedad extra: buscar LOINC en el mapa enviado por el picker JS
                        loinc_id_extra = extra_loinc_map.get(propiedad.pk)
                        loinc = LoincCode.objects.filter(pk=loinc_id_extra).first() if loinc_id_extra else None

                    ResultadoAnalisis.objects.get_or_create(
                        analisis=obj,
                        propiedad=propiedad,
                        defaults={
                            'loinc_code':       loinc,
                            'nombre_propiedad': propiedad.nombre_propiedad,
                            'valor':            '',
                            'unidad':           propiedad.unidad,
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

                try:
                    pp    = PlantillaPropiedad.objects.get(plantilla=analisis.plantilla, propiedad=propiedad_obj)
                    loinc = pp.loinc_code
                except (PlantillaPropiedad.DoesNotExist, AttributeError):
                    loinc = None

                instancia, _ = ResultadoAnalisis.objects.get_or_create(
                    analisis=analisis,
                    propiedad=propiedad_obj,
                    defaults={
                        'loinc_code':       loinc,
                        'nombre_propiedad': propiedad_obj.nombre_propiedad,
                        'valor':            raw_valor,
                        'unidad':           unidad if unidad and unidad != 'N/A' else propiedad_obj.unidad,
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
            partes.append(format_html('<span style="color:#1a7a3c;">+{} extra</span>', extra))
        if excluidas:
            partes.append(format_html('<span style="color:#c0392b;">-{} excluidas</span>', excluidas))
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