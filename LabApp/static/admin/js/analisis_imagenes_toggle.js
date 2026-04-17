/**
 * analisis_imagenes_toggle.js  v18
 *
 * NUEVAS FUNCIONES respecto a v17:
 *   1. SECCIÓN para propiedades extra — al agregar una propiedad extra se
 *      muestra un select de "Serie / Sección" igual al que aparece en el
 *      picker de plantillas. El valor elegido se envía al backend via el
 *      hidden _propiedades_extra_secciones (array paralelo a los ids).
 *
 *   2. TIPO DE MUESTRA y MÉTODO bloqueados al entrar — los campos se
 *      muestran en modo solo-lectura con un candado visual. Un botón
 *      "✏️ Modificar" los desbloquea. Al desbloquearlos aparece un banner
 *      de advertencia que indica que los LOINCs deben revisarse si se
 *      cambia el espécimen o método analítico.
 *
 *   3. PRE-LLENADO AUTOMÁTICO de muestra/método desde la plantilla — al
 *      seleccionar una plantilla (modo alta) se consulta el endpoint
 *      /admin_ext/plantilla/<id>/muestra-metodo/ y se rellenan los campos,
 *      que quedan bloqueados con la etiqueta "Heredado de la plantilla".
 */

(function () {
    'use strict';

    var PREFIX = 'resultados';

    // ═══════════════════════════════════════════════════════════════════════
    // SECCIONES SUGERIDAS (igual que SECCIONES_SUGERIDAS en admin.py)
    // ═══════════════════════════════════════════════════════════════════════
    var SECCIONES_SUGERIDAS = [
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
    ];

    // -------------------------------------------------------
    // HELPERS DE MODO
    // -------------------------------------------------------

    function esModoEdicion() {
        return window.location.pathname.indexOf('/change/') !== -1;
    }

    function tieneResultadosGuardados() {
        var tbody = getTbodyInline();
        if (!tbody) return false;
        var filas = tbody.querySelectorAll('tr.dynamic-' + PREFIX);
        for (var i = 0; i < filas.length; i++) {
            var pk = filas[i].querySelector('input[name$="-id"]');
            if (pk && pk.value !== '') return true;
        }
        return false;
    }

    function debeBloquearPrecarga() {
        return esModoEdicion() || tieneResultadosGuardados();
    }

    // -------------------------------------------------------
    // SECCIÓN IMÁGENES
    // -------------------------------------------------------

    function getSectionImagen() {
        return document.querySelector('.seccion-imagenes-analisis');
    }

    function mostrarOcultarImagenes(tipoFormato) {
        var seccion = getSectionImagen();
        if (!seccion) return;
        var fieldset = seccion.closest('fieldset') || seccion;

        if (tipoFormato === 'IMAGENES_RESULTADOS') {
            fieldset.style.visibility = '';
            fieldset.style.position   = '';
            fieldset.style.height     = '';
            fieldset.style.overflow   = '';
            fieldset.style.padding    = '';
            fieldset.style.margin     = '';
            fieldset.style.border     = '';
            fieldset.querySelectorAll('input[type="file"]').forEach(function (inp) {
                inp.disabled = false;
            });
        } else {
            fieldset.style.visibility = 'hidden';
            fieldset.style.position   = 'absolute';
            fieldset.style.height     = '0';
            fieldset.style.overflow   = 'hidden';
            fieldset.style.padding    = '0';
            fieldset.style.margin     = '0';
            fieldset.style.border     = 'none';
        }
    }

    // -------------------------------------------------------
    // INLINE — utilidades
    // -------------------------------------------------------

    function getTbodyInline() {
        return document.querySelector('#' + PREFIX + '-group tbody');
    }

    function getInlineTotal() {
        return document.getElementById('id_' + PREFIX + '-TOTAL_FORMS');
    }

    function getInlineGroup() {
        return document.getElementById(PREFIX + '-group');
    }

    function limpiarFilasSinPk() {
        var tbody = getTbodyInline();
        if (!tbody) return;
        tbody.querySelectorAll('tr.dynamic-' + PREFIX).forEach(function (fila) {
            var pk = fila.querySelector('input[name$="-id"]');
            if (!pk || pk.value === '') fila.remove();
        });
    }

    function recalcularTotalForms() {
        var input = getInlineTotal();
        var tbody = getTbodyInline();
        if (!input || !tbody) return;
        input.value = tbody.querySelectorAll('tr.dynamic-' + PREFIX).length;
    }

    // -------------------------------------------------------
    // Estilos compartidos
    // -------------------------------------------------------
    var ESTILO_READONLY =
        'background:transparent;border:none;outline:none;box-shadow:none;' +
        'font-size:13px;color:inherit;width:100%;padding:0;cursor:default;';

    var ESTILO_UNIDAD_NA =
        'background-color:#f0f0f0;color:#999;cursor:not-allowed;' +
        'border:1px solid #ddd;border-radius:4px;font-size:13px;width:100%;padding:2px 6px;';

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
            .replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // -------------------------------------------------------
    // Estado global
    // -------------------------------------------------------
    var _propiedadesBase        = [];
    var _extrasSeleccionadas    = {}; // { id: propObj }
    var _excluidasSeleccionadas = {}; // { nombre_propiedad: true }
    var _extraLoincMap          = {}; // { propId: { loincId, loincNum, loincDesc } }
    var _extraSeccionMap        = {}; // { propId: 'NOMBRE SECCION' }  ← NUEVO

    // Valores de muestra/método heredados de la plantilla (para restaurar)
    var _templateMuestra = '';
    var _templateMetodo  = '';

    // ═══════════════════════════════════════════════════════════════════════
    // BLOQUEO / DESBLOQUEO DE TIPO DE MUESTRA Y MÉTODO
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * Inyecta el sistema lock/unlock en los campos tipo_muestra y metodo.
     * Debe llamarse después de que el DOM esté listo.
     * Puede llamarse varias veces (es idempotente gracias al id único).
     */
    function setupMuestraMetodoCampos() {
        if (document.getElementById('_mm_control_bar')) return;

        var inputMuestra = document.getElementById('id_tipo_muestra');
        var inputMetodo  = document.getElementById('id_metodo');
        if (!inputMuestra && !inputMetodo) return;

        // Encontrar el fieldset que contiene estos campos
        var fieldset = null;
        if (inputMuestra) {
            fieldset = inputMuestra.closest('fieldset');
        }
        if (!fieldset && inputMetodo) {
            fieldset = inputMetodo.closest('fieldset');
        }

        // ── Banner de advertencia (oculto hasta que el usuario desbloquee) ──
        var aviso = document.createElement('div');
        aviso.id = '_mm_aviso_loinc';
        aviso.style.cssText = [
            'display:none',
            'margin:10px 0 4px',
            'padding:10px 14px',
            'background:#fff8e1',
            'border:1px solid #f9a825',
            'border-left:4px solid #f57f17',
            'border-radius:4px',
            'font-size:13px',
            'line-height:1.5',
        ].join(';');
        aviso.innerHTML = [
            '<strong style="color:#e65100;">⚠️ Verifique los códigos LOINC</strong><br>',
            'Ha modificado el tipo de muestra o el método analítico. Una misma magnitud ',
            '(p. ej. Hemoglobina) puede tener distintos códigos LOINC según el espécimen ',
            'o el método. Revise que cada propiedad tenga el LOINC correcto para el nuevo ',
            'contexto.<br>',
            '<a href="https://loinc.org/search/" target="_blank" rel="noopener" ',
            'style="color:#1a6fa8;font-size:12px;">🌐 Buscar en LOINC.org ↗</a>',
            '<span id="_mm_restaurar_wrap" style="display:none;">',
            ' &nbsp;·&nbsp; ',
            '<button type="button" id="_mm_btn_restaurar" ',
            'style="border:none;background:none;color:#1a6fa8;cursor:pointer;',
            'font-size:12px;text-decoration:underline;padding:0;">',
            '🔒 Restaurar valores de la plantilla',
            '</button>',
            '</span>',
        ].join('');

        // ── Barra de control: botón "Modificar" ─────────────────────────────
        var controlBar = document.createElement('div');
        controlBar.id = '_mm_control_bar';
        controlBar.style.cssText = 'margin:6px 0 2px;display:flex;align-items:center;gap:8px;';
        controlBar.innerHTML = [
            '<span id="_mm_lock_badge" style="',
            'display:inline-flex;align-items:center;gap:5px;',
            'background:#f5f5f5;border:1px solid #ddd;border-radius:4px;',
            'padding:3px 10px;font-size:12px;color:#555;">',
            '🔒 <span id="_mm_badge_texto">Los campos están protegidos</span>',
            '</span>',
            '<button type="button" id="_mm_btn_modificar" style="',
            'border:1px solid #1a6fa8;background:#e8f0fe;color:#1a6fa8;',
            'border-radius:4px;padding:4px 12px;cursor:pointer;font-size:12px;',
            'font-weight:600;white-space:nowrap;">',
            '✏️ Modificar',
            '</button>',
        ].join('');

        // Insertar en el fieldset (o en el contenedor padre)
        if (fieldset) {
            fieldset.appendChild(aviso);
            fieldset.appendChild(controlBar);
        } else {
            // Fallback: insertar después del último campo de metodo
            var refEl = inputMetodo
                ? (inputMetodo.closest('.form-row') || inputMetodo)
                : (inputMuestra ? (inputMuestra.closest('.form-row') || inputMuestra) : null);
            if (refEl && refEl.parentNode) {
                refEl.parentNode.insertBefore(aviso, refEl.nextSibling);
                refEl.parentNode.insertBefore(controlBar, aviso.nextSibling);
            }
        }

        // ── Aplicar bloqueo inicial ─────────────────────────────────────────
        _aplicarBloqueoVisual(inputMuestra, inputMetodo);

        // ── Evento: desbloquear ─────────────────────────────────────────────
        document.getElementById('_mm_btn_modificar').addEventListener('click', function () {
            _desbloquearCampos(inputMuestra, inputMetodo);
        });

        // ── Evento: restaurar ───────────────────────────────────────────────
        document.getElementById('_mm_btn_restaurar').addEventListener('click', function () {
            if (inputMuestra) inputMuestra.value = _templateMuestra;
            if (inputMetodo)  inputMetodo.value  = _templateMetodo;
            _aplicarBloqueoVisual(inputMuestra, inputMetodo);
            document.getElementById('_mm_aviso_loinc').style.display = 'none';
            document.getElementById('_mm_restaurar_wrap').style.display = 'none';
        });
    }

    /** Pone los campos en modo solo lectura (gris, bloqueado). */
    function _aplicarBloqueoVisual(inputMuestra, inputMetodo) {
        [inputMuestra, inputMetodo].forEach(function (inp) {
            if (!inp) return;
            inp.readOnly = true;
            inp.style.background    = '#f5f5f5';
            inp.style.color         = '#555';
            inp.style.cursor        = 'not-allowed';
            inp.style.borderColor   = '#ddd';
            // Ocultar el botón 📋 del SugerenciasDropdownWidget
            var wrap = inp.closest('.sdw-wrap');
            if (wrap) {
                var btn = wrap.querySelector('.sdw-btn');
                if (btn) btn.style.display = 'none';
                // Cerrar menú si estaba abierto
                var ddId = 'dd_' + inp.id.replace('id_', '');
                var dd = document.getElementById(ddId);
                if (dd) dd.style.display = 'none';
            }
        });

        var badge = document.getElementById('_mm_lock_badge');
        var btnMod = document.getElementById('_mm_btn_modificar');
        if (badge) badge.style.display = 'inline-flex';
        if (btnMod) btnMod.style.display = '';
    }

    /** Quita el modo solo lectura y muestra el banner de advertencia. */
    function _desbloquearCampos(inputMuestra, inputMetodo) {
        [inputMuestra, inputMetodo].forEach(function (inp) {
            if (!inp) return;
            inp.readOnly = false;
            inp.style.background  = '';
            inp.style.color       = '';
            inp.style.cursor      = '';
            inp.style.borderColor = '';
            // Restaurar el botón 📋
            var wrap = inp.closest('.sdw-wrap');
            if (wrap) {
                var btn = wrap.querySelector('.sdw-btn');
                if (btn) btn.style.display = '';
            }
        });

        // Ocultar el botón Modificar y el candado
        var badge = document.getElementById('_mm_lock_badge');
        var btnMod = document.getElementById('_mm_btn_modificar');
        if (badge) badge.style.display = 'none';
        if (btnMod) btnMod.style.display = 'none';

        // Mostrar aviso LOINC
        var aviso = document.getElementById('_mm_aviso_loinc');
        if (aviso) aviso.style.display = '';

        // Mostrar opción restaurar solo si hay valores de plantilla que restaurar
        var restaurarWrap = document.getElementById('_mm_restaurar_wrap');
        if (restaurarWrap && (_templateMuestra || _templateMetodo)) {
            restaurarWrap.style.display = 'inline';
        }
    }

    /**
     * Pre-llena tipo_muestra y metodo desde la plantilla via AJAX,
     * luego aplica el bloqueo visual.
     * Si los campos ya tienen valor (modo edición) solo bloquea.
     */
    function prefillYBloquearMuestraMetodo(plantillaId) {
        var inputMuestra = document.getElementById('id_tipo_muestra');
        var inputMetodo  = document.getElementById('id_metodo');

        if (!plantillaId) return;

        var url = '/admin_ext/plantilla/' + plantillaId + '/muestra-metodo/';
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _templateMuestra = data.tipo_muestra || '';
                _templateMetodo  = data.metodo       || '';

                // Solo rellenar si están vacíos (primera vez)
                if (inputMuestra && !inputMuestra.value) {
                    inputMuestra.value = _templateMuestra;
                }
                if (inputMetodo && !inputMetodo.value) {
                    inputMetodo.value = _templateMetodo;
                }

                // Actualizar texto del badge
                var badgeTexto = document.getElementById('_mm_badge_texto');
                if (badgeTexto) {
                    badgeTexto.textContent = _templateMuestra
                        ? 'Heredado de la plantilla'
                        : 'Los campos están protegidos';
                }

                // Si el control bar ya existe, reaplicar bloqueo visual
                if (document.getElementById('_mm_control_bar')) {
                    // Si estaban desbloqueados (el usuario previamente hizo clic en Modificar),
                    // respetar eso. Si estaban bloqueados, reaplicar.
                    var badge = document.getElementById('_mm_lock_badge');
                    var bloqueoActivo = badge && badge.style.display !== 'none';
                    if (bloqueoActivo) {
                        _aplicarBloqueoVisual(inputMuestra, inputMetodo);
                    }
                } else {
                    // El control bar todavía no se creó — setupMuestraMetodoCampos()
                    // se llama desde init() y lo creará después.
                }
            })
            .catch(function () { /* silencioso */ });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CONSTRUIR FILA del inline de resultados
    // ═══════════════════════════════════════════════════════════════════════

    function construirFila(index, prop, esExtra, esExcluida) {
        var nombre   = prop.nombre_propiedad;
        var tipo     = (prop.tipo || 'CUANTITATIVO').trim().toUpperCase();
        var unidad   = prop.unidad || '';
        var opciones = prop.opciones_cualitativas || '';
        var valorMin = prop.valor_min;
        var valorMax = prop.valor_max;
        var pref     = PREFIX + '-' + index;

        var loincNum  = '';
        var loincDesc = '';
        if (esExtra) {
            var loincEntry = _extraLoincMap[String(prop.id)];
            if (loincEntry) {
                loincNum  = loincEntry.loincNum  || '';
                loincDesc = loincEntry.loincDesc || '';
            }
        } else {
            loincNum  = prop.loinc_num  || '';
            loincDesc = prop.loinc_desc || '';
        }

        var tr = document.createElement('tr');
        tr.id        = PREFIX + '-' + index;
        tr.className = 'form-row dynamic-' + PREFIX;
        if (esExcluida) tr.style.cssText = 'opacity:0.45;background:#f5f5f5;';

        // ── Hidden: id + analisis ──────────────────────────────────────────
        var tdId = document.createElement('td');
        tdId.className     = 'original';
        tdId.style.display = 'none';
        ['id','analisis'].forEach(function (campo) {
            var inp = document.createElement('input');
            inp.type  = 'hidden';
            inp.name  = pref + '-' + campo;
            inp.id    = 'id_' + pref + '-' + campo;
            inp.value = '';
            tdId.appendChild(inp);
        });
        tr.appendChild(tdId);

        // ── Columna: propiedad ─────────────────────────────────────────────
        var tdProp = document.createElement('td');
        tdProp.className           = 'field-propiedad';
        tdProp.style.verticalAlign = 'middle';

        var inputPropFk = document.createElement('input');
        inputPropFk.type  = 'hidden';
        inputPropFk.name  = pref + '-propiedad';
        inputPropFk.id    = 'id_' + pref + '-propiedad';
        inputPropFk.value = prop.id || '';
        tdProp.appendChild(inputPropFk);

        var inputPropHidden = document.createElement('input');
        inputPropHidden.type  = 'hidden';
        inputPropHidden.name  = pref + '-propiedad_nombre';
        inputPropHidden.value = nombre;
        tdProp.appendChild(inputPropHidden);

        var spanNombre = document.createElement('span');
        spanNombre.style.cssText = 'font-weight:600;font-size:13px;';
        spanNombre.textContent   = nombre;
        tdProp.appendChild(spanNombre);

        if (esExtra) {
            var badge = document.createElement('span');
            badge.textContent   = ' \u2795 Extra';
            badge.style.cssText = 'font-size:10px;color:#fff;background:#27ae60;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            tdProp.appendChild(badge);
        }
        if (esExcluida) {
            var badgeEx = document.createElement('span');
            badgeEx.textContent   = ' \u2796 Excluida';
            badgeEx.style.cssText = 'font-size:10px;color:#fff;background:#e74c3c;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            tdProp.appendChild(badgeEx);
        }
        tr.appendChild(tdProp);

        // ── Columna: col_loinc_code ────────────────────────────────────────
        var tdLoinc = document.createElement('td');
        tdLoinc.className           = 'field-col_loinc_code';
        tdLoinc.style.verticalAlign = 'middle';
        var divLoinc = document.createElement('div');
        divLoinc.className = 'readonly';
        if (loincNum) {
            divLoinc.innerHTML =
                '<span style="font-family:monospace;font-size:12px;background:#e8f4fd;' +
                'border:1px solid #aac8e8;border-radius:3px;padding:2px 6px;color:#1a5276;">' +
                '\uD83D\uDD2C ' + escHtml(loincNum) + '</span>' +
                (loincDesc
                    ? ' <span style="font-size:11px;color:#555;">' + escHtml(loincDesc) + '</span>'
                    : '');
        } else {
            divLoinc.innerHTML = '<span style="color:#aaa;font-size:11px;">\u2014 sin LOINC \u2014</span>';
        }
        tdLoinc.appendChild(divLoinc);
        tr.appendChild(tdLoinc);

        // ── Columna: valor ─────────────────────────────────────────────────
        var tdValor = document.createElement('td');
        tdValor.className           = 'field-valor';
        tdValor.style.verticalAlign = 'middle';

        if (tipo === 'CUALITATIVO' && opciones) {
            var opsList = opciones.split(',').map(function (o) { return o.trim(); }).filter(Boolean);
            var sel = document.createElement('select');
            sel.name           = pref + '-valor';
            sel.id             = 'id_' + pref + '-valor';
            sel.style.cssText  = 'width:120px;max-width:100%;font-size:13px;';
            if (esExcluida) sel.disabled = true;
            var optBlank = document.createElement('option');
            optBlank.value = ''; optBlank.textContent = '---------';
            sel.appendChild(optBlank);
            opsList.forEach(function (op) {
                var opt = document.createElement('option');
                opt.value = op; opt.textContent = op;
                sel.appendChild(opt);
            });
            tdValor.appendChild(sel);
        } else {
            var inputValor = document.createElement('input');
            inputValor.type          = 'text';
            inputValor.name          = pref + '-valor';
            inputValor.id            = 'id_' + pref + '-valor';
            inputValor.value         = '';
            inputValor.style.cssText = 'width:80px;max-width:100%;font-size:13px;';
            if (esExcluida) inputValor.disabled = true;
            tdValor.appendChild(inputValor);
        }
        tr.appendChild(tdValor);

        // ── Columna: unidad ────────────────────────────────────────────────
        var tdUnidad = document.createElement('td');
        tdUnidad.className           = 'field-unidad';
        tdUnidad.style.verticalAlign = 'middle';
        var unidadVal = (tipo === 'CUALITATIVO') ? 'N/A' : (unidad || '');
        var inputUnidadHidden = document.createElement('input');
        inputUnidadHidden.type  = 'hidden';
        inputUnidadHidden.name  = pref + '-unidad';
        inputUnidadHidden.id    = 'id_' + pref + '-unidad';
        inputUnidadHidden.value = unidadVal;
        tdUnidad.appendChild(inputUnidadHidden);
        var spanUnidad = document.createElement('span');
        spanUnidad.textContent  = unidadVal;
        spanUnidad.style.cssText = 'font-size:13px;color:' +
            (tipo === 'CUALITATIVO' ? '#999;font-style:italic;' : 'inherit;');
        if (tipo === 'CUALITATIVO') spanUnidad.title = 'No aplica para propiedades cualitativas';
        tdUnidad.appendChild(spanUnidad);
        tr.appendChild(tdUnidad);

        // ── Columna: referencia / opciones ─────────────────────────────────
        var tdRef = document.createElement('td');
        tdRef.className = 'field-col_intervalo_referencia';
        tdRef.style.cssText = 'vertical-align:middle;font-size:12px;color:#555;';
        if (tipo === 'CUALITATIVO' && opciones) {
            tdRef.textContent = opciones.split(',').map(function (o) { return o.trim(); }).join(' / ');
        } else if (tipo === 'CUANTITATIVO' && valorMin !== null && valorMin !== undefined &&
                   valorMax !== null && valorMax !== undefined) {
            tdRef.textContent = valorMin + ' \u2013 ' + valorMax + (unidad ? ' ' + unidad : '');
        } else {
            tdRef.textContent = '-';
        }
        tr.appendChild(tdRef);

        // ── Columna: estado del valor ───────────────────────────────────────
        var tdEstado = document.createElement('td');
        tdEstado.className           = 'field-col_valor_coloreado';
        tdEstado.style.verticalAlign = 'middle';
        tdEstado.textContent         = '';
        tr.appendChild(tdEstado);

        // ── Columna: DELETE ─────────────────────────────────────────────────
        var tdDel = document.createElement('td');
        tdDel.className = 'delete';
        if (!esExcluida) {
            var chkDel = document.createElement('input');
            chkDel.type = 'checkbox';
            chkDel.name = pref + '-DELETE';
            chkDel.id   = 'id_' + pref + '-DELETE';
            tdDel.appendChild(chkDel);
        }
        tr.appendChild(tdDel);

        return tr;
    }

    // -------------------------------------------------------
    // PRESERVAR VALORES ESCRITOS POR EL USUARIO
    // -------------------------------------------------------

    function capturarValoresActuales() {
        var valores = {};
        var tbody = getTbodyInline();
        if (!tbody) return valores;
        tbody.querySelectorAll('tr.dynamic-' + PREFIX).forEach(function (fila) {
            var propInput = fila.querySelector('input[name$="-propiedad"]');
            if (!propInput || !propInput.value) return;
            var valorEl = fila.querySelector('[name$="-valor"]');
            if (valorEl) valores[propInput.value] = valorEl.value;
        });
        return valores;
    }

    function restaurarValores(guardados) {
        if (!guardados || !Object.keys(guardados).length) return;
        var tbody = getTbodyInline();
        if (!tbody) return;
        tbody.querySelectorAll('tr.dynamic-' + PREFIX).forEach(function (fila) {
            var propInput = fila.querySelector('input[name$="-propiedad"]');
            if (!propInput || !propInput.value) return;
            var val = guardados[propInput.value];
            if (val === undefined) return;
            var valorEl = fila.querySelector('[name$="-valor"]');
            if (valorEl && !valorEl.disabled) valorEl.value = val;
        });
    }

    // -------------------------------------------------------
    // RENDERIZAR TABLA COMPLETA
    // -------------------------------------------------------

    function renderizarTablaCompleta() {
        var tbody = getTbodyInline();
        if (!tbody || debeBloquearPrecarga()) return;

        var valoresGuardados = capturarValoresActuales();
        limpiarFilasSinPk();
        var index = tbody.querySelectorAll('tr.dynamic-' + PREFIX).length;

        _propiedadesBase.forEach(function (prop) {
            if (!_excluidasSeleccionadas[prop.nombre_propiedad]) {
                tbody.appendChild(construirFila(index++, prop, false, false));
            }
        });
        Object.keys(_extrasSeleccionadas).forEach(function (id) {
            tbody.appendChild(construirFila(index++, _extrasSeleccionadas[id], true, false));
        });
        _propiedadesBase.forEach(function (prop) {
            if (_excluidasSeleccionadas[prop.nombre_propiedad]) {
                tbody.appendChild(construirFila(index++, prop, false, true));
            }
        });

        recalcularTotalForms();
        actualizarHiddens();
        restaurarValores(valoresGuardados);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECCIÓN EXTRAS
    // ═══════════════════════════════════════════════════════════════════════

    function crearSeccionExtras() {
        if (document.getElementById('_seccion_extras')) return;
        var inlineGroup = getInlineGroup();
        if (!inlineGroup) return;

        var wrapper = document.createElement('div');
        wrapper.id            = '_seccion_extras';
        wrapper.style.cssText = 'margin:12px 0;border:1px solid #c8e6c9;border-radius:6px;overflow:hidden;';
        wrapper.innerHTML = [
            '<div style="background:#f1f8e9;padding:10px 14px;display:flex;align-items:center;gap:8px;">',
            '<input type="checkbox" id="_chk_extras" style="cursor:pointer;width:16px;height:16px;">',
            '<label for="_chk_extras" style="cursor:pointer;font-weight:600;color:#2e7d32;margin:0;font-size:13px;">',
            '➕ Agregar propiedades extra a este análisis</label>',
            '</div>',
            '<div id="_extras_body" style="display:none;padding:12px;">',
            '<p style="color:#666;font-size:12px;margin:0 0 8px;">',
            'Propiedades que no pertenecen a la plantilla seleccionada. ',
            'Asigne el <strong>código LOINC</strong> y la <strong>sección</strong> correspondiente.</p>',
            '<div id="_extras_lista" style="max-height:280px;overflow-y:auto;"></div>',
            '</div>',
        ].join('');

        inlineGroup.insertAdjacentElement('afterend', wrapper);

        document.getElementById('_chk_extras').addEventListener('change', function () {
            document.getElementById('_extras_body').style.display = this.checked ? '' : 'none';
            if (!this.checked) {
                _extrasSeleccionadas = {};
                _extraSeccionMap     = {};
                document.querySelectorAll('._chk_prop_extra').forEach(function (c) { c.checked = false; });
                renderizarTablaCompleta();
            }
        });
    }

    /**
     * Construye el select de sección para una propiedad extra.
     * @param {string} propId - ID de la propiedad
     * @returns {HTMLSelectElement}
     */
    function crearSelectSeccion(propId) {
        var sel = document.createElement('select');
        sel.id            = '_sec_sel_extra_' + propId;
        sel.style.cssText = 'font-size:12px;border:1px solid #bbb;border-radius:3px;' +
            'padding:2px 4px;max-width:170px;cursor:pointer;';
        sel.title = 'Serie / Sección del reporte PDF';

        var optBlank = document.createElement('option');
        optBlank.value = ''; optBlank.textContent = '— Sin sección —';
        sel.appendChild(optBlank);

        SECCIONES_SUGERIDAS.forEach(function (sec) {
            var opt = document.createElement('option');
            opt.value = sec; opt.textContent = sec;
            if (_extraSeccionMap[propId] === sec) opt.selected = true;
            sel.appendChild(opt);
        });

        sel.addEventListener('change', function () {
            _extraSeccionMap[propId] = sel.value;
            actualizarHiddens();
        });
        return sel;
    }

    function poblarExtras(propiedadesDisp) {
        var lista = document.getElementById('_extras_lista');
        if (!lista) return;
        lista.innerHTML = '';

        if (!propiedadesDisp || propiedadesDisp.length === 0) {
            lista.innerHTML = '<p style="color:#999;font-size:12px;">No hay propiedades adicionales disponibles.</p>';
            return;
        }

        propiedadesDisp.forEach(function (prop) {
            var propIdStr = String(prop.id);

            // ── Fila principal con checkbox + nombre ─────────────────────────
            var row = document.createElement('div');
            row.style.cssText = [
                'padding:6px 4px',
                'border-bottom:1px solid #f0f0f0',
                'display:flex',
                'flex-direction:column',
                'gap:4px',
            ].join(';');

            var topRow = document.createElement('div');
            topRow.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;';

            var chk = document.createElement('input');
            chk.type      = 'checkbox';
            chk.className = '_chk_prop_extra';
            chk.value     = prop.id;
            if (_extrasSeleccionadas[prop.id]) chk.checked = true;

            var lbl = document.createElement('label');
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;flex:1;min-width:120px;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            topRow.appendChild(chk);
            topRow.appendChild(lbl);
            row.appendChild(topRow);

            // ── Sub-fila con LOINC + Sección (visible solo si está seleccionada) ─
            var subRow = document.createElement('div');
            subRow.id            = '_extra_subrow_' + propIdStr;
            subRow.style.cssText = 'display:' + (_extrasSeleccionadas[prop.id] ? 'flex' : 'none') + ';' +
                'align-items:center;gap:8px;flex-wrap:wrap;padding-left:24px;';

            // ── Label de sección ─────────────────────────────────────────────
            var secLabel = document.createElement('label');
            secLabel.style.cssText = 'font-size:11px;color:#555;margin:0;white-space:nowrap;';
            secLabel.textContent = '📂 Sección:';

            var selectSec = crearSelectSeccion(propIdStr);

            // ── Zona LOINC ───────────────────────────────────────────────────
            var loincWrap = document.createElement('div');
            loincWrap.id            = '_loinc_wrap_extra_' + propIdStr;
            loincWrap.style.cssText = 'display:flex;align-items:center;gap:4px;';

            var loincDisplay = document.createElement('span');
            loincDisplay.id = '_loinc_display_extra_' + propIdStr;
            var loincEntry = _extraLoincMap[propIdStr];
            if (loincEntry && loincEntry.loincNum) {
                loincDisplay.innerHTML =
                    '<span style="color:#1a6fa8;font-weight:600;font-size:12px;font-family:monospace;">' +
                    escHtml(loincEntry.loincNum) + '</span>' +
                    (loincEntry.loincDesc
                        ? '<span style="color:#555;font-size:11px;margin-left:4px;">\u2014 ' + escHtml(loincEntry.loincDesc) + '</span>'
                        : '');
            } else {
                loincDisplay.innerHTML = '<span style="color:#999;font-size:11px;">Sin c\u00F3digo LOINC</span>';
            }

            var loincBtn = document.createElement('button');
            loincBtn.type      = 'button';
            loincBtn.className = 'pp-extra-loinc-btn';
            loincBtn.title     = 'Buscar y asignar código LOINC';
            loincBtn.style.cssText =
                'border:1px solid #1a6fa8;background:#e8f0fe;color:#1a6fa8;' +
                'border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;white-space:nowrap;';
            loincBtn.textContent = '\uD83D\uDD0D LOINC';
            loincBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                mostrarExtraLoincPopup(propIdStr, loincBtn, prop.nombre_propiedad);
            });

            loincWrap.appendChild(loincDisplay);
            loincWrap.appendChild(loincBtn);

            subRow.appendChild(secLabel);
            subRow.appendChild(selectSec);
            subRow.appendChild(loincWrap);
            row.appendChild(subRow);

            // ── Evento checkbox ─────────────────────────────────────────────
            chk.addEventListener('change', function () {
                var subRowEl = document.getElementById('_extra_subrow_' + propIdStr);
                if (this.checked) {
                    _extrasSeleccionadas[prop.id] = prop;
                    if (subRowEl) subRowEl.style.display = 'flex';
                } else {
                    delete _extrasSeleccionadas[prop.id];
                    delete _extraLoincMap[propIdStr];
                    delete _extraSeccionMap[propIdStr];
                    if (subRowEl) subRowEl.style.display = 'none';
                }
                renderizarTablaCompleta();
                actualizarHiddens();
            });

            lista.appendChild(row);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECCIÓN EXCLUIR
    // ═══════════════════════════════════════════════════════════════════════

    function crearSeccionExcluir() {
        if (document.getElementById('_seccion_excluir')) return;
        var inlineGroup = getInlineGroup();
        if (!inlineGroup) return;

        var wrapper = document.createElement('div');
        wrapper.id            = '_seccion_excluir';
        wrapper.style.cssText = 'margin:12px 0;border:1px solid #ffccbc;border-radius:6px;overflow:hidden;';
        wrapper.innerHTML = [
            '<div style="background:#fff3e0;padding:10px 14px;display:flex;align-items:center;gap:8px;">',
            '<input type="checkbox" id="_chk_excluir" style="cursor:pointer;width:16px;height:16px;">',
            '<label for="_chk_excluir" style="cursor:pointer;font-weight:600;color:#bf360c;margin:0;font-size:13px;">',
            '➖ Excluir propiedades de la plantilla en este análisis</label>',
            '</div>',
            '<div id="_excluir_body" style="display:none;padding:12px;">',
            '<p style="color:#666;font-size:12px;margin:0 0 8px;">',
            'Las marcadas no se incluirán en este análisis y aparecerán en gris.</p>',
            '<div id="_excluir_lista" style="max-height:220px;overflow-y:auto;"></div>',
            '</div>',
        ].join('');

        var seccionExtras = document.getElementById('_seccion_extras');
        if (seccionExtras) {
            seccionExtras.insertAdjacentElement('beforebegin', wrapper);
        } else {
            inlineGroup.insertAdjacentElement('afterend', wrapper);
        }

        document.getElementById('_chk_excluir').addEventListener('change', function () {
            document.getElementById('_excluir_body').style.display = this.checked ? '' : 'none';
            if (!this.checked) {
                _excluidasSeleccionadas = {};
                document.querySelectorAll('._chk_prop_excluir').forEach(function (c) { c.checked = false; });
                renderizarTablaCompleta();
            }
        });
    }

    function poblarExcluir(propiedadesBase) {
        var lista = document.getElementById('_excluir_lista');
        if (!lista) return;
        lista.innerHTML = '';

        if (!propiedadesBase || propiedadesBase.length === 0) {
            lista.innerHTML = '<p style="color:#999;font-size:12px;">No hay propiedades en la plantilla.</p>';
            return;
        }

        propiedadesBase.forEach(function (prop) {
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 2px;border-bottom:1px solid #f0f0f0;';

            var chk = document.createElement('input');
            chk.type      = 'checkbox';
            chk.className = '_chk_prop_excluir';
            chk.value     = prop.nombre_propiedad;
            if (_excluidasSeleccionadas[prop.nombre_propiedad]) chk.checked = true;

            chk.addEventListener('change', function () {
                if (this.checked) { _excluidasSeleccionadas[prop.nombre_propiedad] = true; }
                else              { delete _excluidasSeleccionadas[prop.nombre_propiedad]; }
                renderizarTablaCompleta();
                actualizarHiddens();
            });

            var lbl = document.createElement('label');
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;flex:1;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            row.appendChild(chk);
            row.appendChild(lbl);

            if (prop.loinc_num) {
                var loincTag = document.createElement('span');
                loincTag.title         = prop.loinc_desc || prop.loinc_num;
                loincTag.style.cssText =
                    'font-family:monospace;font-size:11px;color:#1a5276;' +
                    'background:#e8f4fd;border:1px solid #aac8e8;border-radius:3px;' +
                    'padding:1px 5px;white-space:nowrap;';
                loincTag.textContent = '\uD83D\uDD2C ' + prop.loinc_num;
                row.appendChild(loincTag);
            }

            lista.appendChild(row);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // HIDDENS para el submit
    // ═══════════════════════════════════════════════════════════════════════

    function getForm() {
        return document.querySelector('#content-main form') ||
               document.querySelector('form.change-form') ||
               document.querySelector('form');
    }

    function setHidden(id, name, value) {
        var el = document.getElementById(id);
        if (!el) {
            el       = document.createElement('input');
            el.type  = 'hidden';
            el.id    = id;
            el.name  = name;
            var f = getForm();
            if (f) f.appendChild(el);
        }
        el.value = value;
    }

    function actualizarHiddens() {
        var extraIds = Object.keys(_extrasSeleccionadas);

        setHidden('_hidden_extras',      '_propiedades_extra_ids',
            extraIds.join(','));

        setHidden('_hidden_excluidas',   '_propiedades_excluidas_nombres',
            Object.keys(_excluidasSeleccionadas).join(','));

        // LOINCs paralelos a los ids de extras
        var loincIds = extraIds.map(function (id) {
            return (_extraLoincMap[id] && _extraLoincMap[id].loincId)
                ? _extraLoincMap[id].loincId : '';
        });
        setHidden('_hidden_extras_loinc', '_propiedades_extra_loinc_ids', loincIds.join(','));

        // ← NUEVO: secciones paralelas a los ids de extras
        var secciones = extraIds.map(function (id) {
            return _extraSeccionMap[id] || '';
        });
        setHidden('_hidden_extras_secciones', '_propiedades_extra_secciones', secciones.join(','));
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LOINC PICKER PARA PROPIEDADES EXTRA
    // ═══════════════════════════════════════════════════════════════════════

    var _extraLoincPopup    = null;
    var _extraLoincDebounce = null;
    var _extraLoincPropId   = null;

    function getLoincAdminBase() {
        var m = window.location.pathname.match(/^(\/admin\/[^/]+\/analisis\/)/i);
        return m ? m[1] : '/admin/LabApp/analisis/';
    }

    function getMuestraAnalisis() {
        var el = document.getElementById('id_tipo_muestra');
        return el ? el.value.trim() : '';
    }

    function getMetodoAnalisis() {
        var el = document.getElementById('id_metodo');
        return el ? el.value.trim() : '';
    }

    function crearExtraLoincPopup() {
        if (_extraLoincPopup) return _extraLoincPopup;
        var popup = document.createElement('div');
        popup.id = 'pp-extra-loinc-popup';
        popup.style.cssText = [
            'display:none', 'position:fixed', 'z-index:999999',
            'background:#fff', 'border:1px solid #bbb', 'border-radius:6px',
            'box-shadow:0 4px 20px rgba(0,0,0,.22)', 'padding:8px',
            'min-width:360px', 'max-width:600px', 'box-sizing:border-box',
        ].join(';');
        popup.innerHTML = [
            '<div style="display:flex;gap:6px;align-items:center;margin-bottom:6px;">',
            '<input id="pp-extra-loinc-inp" type="text" autocomplete="off"',
            ' placeholder="Buscar código LOINC..." style="flex:1;box-sizing:border-box;',
            'padding:6px 10px;border:1px solid #bbb;border-radius:4px;font-size:13px;">',
            '<a id="pp-extra-loinc-extbtn" href="https://loinc.org/search/" target="_blank"',
            ' title="Buscar en loinc.org" style="display:inline-flex;align-items:center;',
            'gap:3px;padding:5px 8px;background:#1a6fa8;color:#fff;border-radius:4px;',
            'text-decoration:none;font-size:12px;white-space:nowrap;flex-shrink:0;">',
            '\uD83C\uDF10 LOINC.org</a>',
            '</div>',
            '<div id="pp-extra-loinc-results" style="max-height:240px;overflow-y:auto;',
            'border-top:1px solid #eee;padding-top:4px;">',
            '<div style="color:#999;font-size:12px;padding:6px;">Escribe para buscar\u2026</div>',
            '</div>',
        ].join('');
        document.body.appendChild(popup);

        var inp = popup.querySelector('#pp-extra-loinc-inp');
        inp.addEventListener('input', function () {
            var q = inp.value.trim();
            var extBtn = document.getElementById('pp-extra-loinc-extbtn');
            if (extBtn) extBtn.href = q
                ? 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(q)
                : 'https://loinc.org/search/';
            clearTimeout(_extraLoincDebounce);
            var resEl = document.getElementById('pp-extra-loinc-results');
            if (q.length < 2) {
                if (resEl) resEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Escribe al menos 2 caracteres\u2026</div>';
                return;
            }
            _extraLoincDebounce = setTimeout(function () {
                buscarLoincExtra(q, _extraLoincPropId);
            }, 280);
        });
        inp.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') cerrarExtraLoincPopup();
        });
        _extraLoincPopup = popup;
        return popup;
    }

    function mostrarExtraLoincPopup(propId, btnEl, nombreProp) {
        var popup  = crearExtraLoincPopup();
        _extraLoincPropId = propId;
        var rect   = btnEl.getBoundingClientRect();
        var popupW = 380, popupH = 300;
        popup.style.display = 'block';
        var top  = (window.innerHeight - rect.bottom >= popupH || rect.top < popupH)
            ? rect.bottom + 4 : rect.top - popupH - 4;
        var left = Math.min(rect.left, window.innerWidth - popupW - 8);
        popup.style.top  = top  + 'px';
        popup.style.left = left + 'px';

        var inp = document.getElementById('pp-extra-loinc-inp');
        if (inp) {
            inp.value = nombreProp || '';
            inp.focus(); inp.select();
            var extBtn = document.getElementById('pp-extra-loinc-extbtn');
            if (extBtn && nombreProp)
                extBtn.href = 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(nombreProp);
        }
        var resEl = document.getElementById('pp-extra-loinc-results');
        if (resEl) {
            if (nombreProp && nombreProp.length >= 2) {
                resEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Buscando\u2026</div>';
                buscarLoincExtra(nombreProp, propId);
            } else {
                resEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Escribe para buscar\u2026</div>';
            }
        }
    }

    function cerrarExtraLoincPopup() {
        if (_extraLoincPopup) _extraLoincPopup.style.display = 'none';
        _extraLoincPropId = null;
    }

    document.addEventListener('click', function (e) {
        if (!_extraLoincPopup || _extraLoincPopup.style.display === 'none') return;
        if (!e.target.closest('#pp-extra-loinc-popup') && !e.target.closest('.pp-extra-loinc-btn'))
            cerrarExtraLoincPopup();
    });
    ['scroll', 'resize'].forEach(function (ev) {
        window.addEventListener(ev, function (e) {
            if (!_extraLoincPopup || _extraLoincPopup.style.display === 'none') return;
            if (_extraLoincPopup.contains(e.target)) return;
            cerrarExtraLoincPopup();
        }, true);
    });

    function buscarLoincExtra(q, propId) {
        var resEl = document.getElementById('pp-extra-loinc-results');
        if (!resEl) return;
        var muestra = getMuestraAnalisis();
        var metodo  = getMetodoAnalisis();
        var url = getLoincAdminBase() + 'loinc-buscar/?q=' + encodeURIComponent(q);
        if (muestra) url += '&muestra=' + encodeURIComponent(muestra);
        if (metodo)  url += '&metodo='  + encodeURIComponent(metodo);

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (_extraLoincPropId !== propId) return;
                resEl = document.getElementById('pp-extra-loinc-results');
                if (!resEl) return;
                if (!data.results || data.results.length === 0) {
                    resEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Sin resultados.</div>';
                    return;
                }
                resEl.innerHTML = '';
                if (data.filtrado && (data.muestra || data.metodo)) {
                    var badge = document.createElement('div');
                    badge.style.cssText = 'font-size:11px;color:#1a6fa8;padding:3px 6px;margin-bottom:4px;background:#e8f0fe;border-radius:3px;';
                    badge.textContent = '\uD83E\uDDEA Filtrado por: ' + [data.muestra, data.metodo].filter(Boolean).join(' \u00B7 ');
                    resEl.appendChild(badge);
                }
                data.results.forEach(function (lc) {
                    var row = document.createElement('div');
                    row.style.cssText = 'padding:6px 8px;cursor:pointer;border-bottom:1px solid #f0f0f0;font-size:12px;';
                    row.onmouseover = function () { row.style.background = '#e8f0fe'; };
                    row.onmouseout  = function () { row.style.background = ''; };
                    var meta = [lc.system, lc.property, lc.scale_typ, lc.method_typ ? '\u2699 ' + lc.method_typ : ''].filter(Boolean).join(' \u00B7 ');
                    row.innerHTML =
                        '<span style="font-weight:600;color:#1a6fa8;">' + escHtml(lc.loinc_num) + '</span>' +
                        ' <span>' + escHtml(lc.shortname || lc.component || '') + '</span>' +
                        (meta ? '<br><span style="color:#888;font-size:11px;">' + escHtml(meta) + '</span>' : '');
                    row.addEventListener('click', function (ev) {
                        ev.stopPropagation();
                        _extraLoincMap[propId] = {
                            loincId:   String(lc.id),
                            loincNum:  lc.loinc_num,
                            loincDesc: lc.shortname || lc.component || '',
                        };
                        cerrarExtraLoincPopup();
                        actualizarHiddens();
                        actualizarDisplayLoincExtra(propId);
                        renderizarTablaCompleta();
                    });
                    resEl.appendChild(row);
                });
            })
            .catch(function () {
                var el = document.getElementById('pp-extra-loinc-results');
                if (el) el.innerHTML = '<div style="color:#c0392b;font-size:12px;padding:6px;">Error de conexi\u00F3n.</div>';
            });
    }

    function actualizarDisplayLoincExtra(propId) {
        var displayEl = document.getElementById('_loinc_display_extra_' + propId);
        if (!displayEl) return;
        var loinc = _extraLoincMap[propId];
        displayEl.innerHTML = '';
        if (loinc && loinc.loincNum) {
            var numSpan = document.createElement('span');
            numSpan.style.cssText = 'color:#1a6fa8;font-weight:600;font-size:12px;font-family:monospace;';
            numSpan.textContent   = loinc.loincNum;
            displayEl.appendChild(numSpan);
            if (loinc.loincDesc) {
                var descSpan = document.createElement('span');
                descSpan.style.cssText = 'color:#555;font-size:11px;margin-left:4px;';
                descSpan.textContent   = '\u2014 ' + loinc.loincDesc;
                displayEl.appendChild(descSpan);
            }
            var clearBtn = document.createElement('button');
            clearBtn.type            = 'button';
            clearBtn.style.cssText   = 'border:none;background:none;color:#c0392b;cursor:pointer;font-size:11px;padding:0 4px;';
            clearBtn.textContent     = '\u2715';
            clearBtn.title           = 'Quitar LOINC';
            clearBtn.addEventListener('click', function () {
                delete _extraLoincMap[propId];
                actualizarHiddens();
                actualizarDisplayLoincExtra(propId);
                renderizarTablaCompleta();
            });
            displayEl.appendChild(clearBtn);
        } else {
            var empty = document.createElement('span');
            empty.style.cssText = 'color:#999;font-size:11px;';
            empty.textContent   = 'Sin c\u00F3digo LOINC';
            displayEl.appendChild(empty);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CONSULTAS AL SERVIDOR
    // ═══════════════════════════════════════════════════════════════════════

    function getSelectValue(id) {
        var el = document.getElementById(id);
        return el ? el.value : '';
    }

    function consultarPlantilla(plantillaId, callback) {
        if (!plantillaId) {
            limpiarFilasSinPk();
            recalcularTotalForms();
            callback('', [], []);
            return;
        }
        var pacienteId = getSelectValue('id_paciente');
        var urlTipo  = '/admin_ext/plantilla/' + plantillaId + '/tipo_formato/';
        var urlProps = '/admin_ext/plantilla/' + plantillaId + '/propiedades/'
                       + (pacienteId ? '?paciente_id=' + pacienteId : '');
        var urlDisp  = '/admin_ext/propiedades_disponibles/?plantilla_id=' + plantillaId
                       + (pacienteId ? '&paciente_id=' + pacienteId : '');

        Promise.all([
            fetch(urlTipo,  { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
            fetch(urlProps, { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
            fetch(urlDisp,  { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
        ])
        .then(function (res) {
            callback(res[0].tipo_formato || '', res[1].propiedades || [], res[2].propiedades || []);
        })
        .catch(function () { callback('', [], []); });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LÓGICA CENTRAL
    // ═══════════════════════════════════════════════════════════════════════

    function onSeleccionCambio() {
        if (debeBloquearPrecarga()) return;

        _extrasSeleccionadas    = {};
        _excluidasSeleccionadas = {};
        _extraSeccionMap        = {};

        var plantillaId = getSelectValue('id_plantilla');

        // Pre-llenar y bloquear muestra/método desde la plantilla
        if (plantillaId) {
            prefillYBloquearMuestraMetodo(plantillaId);
        }

        consultarPlantilla(plantillaId, function (tipoFormato, propiedadesBase, propiedadesDisp) {
            mostrarOcultarImagenes(tipoFormato);
            _propiedadesBase = propiedadesBase;

            ['_chk_extras', '_chk_excluir'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.checked = false;
            });
            ['_extras_body', '_excluir_body'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });

            if (propiedadesBase.length > 0) {
                crearSeccionExtras();
                crearSeccionExcluir();
                poblarExcluir(propiedadesBase);
                poblarExtras(propiedadesDisp);
                renderizarTablaCompleta();
            } else {
                limpiarFilasSinPk();
                recalcularTotalForms();
                actualizarHiddens();
            }
        });
    }

    function onCargaInicialEdicion(plantillaId) {
        fetch('/admin_ext/plantilla/' + plantillaId + '/tipo_formato/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (r) { return r.json(); })
        .then(function (d) { mostrarOcultarImagenes(d.tipo_formato || ''); })
        .catch(function () {});
    }

    // -------------------------------------------------------
    // BIND SELECT2 + FALLBACK NATIVO
    // -------------------------------------------------------

    function bindSelect2(selectId, handler) {
        var intentos = 0;

        function enganchar() {
            if (window.django && window.django.jQuery) {
                var $sel = window.django.jQuery('#' + selectId);
                if ($sel.length) {
                    $sel.on('select2:select select2:clear change', handler);
                }
            }
            var selectEl = document.getElementById(selectId);
            if (selectEl) {
                selectEl.addEventListener('change', handler);
            }
        }

        function intentar() {
            var selectEl = document.getElementById(selectId);
            if (selectEl) {
                enganchar();
                return;
            }
            if (intentos++ < 50) setTimeout(intentar, 100);
        }
        intentar();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════════════

    function init() {
        // Ocultar sección imágenes al inicio
        mostrarOcultarImagenes('');

        // ── Botón LOINC.org en el encabezado del inline ────────────────────
        (function agregarBotonLoinc() {
            var grupo = getInlineGroup();
            if (!grupo) return;
            if (document.getElementById('_btn_loinc_org')) return;
            var h2 = grupo.querySelector('h2');
            if (!h2) return;
            var a = document.createElement('a');
            a.id        = '_btn_loinc_org';
            a.href      = 'https://loinc.org/search/';
            a.target    = '_blank';
            a.rel       = 'noopener noreferrer';
            a.title     = 'Abre el buscador oficial de LOINC.org en una nueva pestaña';
            a.style.cssText =
                'margin-left:14px;display:inline-flex;align-items:center;gap:4px;' +
                'padding:3px 10px;background:#1a6fa8;color:#fff;border-radius:4px;' +
                'text-decoration:none;font-size:12px;vertical-align:middle;' +
                'font-weight:normal;white-space:nowrap;';
            a.innerHTML = '\uD83C\uDF10 Buscar en LOINC.org';
            h2.appendChild(a);
        })();

        // ── Setup de bloqueo de muestra/método ────────────────────────────
        // Se llama aquí para ambos modos (alta y edición).
        setupMuestraMetodoCampos();

        // ── Bindings de selects ────────────────────────────────────────────
        bindSelect2('id_plantilla', function () {
            if (!debeBloquearPrecarga()) onSeleccionCambio();
        });
        bindSelect2('id_paciente', function () {
            if (!debeBloquearPrecarga()) onSeleccionCambio();
        });

        setTimeout(function () {
            var plantillaId = getSelectValue('id_plantilla');
            if (!plantillaId) return;
            if (debeBloquearPrecarga()) {
                onCargaInicialEdicion(plantillaId);
                // En modo edición, los campos ya tienen valor desde Django.
                // Simplemente aplicar el bloqueo visual con los valores actuales.
                var inputMuestra = document.getElementById('id_tipo_muestra');
                var inputMetodo  = document.getElementById('id_metodo');
                if (inputMuestra) _templateMuestra = inputMuestra.value;
                if (inputMetodo)  _templateMetodo  = inputMetodo.value;
                _aplicarBloqueoVisual(inputMuestra, inputMetodo);
                var badgeTexto = document.getElementById('_mm_badge_texto');
                if (badgeTexto && (_templateMuestra || _templateMetodo)) {
                    badgeTexto.textContent = 'Valores actuales del análisis';
                }
            } else {
                onSeleccionCambio();
            }
        }, 800);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
