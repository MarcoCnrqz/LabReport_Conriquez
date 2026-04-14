/**
 * analisis_imagenes_toggle.js
 * v15 — FIX: construirFila ahora incluye input hidden `propiedad` (FK id)
 * para evitar IntegrityError NOT NULL en propiedad_id al guardar.
 * No depende de #resultados-empty.
 * Construye filas directamente en el tbody del inline.
 * Incluye secciones de propiedades extra y excluidas.
 */

(function () {
    'use strict';

    var PREFIX = 'resultados';

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
        fieldset.style.display = (tipoFormato === 'IMAGENES_RESULTADOS') ? '' : 'none';
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

    function getColumnas() {
        // Leer las columnas del thead del inline para saber cuántas <td> crear
        var thead = document.querySelector('#' + PREFIX + '-group thead tr');
        if (!thead) return ['propiedad', 'nombre_propiedad', 'col_loinc_code', 'valor', 'unidad', 'col_intervalo_referencia', 'col_valor_coloreado', 'DELETE'];
        var cols = [];
        thead.querySelectorAll('th').forEach(function (th) {
            cols.push(th.className || th.textContent.trim());
        });
        return cols;
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

    // -------------------------------------------------------
    // Estado global
    // -------------------------------------------------------
    var _propiedadesBase        = [];
    var _extrasSeleccionadas    = {}; // { id: propObj }
    var _excluidasSeleccionadas = {}; // { nombre_propiedad: true }
    var _extraLoincMap        = {}; // { propId: { loincId, loincNum, loincDesc } }

    // -------------------------------------------------------
    // CONSTRUIR FILA sin depender del empty form
    // -------------------------------------------------------

    function construirFila(index, prop, esExtra, esExcluida) {
        var nombre   = prop.nombre_propiedad;
        var tipo     = (prop.tipo || 'CUANTITATIVO').trim().toUpperCase();
        var unidad   = prop.unidad || '';
        var opciones = prop.opciones_cualitativas || '';
        var valorMin = prop.valor_min;
        var valorMax = prop.valor_max;
        var pref     = PREFIX + '-' + index;

        // LOINC: propiedades base → prop.loinc_num / prop.loinc_desc
        //        propiedades extra → _extraLoincMap[prop.id]
        var loincNum  = '';
        var loincDesc = '';
        if (esExtra) {
            var loincEntry = _extraLoincMap[String(prop.id)] || _extraLoincMap[prop.id];
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

        // ════════════════════════════════════════════════════════════
        // NOTA SOBRE EL ORDEN DE COLUMNAS:
        // Django TabularInline renderiza exactamente los campos en el
        // orden del atributo `fields`. Para ResultadoAnalisisInline:
        //
        //   fields = ('propiedad', 'nombre_propiedad', 'col_loinc_code',
        //             'valor', 'unidad',
        //             'col_intervalo_referencia', 'col_valor_coloreado')
        //
        // Los campos en readonly_fields se renderizan como <div class="readonly">
        // dentro de su <td> — NO generan <input>.
        // Los campos editables (valor, unidad) generan <input>.
        // El <td class="original"> del pk siempre va primero (oculto).
        //
        // Orden real del TR:
        //   td.original(hidden) |
        //   td.field-propiedad(readonly·div) |
        //   td.field-nombre_propiedad(readonly·div) |
        //   td.field-col_loinc_code(readonly·div) |
        //   td.field-valor(input) |
        //   td.field-unidad(input) |
        //   td.field-col_intervalo_referencia(readonly·div) |
        //   td.field-col_valor_coloreado(readonly·div) |
        //   td.delete
        // ════════════════════════════════════════════════════════════

        // ── td.original — id pk (oculto) + analisis (oculto) ───────
        var tdId = document.createElement('td');
        tdId.className    = 'original';
        tdId.style.display = 'none';

        var inputId = document.createElement('input');
        inputId.type = 'hidden'; inputId.name = pref + '-id';
        inputId.id   = 'id_' + pref + '-id'; inputId.value = '';
        tdId.appendChild(inputId);

        var inputAnalisis = document.createElement('input');
        inputAnalisis.type = 'hidden'; inputAnalisis.name = pref + '-analisis';
        inputAnalisis.id   = 'id_' + pref + '-analisis'; inputAnalisis.value = '';
        tdId.appendChild(inputAnalisis);

        // FK hidden de propiedad — lo metemos aquí para no afectar el conteo
        // de columnas visibles. Django lo lee del POST por name, no por posición.
        var inputPropFk = document.createElement('input');
        inputPropFk.type  = 'hidden';
        inputPropFk.name  = pref + '-propiedad';
        inputPropFk.id    = 'id_' + pref + '-propiedad';
        inputPropFk.value = String(prop.id || '');
        tdId.appendChild(inputPropFk);

        var inputPropNombre = document.createElement('input');
        inputPropNombre.type  = 'hidden';
        inputPropNombre.name  = pref + '-propiedad_nombre';
        inputPropNombre.value = nombre;
        tdId.appendChild(inputPropNombre);

        tr.appendChild(tdId);

        // ── td.field-propiedad — readonly div (col 1) ──────────────
        var tdProp = document.createElement('td');
        tdProp.className           = 'field-propiedad';
        tdProp.style.verticalAlign = 'middle';

        var divProp = document.createElement('div');
        divProp.className = 'readonly';

        var spanNombre = document.createElement('span');
        spanNombre.style.cssText = 'font-weight:600;font-size:13px;';
        spanNombre.textContent   = nombre;
        divProp.appendChild(spanNombre);

        if (esExtra) {
            var badge = document.createElement('span');
            badge.textContent   = ' ➕ Extra';
            badge.style.cssText = 'font-size:10px;color:#fff;background:#27ae60;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            divProp.appendChild(badge);
        }
        if (esExcluida) {
            var badgeEx = document.createElement('span');
            badgeEx.textContent   = ' ➖ Excluida';
            badgeEx.style.cssText = 'font-size:10px;color:#fff;background:#e74c3c;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            divProp.appendChild(badgeEx);
        }
        tdProp.appendChild(divProp);
        tr.appendChild(tdProp);

        // ── td.field-nombre_propiedad — readonly div (col 2) ───────
        var tdNombre = document.createElement('td');
        tdNombre.className           = 'field-nombre_propiedad';
        tdNombre.style.verticalAlign = 'middle';
        var divNombre = document.createElement('div');
        divNombre.className   = 'readonly';
        divNombre.textContent = nombre;
        divNombre.style.cssText = 'font-size:13px;';
        tdNombre.appendChild(divNombre);
        tr.appendChild(tdNombre);

        // ── td.field-col_loinc_code — readonly div (col 3) ─────────
        var tdLoinc = document.createElement('td');
        tdLoinc.className           = 'field-col_loinc_code';
        tdLoinc.style.verticalAlign = 'middle';
        var divLoinc = document.createElement('div');
        divLoinc.className = 'readonly';
        if (loincNum) {
            divLoinc.innerHTML =
                '<span style="font-family:monospace;font-size:12px;background:#e8f4fd;' +
                'border:1px solid #aac8e8;border-radius:3px;padding:2px 6px;color:#1a5276;">' +
                '🔬 ' + escHtml(loincNum) + '</span>' +
                (loincDesc ? ' <span style="font-size:11px;color:#555;">' + escHtml(loincDesc) + '</span>' : '');
        } else {
            divLoinc.innerHTML = '<span style="color:#aaa;font-size:11px;">—</span>';
        }
        tdLoinc.appendChild(divLoinc);
        tr.appendChild(tdLoinc);

        // ── td.field-valor — input editable (col 4) ────────────────
        var tdValor = document.createElement('td');
        tdValor.className           = 'field-valor';
        tdValor.style.verticalAlign = 'middle';

        if (tipo === 'CUALITATIVO' && opciones) {
            var opsList = opciones.split(',').map(function(o){ return o.trim(); }).filter(Boolean);
            var sel = document.createElement('select');
            sel.name = pref + '-valor'; sel.id = 'id_' + pref + '-valor';
            sel.style.cssText = 'width:100%;font-size:13px;';
            if (esExcluida) sel.disabled = true;
            var optBlank = document.createElement('option');
            optBlank.value = ''; optBlank.textContent = '---------';
            sel.appendChild(optBlank);
            opsList.forEach(function(op) {
                var opt = document.createElement('option');
                opt.value = op; opt.textContent = op;
                sel.appendChild(opt);
            });
            tdValor.appendChild(sel);
        } else {
            var inputValor = document.createElement('input');
            inputValor.type  = 'text';
            inputValor.name  = pref + '-valor';
            inputValor.id    = 'id_' + pref + '-valor';
            inputValor.value = '';
            inputValor.style.cssText = 'width:100%;font-size:13px;';
            if (esExcluida) {
                inputValor.disabled      = true;
                inputValor.style.cssText += 'pointer-events:none;';
            }
            tdValor.appendChild(inputValor);
        }
        tr.appendChild(tdValor);

        // ── td.field-unidad — input editable (col 5) ───────────────
        var tdUnidad = document.createElement('td');
        tdUnidad.className           = 'field-unidad';
        tdUnidad.style.verticalAlign = 'middle';

        var inputUnidad = document.createElement('input');
        inputUnidad.type = 'text';
        inputUnidad.name = pref + '-unidad';
        inputUnidad.id   = 'id_' + pref + '-unidad';
        if (tipo === 'CUALITATIVO') {
            inputUnidad.value         = 'N/A';
            inputUnidad.disabled      = true;
            inputUnidad.style.cssText = ESTILO_UNIDAD_NA;
            inputUnidad.setAttribute('title', 'No aplica para propiedades cualitativas');
        } else {
            inputUnidad.value         = unidad;
            inputUnidad.readOnly      = true;
            inputUnidad.style.cssText = ESTILO_READONLY;
        }
        tdUnidad.appendChild(inputUnidad);
        tr.appendChild(tdUnidad);

        // ── td.field-col_intervalo_referencia — readonly div (col 6) ─
        var tdRef = document.createElement('td');
        tdRef.className           = 'field-col_intervalo_referencia';
        tdRef.style.verticalAlign = 'middle';
        var divRef = document.createElement('div');
        divRef.className = 'readonly';

        if (tipo === 'CUALITATIVO' && opciones) {
            divRef.style.cssText = 'font-size:12px;color:#555;';
            divRef.textContent   = opciones.split(',').map(function(o){ return o.trim(); }).join(' / ');
        } else if (
            tipo === 'CUANTITATIVO' &&
            valorMin !== null && valorMin !== undefined && String(valorMin) !== '' &&
            valorMax !== null && valorMax !== undefined && String(valorMax) !== ''
        ) {
            divRef.innerHTML =
                '<span style="display:inline-block;background:#eaf4fb;border:1px solid #aad4ee;' +
                'border-radius:4px;padding:2px 8px;font-size:12px;color:#1a5276;white-space:nowrap;">' +
                '📏 ' + escHtml(String(valorMin)) + ' – ' + escHtml(String(valorMax)) +
                (unidad ? ' <em style="color:#777;">' + escHtml(unidad) + '</em>' : '') +
                '</span>';
        } else {
            divRef.style.cssText = 'font-size:12px;color:#aaa;';
            divRef.textContent   = '—';
        }
        tdRef.appendChild(divRef);
        tr.appendChild(tdRef);

        // ── td.field-col_valor_coloreado — readonly div (col 7) ────
        var tdEstado = document.createElement('td');
        tdEstado.className           = 'field-col_valor_coloreado';
        tdEstado.style.verticalAlign = 'middle';
        var divEstado = document.createElement('div');
        divEstado.className   = 'readonly';
        divEstado.textContent = '';
        tdEstado.appendChild(divEstado);
        tr.appendChild(tdEstado);

        // ── td.delete — checkbox eliminar (col 8) ──────────────────
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
    // RENDERIZAR TABLA COMPLETA
    // -------------------------------------------------------

    function capturarValoresActuales() {
        var valores = {};
        var tbody = getTbodyInline();
        if (!tbody) return valores;
        tbody.querySelectorAll('tr.dynamic-' + PREFIX).forEach(function (fila) {
            var propInput = fila.querySelector('input[name$="-propiedad"]');
            if (!propInput || !propInput.value) return;
            var propId = propInput.value;
            var valorEl = fila.querySelector('[name$="-valor"]');
            if (valorEl) valores[propId] = valorEl.value;
        });
        return valores;
    }

    function restaurarValores(valoresGuardados) {
        if (!valoresGuardados || Object.keys(valoresGuardados).length === 0) return;
        var tbody = getTbodyInline();
        if (!tbody) return;
        tbody.querySelectorAll('tr.dynamic-' + PREFIX).forEach(function (fila) {
            var propInput = fila.querySelector('input[name$="-propiedad"]');
            if (!propInput || !propInput.value) return;
            var propId = propInput.value;
            if (valoresGuardados[propId] !== undefined) {
                var valorEl = fila.querySelector('[name$="-valor"]');
                if (valorEl && !valorEl.disabled) valorEl.value = valoresGuardados[propId];
            }
        });
    }

    function renderizarTablaCompleta() {
        var tbody = getTbodyInline();
        if (!tbody || debeBloquearPrecarga()) return;

        // BUG FIX: Guardar valores escritos por el usuario antes de reconstruir
        var valoresGuardados = capturarValoresActuales();

        limpiarFilasSinPk();

        var index = tbody.querySelectorAll('tr.dynamic-' + PREFIX).length;

        // 1. Propiedades base NO excluidas
        _propiedadesBase.forEach(function (prop) {
            if (!_excluidasSeleccionadas[prop.nombre_propiedad]) {
                tbody.appendChild(construirFila(index++, prop, false, false));
            }
        });

        // 2. Propiedades extra
        Object.keys(_extrasSeleccionadas).forEach(function (id) {
            tbody.appendChild(construirFila(index++, _extrasSeleccionadas[id], true, false));
        });

        // 3. Excluidas al final en gris
        _propiedadesBase.forEach(function (prop) {
            if (_excluidasSeleccionadas[prop.nombre_propiedad]) {
                tbody.appendChild(construirFila(index++, prop, false, true));
            }
        });

        recalcularTotalForms();
        actualizarHiddens();

        // BUG FIX: Restaurar valores que el usuario ya había escrito
        restaurarValores(valoresGuardados);
    }

    // -------------------------------------------------------
    // SECCIÓN EXTRAS
    // -------------------------------------------------------


    // -------------------------------------------------------
    // LOINC PICKER PARA PROPIEDADES EXTRA
    // Popup flotante idéntico al de plantilla_propiedades_picker.js
    // -------------------------------------------------------
    var _extraLoincPopup   = null;
    var _extraLoincDebounce = null;
    var _extraLoincPropId  = null;  // propId actual que se está editando

    function getLoincAdminBase() {
        // Detectar la URL base del admin para el endpoint LOINC de Analisis
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
            '🌐 LOINC.org</a>',
            '</div>',
            '<div id="pp-extra-loinc-results" style="max-height:240px;overflow-y:auto;',
            'border-top:1px solid #eee;padding-top:4px;">',
            '<div style="color:#999;font-size:12px;padding:6px;">Escribe para buscar…</div>',
            '</div>',
        ].join('');
        document.body.appendChild(popup);

        var inp = popup.querySelector('#pp-extra-loinc-inp');
        inp.addEventListener('input', function () {
            var q = inp.value.trim();
            var extBtn = document.getElementById('pp-extra-loinc-extbtn');
            if (extBtn) {
                extBtn.href = q
                    ? 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(q)
                    : 'https://loinc.org/search/';
            }
            clearTimeout(_extraLoincDebounce);
            var resultsEl = document.getElementById('pp-extra-loinc-results');
            if (q.length < 2) {
                if (resultsEl) resultsEl.innerHTML =
                    '<div style="color:#999;font-size:12px;padding:6px;">Escribe al menos 2 caracteres…</div>';
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
        var popup = crearExtraLoincPopup();
        _extraLoincPropId = propId;
        var rect   = btnEl.getBoundingClientRect();
        var popupW = 380;
        var popupH = 300;
        popup.style.display = 'block';
        var top = (window.innerHeight - rect.bottom >= popupH || rect.top < popupH)
            ? rect.bottom + 4
            : rect.top - popupH - 4;
        var left = Math.min(rect.left, window.innerWidth - popupW - 8);
        popup.style.top  = top  + 'px';
        popup.style.left = left + 'px';

        var inp = document.getElementById('pp-extra-loinc-inp');
        if (inp) {
            inp.value = nombreProp || '';
            inp.focus(); inp.select();
            var extBtn = document.getElementById('pp-extra-loinc-extbtn');
            if (extBtn && nombreProp) {
                extBtn.href = 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(nombreProp);
            }
        }
        var resultsEl = document.getElementById('pp-extra-loinc-results');
        if (resultsEl) {
            if (nombreProp && nombreProp.length >= 2) {
                resultsEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Buscando…</div>';
                buscarLoincExtra(nombreProp, propId);
            } else {
                resultsEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Escribe para buscar…</div>';
            }
        }
    }

    function cerrarExtraLoincPopup() {
        if (_extraLoincPopup) _extraLoincPopup.style.display = 'none';
        _extraLoincPropId = null;
    }

    // Cerrar al clic fuera o scroll de página
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
        var resultsEl = document.getElementById('pp-extra-loinc-results');
        if (!resultsEl) return;
        var muestra = getMuestraAnalisis();
        var metodo  = getMetodoAnalisis();
        var url = getLoincAdminBase() + 'loinc-buscar/?q=' + encodeURIComponent(q);
        if (muestra) url += '&muestra=' + encodeURIComponent(muestra);
        if (metodo)  url += '&metodo='  + encodeURIComponent(metodo);

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (_extraLoincPropId !== propId) return; // stale
                resultsEl = document.getElementById('pp-extra-loinc-results');
                if (!resultsEl) return;
                if (!data.results || data.results.length === 0) {
                    resultsEl.innerHTML = '<div style="color:#999;font-size:12px;padding:6px;">Sin resultados.</div>';
                    return;
                }
                resultsEl.innerHTML = '';
                if (data.filtrado && (data.muestra || data.metodo)) {
                    var badge = document.createElement('div');
                    badge.style.cssText = 'font-size:11px;color:#1a6fa8;padding:3px 6px;margin-bottom:4px;background:#e8f0fe;border-radius:3px;';
                    badge.textContent = '🧪 Filtrado por: ' + [data.muestra, data.metodo].filter(Boolean).join(' · ');
                    resultsEl.appendChild(badge);
                }
                data.results.forEach(function (lc) {
                    var row = document.createElement('div');
                    row.style.cssText = 'padding:6px 8px;cursor:pointer;border-bottom:1px solid #f0f0f0;font-size:12px;';
                    row.onmouseover = function () { row.style.background = '#e8f0fe'; };
                    row.onmouseout  = function () { row.style.background = ''; };
                    var meta = [lc.system, lc.property, lc.scale_typ, lc.method_typ ? '⚙ '+lc.method_typ : ''].filter(Boolean).join(' · ');
                    row.innerHTML =
                        '<span style="font-weight:600;color:#1a6fa8;">' + escHtml(lc.loinc_num) + '</span>' +
                        ' <span>' + escHtml(lc.shortname || lc.component || '') + '</span>' +
                        (meta ? '<br><span style="color:#888;font-size:11px;">' + escHtml(meta) + '</span>' : '');
                    row.addEventListener('click', function (e) {
                        e.stopPropagation();
                        _extraLoincMap[propId] = {
                            loincId:   String(lc.id),
                            loincNum:  lc.loinc_num,
                            loincDesc: lc.shortname || lc.component || '',
                        };
                        cerrarExtraLoincPopup();
                        actualizarHiddens();
                        // Actualizar display del botón en la lista de extras
                        actualizarDisplayLoincExtra(propId);
                    });
                    resultsEl.appendChild(row);
                });
            })
            .catch(function () {
                var el = document.getElementById('pp-extra-loinc-results');
                if (el) el.innerHTML = '<div style="color:#c0392b;font-size:12px;padding:6px;">Error de conexión.</div>';
            });
    }

    function escHtml(s) {
        return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function actualizarDisplayLoincExtra(propId) {
        var displayEl = document.getElementById('_loinc_display_extra_' + propId);
        if (!displayEl) return;
        var loinc = _extraLoincMap[propId];
        // Limpiar contenido anterior
        displayEl.innerHTML = '';
        if (loinc && loinc.loincNum) {
            var numSpan = document.createElement('span');
            numSpan.style.cssText = 'color:#1a6fa8;font-weight:600;font-size:12px;';
            numSpan.textContent   = loinc.loincNum;
            displayEl.appendChild(numSpan);
            if (loinc.loincDesc) {
                var descSpan = document.createElement('span');
                descSpan.style.cssText = 'color:#555;font-size:11px;margin-left:4px;';
                descSpan.textContent   = '— ' + loinc.loincDesc;
                displayEl.appendChild(descSpan);
            }
            var clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.style.cssText = 'border:none;background:none;color:#c0392b;cursor:pointer;font-size:11px;padding:0 4px;';
            clearBtn.textContent = '✕';
            clearBtn.title = 'Quitar LOINC';
            clearBtn.addEventListener('click', function () {
                delete _extraLoincMap[propId];
                actualizarHiddens();
                actualizarDisplayLoincExtra(propId);
            });
            displayEl.appendChild(clearBtn);
        } else {
            var emptySpan = document.createElement('span');
            emptySpan.style.cssText = 'color:#999;font-size:11px;';
            emptySpan.textContent = 'Sin código';
            displayEl.appendChild(emptySpan);
        }
    }

    // Exponer mapa al DOM para el onclick del botón de limpiar
    window.__extraLoincMap    = _extraLoincMap;
    window.__syncExtrasHidden = function () { actualizarHiddens(); };

    function crearSeccionExtras() {
        if (document.getElementById('_seccion_extras')) return;

        var inlineGroup = document.getElementById(PREFIX + '-group');
        if (!inlineGroup) return;

        var wrapper = document.createElement('div');
        wrapper.id = '_seccion_extras';
        wrapper.style.cssText = 'margin:12px 0;border:1px solid #c8e6c9;border-radius:6px;overflow:hidden;';
        wrapper.innerHTML = [
            '<div style="background:#f1f8e9;padding:10px 14px;display:flex;align-items:center;gap:8px;">',
            '<input type="checkbox" id="_chk_extras" style="cursor:pointer;width:16px;height:16px;">',
            '<label for="_chk_extras" style="cursor:pointer;font-weight:600;color:#2e7d32;margin:0;font-size:13px;">',
            '➕ Agregar propiedades extra a este análisis</label>',
            '</div>',
            '<div id="_extras_body" style="display:none;padding:12px;">',
            '<p style="color:#666;font-size:12px;margin:0 0 8px;">Propiedades que no pertenecen a la plantilla seleccionada.</p>',
            '<div id="_extras_lista" style="max-height:220px;overflow-y:auto;"></div>',
            '</div>',
        ].join('');

        inlineGroup.parentNode.insertBefore(wrapper, inlineGroup.nextSibling);

        document.getElementById('_chk_extras').addEventListener('change', function () {
            document.getElementById('_extras_body').style.display = this.checked ? '' : 'none';
            if (!this.checked) {
                _extrasSeleccionadas = {};
                document.querySelectorAll('._chk_prop_extra').forEach(function(c){ c.checked = false; });
                renderizarTablaCompleta();
            }
        });
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
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 2px;border-bottom:1px solid #f0f0f0;';

            var chk = document.createElement('input');
            chk.type = 'checkbox'; chk.className = '_chk_prop_extra'; chk.value = prop.id;
            if (_extrasSeleccionadas[prop.id]) chk.checked = true;

            var lbl = document.createElement('label');
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;flex:1;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            var loincWrap = document.createElement('div');
            loincWrap.style.cssText = 'display:none;align-items:center;gap:4px;margin-left:4px;';
            loincWrap.id = '_loinc_wrap_extra_' + prop.id;

            var loincDisplay = document.createElement('span');
            loincDisplay.id = '_loinc_display_extra_' + prop.id;
            loincDisplay.innerHTML = '<span style="color:#999;font-size:11px;">Sin código</span>';

            var loincBtn = document.createElement('button');
            loincBtn.type = 'button';
            loincBtn.className = 'pp-extra-loinc-btn';
            loincBtn.title = 'Asignar código LOINC';
            loincBtn.style.cssText = 'border:1px solid #1a6fa8;background:#e8f0fe;color:#1a6fa8;' +
                'border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;white-space:nowrap;';
            loincBtn.textContent = '🔍 LOINC';
            loincBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                mostrarExtraLoincPopup(String(prop.id), loincBtn, prop.nombre_propiedad);
            });

            loincWrap.appendChild(loincDisplay);
            loincWrap.appendChild(loincBtn);

            chk.addEventListener('change', function () {
                if (this.checked) {
                    _extrasSeleccionadas[prop.id] = prop;
                    loincWrap.style.display = 'flex';
                } else {
                    delete _extrasSeleccionadas[prop.id];
                    delete _extraLoincMap[prop.id];
                    loincWrap.style.display = 'none';
                }
                renderizarTablaCompleta();
                actualizarHiddens();
            });

            row.appendChild(chk);
            row.appendChild(lbl);
            row.appendChild(loincWrap);
            if (_extrasSeleccionadas[prop.id]) loincWrap.style.display = 'flex';
            lista.appendChild(row);
        });
    }

    // -------------------------------------------------------
    // SECCIÓN EXCLUIR
    // -------------------------------------------------------

    function crearSeccionExcluir() {
        if (document.getElementById('_seccion_excluir')) return;

        var inlineGroup = document.getElementById(PREFIX + '-group');
        if (!inlineGroup) return;

        var wrapper = document.createElement('div');
        wrapper.id = '_seccion_excluir';
        wrapper.style.cssText = 'margin:12px 0;border:1px solid #ffccbc;border-radius:6px;overflow:hidden;';
        wrapper.innerHTML = [
            '<div style="background:#fff3e0;padding:10px 14px;display:flex;align-items:center;gap:8px;">',
            '<input type="checkbox" id="_chk_excluir" style="cursor:pointer;width:16px;height:16px;">',
            '<label for="_chk_excluir" style="cursor:pointer;font-weight:600;color:#bf360c;margin:0;font-size:13px;">',
            '➖ Excluir propiedades de la plantilla en este análisis</label>',
            '</div>',
            '<div id="_excluir_body" style="display:none;padding:12px;">',
            '<p style="color:#666;font-size:12px;margin:0 0 8px;">Las marcadas no se incluirán en este análisis y aparecerán en gris.</p>',
            '<div id="_excluir_lista" style="max-height:220px;overflow-y:auto;"></div>',
            '</div>',
        ].join('');

        // Insertar ANTES de la sección extras
        var seccionExtras = document.getElementById('_seccion_extras');
        if (seccionExtras) {
            inlineGroup.parentNode.insertBefore(wrapper, seccionExtras);
        } else {
            inlineGroup.parentNode.insertBefore(wrapper, inlineGroup.nextSibling);
        }

        document.getElementById('_chk_excluir').addEventListener('change', function () {
            document.getElementById('_excluir_body').style.display = this.checked ? '' : 'none';
            if (!this.checked) {
                _excluidasSeleccionadas = {};
                document.querySelectorAll('._chk_prop_excluir').forEach(function(c){ c.checked = false; });
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
            chk.type = 'checkbox'; chk.className = '_chk_prop_excluir'; chk.value = prop.nombre_propiedad;
            if (_excluidasSeleccionadas[prop.nombre_propiedad]) chk.checked = true;

            chk.addEventListener('change', function () {
                if (this.checked) { _excluidasSeleccionadas[prop.nombre_propiedad] = true; }
                else              { delete _excluidasSeleccionadas[prop.nombre_propiedad]; }
                renderizarTablaCompleta();
            });

            var lbl = document.createElement('label');
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;flex:1;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            // Display LOINC actual y botón de asignar
            var loincWrap = document.createElement('div');
            loincWrap.style.cssText = 'display:none;align-items:center;gap:4px;margin-left:4px;';
            loincWrap.id = '_loinc_wrap_extra_' + prop.id;

            var loincDisplay = document.createElement('span');
            loincDisplay.id = '_loinc_display_extra_' + prop.id;
            loincDisplay.innerHTML = '<span style="color:#999;font-size:11px;">Sin código</span>';

            var loincBtn = document.createElement('button');
            loincBtn.type = 'button';
            loincBtn.className = 'pp-extra-loinc-btn';
            loincBtn.title = 'Asignar código LOINC';
            loincBtn.style.cssText = 'border:1px solid #1a6fa8;background:#e8f0fe;color:#1a6fa8;' +
                'border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;white-space:nowrap;';
            loincBtn.textContent = '🔍 LOINC';
            loincBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                mostrarExtraLoincPopup(String(prop.id), loincBtn, prop.nombre_propiedad);
            });

            loincWrap.appendChild(loincDisplay);
            loincWrap.appendChild(loincBtn);

            chk.addEventListener('change', function () {
                if (this.checked) {
                    _extrasSeleccionadas[prop.id] = prop;
                    loincWrap.style.display = 'flex';
                } else {
                    delete _extrasSeleccionadas[prop.id];
                    delete _extraLoincMap[prop.id];
                    loincWrap.style.display = 'none';
                }
                renderizarTablaCompleta();
                actualizarHiddens();
            });

            row.appendChild(chk);
            row.appendChild(lbl);
            row.appendChild(loincWrap);
            if (_extrasSeleccionadas[prop.id]) loincWrap.style.display = 'flex';
            lista.appendChild(row);
        });
    }

    // -------------------------------------------------------
    // HIDDENS para el submit
    // -------------------------------------------------------

    function getForm() {
        return document.querySelector('#content-main form') ||
               document.querySelector('form.change-form') ||
               document.querySelector('form');
    }

    function setHidden(id, name, value) {
        var el = document.getElementById(id);
        if (!el) {
            el = document.createElement('input');
            el.type = 'hidden'; el.id = id; el.name = name;
            var f = getForm();
            if (f) f.appendChild(el);
        }
        el.value = value;
    }

    function actualizarHiddens() {
        var extraIds = Object.keys(_extrasSeleccionadas);
        setHidden('_hidden_extras',      '_propiedades_extra_ids',         extraIds.join(','));
        setHidden('_hidden_excluidas',   '_propiedades_excluidas_nombres', Object.keys(_excluidasSeleccionadas).join(','));
        // LOINCs de propiedades extra — parallel array al de ids
        var loincIds = extraIds.map(function (id) {
            return (_extraLoincMap[id] && _extraLoincMap[id].loincId) ? _extraLoincMap[id].loincId : '';
        });
        setHidden('_hidden_extras_loinc', '_propiedades_extra_loinc_ids', loincIds.join(','));
    }

    // -------------------------------------------------------
    // CONSULTAS AL SERVIDOR
    // -------------------------------------------------------

    function getSelectValue(id) {
        var el = document.getElementById(id);
        return el ? el.value : '';
    }

    function consultarPlantilla(plantillaId, callback) {
        if (!plantillaId) {
            limpiarFilasSinPk(); recalcularTotalForms();
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
            fetch(urlTipo,  { headers:{'X-Requested-With':'XMLHttpRequest'} }).then(function(r){ return r.json(); }),
            fetch(urlProps, { headers:{'X-Requested-With':'XMLHttpRequest'} }).then(function(r){ return r.json(); }),
            fetch(urlDisp,  { headers:{'X-Requested-With':'XMLHttpRequest'} }).then(function(r){ return r.json(); }),
        ])
        .then(function(res) {
            callback(res[0].tipo_formato || '', res[1].propiedades || [], res[2].propiedades || []);
        })
        .catch(function() { callback('', [], []); });
    }

    // -------------------------------------------------------
    // LÓGICA CENTRAL
    // -------------------------------------------------------

    function onSeleccionCambio() {
        if (debeBloquearPrecarga()) return;

        _extrasSeleccionadas    = {};
        _excluidasSeleccionadas = {};

        var plantillaId = getSelectValue('id_plantilla');

        consultarPlantilla(plantillaId, function (tipoFormato, propiedadesBase, propiedadesDisp) {
            mostrarOcultarImagenes(tipoFormato);
            _propiedadesBase = propiedadesBase;

            // Resetear controles
            ['_chk_extras','_chk_excluir'].forEach(function(id){
                var el = document.getElementById(id); if (el) el.checked = false;
            });
            ['_extras_body','_excluir_body'].forEach(function(id){
                var el = document.getElementById(id); if (el) el.style.display = 'none';
            });

            if (propiedadesBase.length > 0) {
                crearSeccionExcluir();
                crearSeccionExtras();
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
            headers: {'X-Requested-With':'XMLHttpRequest'}
        }).then(function(r){ return r.json(); })
          .then(function(d){ mostrarOcultarImagenes(d.tipo_formato || ''); })
          .catch(function(){});
    }

    // -------------------------------------------------------
    // BIND SELECT2
    // -------------------------------------------------------

    function bindSelect2(selectId, handler) {
        var intentos = 0;
        function intentar() {
            if (window.django && window.django.jQuery) {
                var $sel = window.django.jQuery('#' + selectId);
                if ($sel.length) { $sel.on('select2:select select2:clear', handler); return; }
            }
            if (intentos++ < 50) setTimeout(intentar, 100);
        }
        intentar();
    }

    // -------------------------------------------------------
    // INIT
    // -------------------------------------------------------

    function init() {
        // Ocultar imágenes al inicio
        var seccion = getSectionImagen();
        if (seccion) {
            var fieldset = seccion.closest('fieldset') || seccion;
            fieldset.style.display = 'none';
        }

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
            } else {
                onSeleccionCambio();
            }
        }, 400);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();