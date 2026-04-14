/**
 * analisis_imagenes_toggle.js
 * v17 — TRES CORRECCIONES:
 *   1. FIX valores de referencia en props extra: consultarPlantilla ahora
 *      incluye paciente_id en urlDisp para que propiedades_disponibles
 *      devuelva valor_min/valor_max reales (antes siempre null).
 *   2. FIX desalineación de tabla: construirFila restaura la columna
 *      tdLoinc (field-col_loinc_code) que v16 eliminó. tdNombre
 *      (field-nombre_propiedad) se omite porque ese campo fue eliminado
 *      del inline de admin por ser redundante con tdProp.
 *   3. NEW botón "🌐 Buscar en LOINC.org" inyectado en el encabezado del
 *      inline de resultados para acceder rápidamente al buscador oficial.
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

        if (tipoFormato === 'IMAGENES_RESULTADOS') {
            // Mostrar: restaurar estilos normales
            fieldset.style.visibility = '';
            fieldset.style.position   = '';
            fieldset.style.height     = '';
            fieldset.style.overflow   = '';
            fieldset.style.padding    = '';
            fieldset.style.margin     = '';
            fieldset.style.border     = '';
            // Habilitar los inputs de archivo para que el browser los envíe
            fieldset.querySelectorAll('input[type="file"]').forEach(function (inp) {
                inp.disabled = false;
            });
        } else {
            // Ocultar VISUALMENTE pero sin display:none — así los <input type="file">
            // siguen en el DOM activo y el browser los incluye en el POST.
            // Si el usuario no seleccionó archivo, el campo queda vacío (sin cambio),
            // que es el comportamiento correcto para no borrar imágenes existentes.
            fieldset.style.visibility = 'hidden';
            fieldset.style.position   = 'absolute';
            fieldset.style.height     = '0';
            fieldset.style.overflow   = 'hidden';
            fieldset.style.padding    = '0';
            fieldset.style.margin     = '0';
            fieldset.style.border     = 'none';
            // NO deshabilitar — queremos que los inputs existan pero vacíos
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

    // -------------------------------------------------------
    // CONSTRUIR FILA
    // -------------------------------------------------------

    function construirFila(index, prop, esExtra, esExcluida) {
        var nombre   = prop.nombre_propiedad;
        var tipo     = (prop.tipo || 'CUANTITATIVO').trim().toUpperCase();
        var unidad   = prop.unidad || '';
        var opciones = prop.opciones_cualitativas || '';
        var valorMin = prop.valor_min;
        var valorMax = prop.valor_max;
        var pref     = PREFIX + '-' + index;

        // Resolver LOINC: base → prop.loinc_num; extra → _extraLoincMap
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

        if (esExcluida) {
            tr.style.cssText = 'opacity:0.45;background:#f5f5f5;';
        }

        // ── Hidden: id + analisis ───────────────────────────────────
        var tdId = document.createElement('td');
        tdId.className     = 'original';
        tdId.style.display = 'none';

        var inputId = document.createElement('input');
        inputId.type  = 'hidden';
        inputId.name  = pref + '-id';
        inputId.id    = 'id_' + pref + '-id';
        inputId.value = '';
        tdId.appendChild(inputId);

        var inputAnalisis = document.createElement('input');
        inputAnalisis.type  = 'hidden';
        inputAnalisis.name  = pref + '-analisis';
        inputAnalisis.id    = 'id_' + pref + '-analisis';
        inputAnalisis.value = '';
        tdId.appendChild(inputAnalisis);

        tr.appendChild(tdId);

        // ── Columna: propiedad ──────────────────────────────────────
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

        // Mostrar código LOINC bajo el nombre de la propiedad
        tr.appendChild(tdProp);

        // ── Columna: col_loinc_code — readonly div (col 2) ─────────────────
        // nombre_propiedad fue eliminado del inline (es redundante con tdProp),
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
            // Fix C: ancho moderado en lugar de 100%
            sel.style.cssText  = 'width:120px;max-width:100%;font-size:13px;';
            if (esExcluida) sel.disabled = true;

            var optBlank = document.createElement('option');
            optBlank.value       = '';
            optBlank.textContent = '---------';
            sel.appendChild(optBlank);

            opsList.forEach(function (op) {
                var opt = document.createElement('option');
                opt.value = op; opt.textContent = op;
                sel.appendChild(opt);
            });
            tdValor.appendChild(sel);
        } else {
            var inputValor = document.createElement('input');
            inputValor.type         = 'text';
            inputValor.name         = pref + '-valor';
            inputValor.id           = 'id_' + pref + '-valor';
            inputValor.value        = '';
            // Fix C: ancho acotado
            inputValor.style.cssText = 'width:80px;max-width:100%;font-size:13px;';
            if (esExcluida) {
                inputValor.disabled      = true;
                inputValor.style.cssText += 'pointer-events:none;';
            }
            tdValor.appendChild(inputValor);
        }
        tr.appendChild(tdValor);

        // ── Columna: unidad ─────────────────────────────────────────────────
        // Fix B: en lugar de un <input readonly> que se ve como caja de texto,
        // usamos un <span> de solo lectura + un <input hidden> para el POST.
        // Así la unidad se muestra como texto plano sin borde ni fondo.
        var tdUnidad = document.createElement('td');
        tdUnidad.className           = 'field-unidad';
        tdUnidad.style.verticalAlign = 'middle';

        var unidadVal = (tipo === 'CUALITATIVO') ? 'N/A' : (unidad || '');

        // Input oculto — lo necesita el POST de Django
        var inputUnidadHidden = document.createElement('input');
        inputUnidadHidden.type  = 'hidden';
        inputUnidadHidden.name  = pref + '-unidad';
        inputUnidadHidden.id    = 'id_' + pref + '-unidad';
        inputUnidadHidden.value = unidadVal;
        tdUnidad.appendChild(inputUnidadHidden);

        // Span visible — se ve como texto normal, sin caja
        var spanUnidad = document.createElement('span');
        spanUnidad.textContent  = unidadVal;
        spanUnidad.style.cssText =
            'font-size:13px;color:' +
            (tipo === 'CUALITATIVO' ? '#999' : 'inherit') + ';' +
            (tipo === 'CUALITATIVO' ? 'font-style:italic;' : '');
        if (tipo === 'CUALITATIVO') {
            spanUnidad.title = 'No aplica para propiedades cualitativas';
        }
        tdUnidad.appendChild(spanUnidad);
        tr.appendChild(tdUnidad);

        // ── Columna: referencia / opciones ──────────────────────────
        var tdRef = document.createElement('td');
        tdRef.className = 'field-col_intervalo_referencia';
        tdRef.style.cssText = 'vertical-align:middle;font-size:12px;color:#555;';

        if (tipo === 'CUALITATIVO' && opciones) {
            tdRef.textContent = opciones.split(',').map(function (o) { return o.trim(); }).join(' / ');
        } else if (
            tipo === 'CUANTITATIVO' &&
            valorMin !== null && valorMin !== undefined &&
            valorMax !== null && valorMax !== undefined
        ) {
            tdRef.textContent = valorMin + ' – ' + valorMax + (unidad ? ' ' + unidad : '');
        } else {
            tdRef.textContent = '-';
        }
        tr.appendChild(tdRef);

        // ── Columna: estado del valor ───────────────────────────────
        var tdEstado = document.createElement('td');
        tdEstado.className           = 'field-col_valor_coloreado';
        tdEstado.style.verticalAlign = 'middle';
        tdEstado.textContent         = '';
        tr.appendChild(tdEstado);

        // ── Columna: DELETE checkbox ────────────────────────────────
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

    // -------------------------------------------------------
    // PRESERVAR VALORES ESCRITOS POR EL USUARIO
    // Cuando se agrega/quita una propiedad extra, renderizarTablaCompleta()
    // reconstruye toda la tabla. Sin estas funciones los valores ya escritos
    // se pierden porque los inputs se reemplazan por nuevos vacíos.
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

    function renderizarTablaCompleta() {
        var tbody = getTbodyInline();
        if (!tbody || debeBloquearPrecarga()) return;

        // Guardar valores escritos ANTES de reconstruir la tabla
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

        // Restaurar los valores que el usuario ya había escrito
        restaurarValores(valoresGuardados);
    }

    // -------------------------------------------------------
    // SECCIÓN EXTRAS
    // FIX v16: usar insertAdjacentElement('afterend') sobre
    // #resultados-group en lugar de parentNode.insertBefore()
    // -------------------------------------------------------

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
            'Propiedades que no pertenecen a la plantilla seleccionada.</p>',
            '<div id="_extras_lista" style="max-height:220px;overflow-y:auto;"></div>',
            '</div>',
        ].join('');

        // FIX: insertAdjacentElement es más confiable que parentNode.insertBefore
        // porque opera directamente sobre el nodo de referencia, sin depender
        // de nextSibling (que puede ser un nodo de texto o null en el admin).
        inlineGroup.insertAdjacentElement('afterend', wrapper);

        document.getElementById('_chk_extras').addEventListener('change', function () {
            document.getElementById('_extras_body').style.display = this.checked ? '' : 'none';
            if (!this.checked) {
                _extrasSeleccionadas = {};
                document.querySelectorAll('._chk_prop_extra').forEach(function (c) { c.checked = false; });
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
            row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 2px;border-bottom:1px solid #f0f0f0;flex-wrap:wrap;';

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

            // Zona LOINC: display + botón picker
            var loincWrap = document.createElement('div');
            loincWrap.id            = '_loinc_wrap_extra_' + prop.id;
            loincWrap.style.cssText = 'display:none;align-items:center;gap:4px;margin-left:4px;';

            var loincDisplay = document.createElement('span');
            loincDisplay.id = '_loinc_display_extra_' + prop.id;
            // Inicializar con el estado actual (por si se re-renderiza la lista)
            var loincEntry = _extraLoincMap[String(prop.id)];
            if (loincEntry && loincEntry.loincNum) {
                loincDisplay.innerHTML =
                    '<span style="color:#1a6fa8;font-weight:600;font-size:12px;font-family:monospace;">' +
                    escHtml(loincEntry.loincNum) + '</span>' +
                    (loincEntry.loincDesc
                        ? '<span style="color:#555;font-size:11px;margin-left:4px;">\u2014 ' + escHtml(loincEntry.loincDesc) + '</span>'
                        : '');
            } else {
                loincDisplay.innerHTML = '<span style="color:#999;font-size:11px;">Sin c\u00F3digo</span>';
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
                    delete _extraLoincMap[String(prop.id)];
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
    // FIX v16: insertar con insertAdjacentElement('afterend')
    // sobre #resultados-group, y ANTES de _seccion_extras si
    // ya existe, usando insertAdjacentElement('beforebegin').
    // -------------------------------------------------------

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

        // Si ya existe _seccion_extras, insertar ANTES de ella.
        // Si no existe todavía, insertar justo después de #resultados-group.
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

            // Mostrar LOINC de la plantilla como etiqueta de solo lectura (informativa)
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
        setHidden('_hidden_extras',      '_propiedades_extra_ids',         extraIds.join(','));
        setHidden('_hidden_excluidas',   '_propiedades_excluidas_nombres', Object.keys(_excluidasSeleccionadas).join(','));
        // LOINCs en el mismo orden que los ids de extras (array paralelo)
        var loincIds = extraIds.map(function (id) {
            return (_extraLoincMap[id] && _extraLoincMap[id].loincId)
                ? _extraLoincMap[id].loincId
                : '';
        });
        setHidden('_hidden_extras_loinc', '_propiedades_extra_loinc_ids', loincIds.join(','));
    }

    // -------------------------------------------------------
    // LOINC PICKER PARA PROPIEDADES EXTRA
    // Popup flotante con búsqueda contextual (muestra + método).
    // -------------------------------------------------------

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
                if (_extraLoincPropId !== propId) return; // respuesta stale
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
                        renderizarTablaCompleta(); // refresca la fila de la tabla inline
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
            empty.textContent   = 'Sin c\u00F3digo';
            displayEl.appendChild(empty);
        }
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

            // Resetear controles si ya existían de una selección anterior
            ['_chk_extras', '_chk_excluir'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.checked = false;
            });
            ['_extras_body', '_excluir_body'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });

            if (propiedadesBase.length > 0) {
                // Orden de llamada: primero Extras (se inserta afterend de inlineGroup),
                // luego Excluir (se inserta beforebegin de _seccion_extras).
                // Resultado en DOM: [inlineGroup][_seccion_excluir][_seccion_extras]
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
    // FIX v16: el bindSelect2 original fallaba porque Select2
    // ya estaba inicializado antes de que el script intentara
    // engancharse. Ahora usamos tres capas de detección:
    //   1. select2:select / select2:clear  (Select2 events)
    //   2. change nativo en el <select> subyacente
    //   3. MutationObserver sobre el span de Select2 como
    //      último recurso si los eventos no disparan
    // -------------------------------------------------------

    function bindSelect2(selectId, handler) {
        var intentos = 0;

        function enganchar() {
            // Capa 1: eventos Select2 vía django.jQuery
            if (window.django && window.django.jQuery) {
                var $sel = window.django.jQuery('#' + selectId);
                if ($sel.length) {
                    $sel.on('select2:select select2:clear change', handler);
                }
            }
            // Capa 2: evento change nativo en el <select> real
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

    // -------------------------------------------------------
    // INIT
    // -------------------------------------------------------

    function init() {
        // Ocultar sección imágenes al inicio usando visibility (NO display:none)
        // para que los <input type="file"> sigan en el DOM y se envíen al POST.
        mostrarOcultarImagenes('');

        // ── BOTÓN LOINC.org ───────────────────────────────────────────────
        // Inyectar enlace directo a LOINC.org en el encabezado del inline
        // de resultados. Útil para buscar un código LOINC específico sin
        // tener que salir de la página.
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

        bindSelect2('id_plantilla', function () {
            if (!debeBloquearPrecarga()) onSeleccionCambio();
        });
        bindSelect2('id_paciente', function () {
            if (!debeBloquearPrecarga()) onSeleccionCambio();
        });

        // Carga inicial: esperar a que Select2 haya renderizado
        // su valor antes de leerlo (800ms es más seguro que 400ms)
        setTimeout(function () {
            var plantillaId = getSelectValue('id_plantilla');
            if (!plantillaId) return;
            if (debeBloquearPrecarga()) {
                onCargaInicialEdicion(plantillaId);
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