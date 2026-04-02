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
        if (!thead) return ['propiedad', 'valor', 'unidad', 'col_intervalo_referencia', 'col_valor_coloreado', 'DELETE'];
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

        var tr = document.createElement('tr');
        tr.id        = PREFIX + '-' + index;
        tr.className = 'form-row dynamic-' + PREFIX;

        if (esExcluida) {
            tr.style.cssText = 'opacity:0.45;background:#f5f5f5;';
        }

        // ── Hidden: id (pk vacío = nueva fila) ─────────────────────
        var tdId = document.createElement('td');
        tdId.className = 'original';
        tdId.style.display = 'none';

        var inputId = document.createElement('input');
        inputId.type  = 'hidden';
        inputId.name  = pref + '-id';
        inputId.id    = 'id_' + pref + '-id';
        inputId.value = '';
        tdId.appendChild(inputId);

        // ── Hidden: analisis ────────────────────────────────────────
        var inputAnalisis = document.createElement('input');
        inputAnalisis.type  = 'hidden';
        inputAnalisis.name  = pref + '-analisis';
        inputAnalisis.id    = 'id_' + pref + '-analisis';
        inputAnalisis.value = '';
        tdId.appendChild(inputAnalisis);

        tr.appendChild(tdId);

        // ── Columna: propiedad (nombre como texto readonly) ─────────
        var tdProp = document.createElement('td');
        tdProp.className = 'field-propiedad';
        tdProp.style.verticalAlign = 'middle';

        // FIX: Hidden con el ID numérico real de la propiedad (FK).
        // Django necesita este campo para asignar propiedad_id en la BD.
        // Sin esto se produce: NOT NULL constraint failed: propiedad_id
        var inputPropFk = document.createElement('input');
        inputPropFk.type  = 'hidden';
        inputPropFk.name  = pref + '-propiedad';
        inputPropFk.id    = 'id_' + pref + '-propiedad';
        inputPropFk.value = prop.id || '';   // ← id numérico de la BD
        tdProp.appendChild(inputPropFk);

        // Hidden adicional con nombre_propiedad (referencia legible para save_model)
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
            badge.textContent = ' ➕ Extra';
            badge.style.cssText = 'font-size:10px;color:#fff;background:#27ae60;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            tdProp.appendChild(badge);
        }
        if (esExcluida) {
            var badgeEx = document.createElement('span');
            badgeEx.textContent = ' ➖ Excluida';
            badgeEx.style.cssText = 'font-size:10px;color:#fff;background:#e74c3c;' +
                'border-radius:3px;padding:1px 5px;margin-left:5px;';
            tdProp.appendChild(badgeEx);
        }
        tr.appendChild(tdProp);

        // ── Columna: valor ──────────────────────────────────────────
        var tdValor = document.createElement('td');
        tdValor.className = 'field-valor';
        tdValor.style.verticalAlign = 'middle';

        if (tipo === 'CUALITATIVO' && opciones) {
            var opsList = opciones.split(',').map(function(o){ return o.trim(); }).filter(Boolean);
            var sel = document.createElement('select');
            sel.name = pref + '-valor';
            sel.id   = 'id_' + pref + '-valor';
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
                inputValor.disabled = true;
                inputValor.style.cssText += 'pointer-events:none;';
            }
            tdValor.appendChild(inputValor);
        }
        tr.appendChild(tdValor);

        // ── Columna: unidad ─────────────────────────────────────────
        var tdUnidad = document.createElement('td');
        tdUnidad.className = 'field-unidad';
        tdUnidad.style.verticalAlign = 'middle';

        var inputUnidad = document.createElement('input');
        inputUnidad.type = 'text';
        inputUnidad.name = pref + '-unidad';
        inputUnidad.id   = 'id_' + pref + '-unidad';

        if (tipo === 'CUALITATIVO') {
            inputUnidad.value    = 'N/A';
            inputUnidad.disabled = true;
            inputUnidad.setAttribute('title', 'No aplica para propiedades cualitativas');
            inputUnidad.style.cssText = ESTILO_UNIDAD_NA;
        } else {
            inputUnidad.value    = unidad;
            inputUnidad.readOnly = true;
            inputUnidad.style.cssText = ESTILO_READONLY;
        }
        tdUnidad.appendChild(inputUnidad);
        tr.appendChild(tdUnidad);

        // ── Columna: referencia / opciones ──────────────────────────
        var tdRef = document.createElement('td');
        tdRef.className = 'field-col_intervalo_referencia';
        tdRef.style.cssText = 'vertical-align:middle;font-size:12px;color:#555;';

        if (tipo === 'CUALITATIVO' && opciones) {
            tdRef.textContent = opciones.split(',').map(function(o){ return o.trim(); }).join(' / ');
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

        // ── Columna: estado del valor (vacío al crear) ──────────────
        var tdEstado = document.createElement('td');
        tdEstado.className = 'field-col_valor_coloreado';
        tdEstado.style.verticalAlign = 'middle';
        tdEstado.textContent = '';
        tr.appendChild(tdEstado);

        // ── Columna: DELETE checkbox ────────────────────────────────
        var tdDel = document.createElement('td');
        tdDel.className = 'delete';
        if (!esExcluida) {
            var chkDel = document.createElement('input');
            chkDel.type  = 'checkbox';
            chkDel.name  = pref + '-DELETE';
            chkDel.id    = 'id_' + pref + '-DELETE';
            tdDel.appendChild(chkDel);
        }
        tr.appendChild(tdDel);

        return tr;
    }

    // -------------------------------------------------------
    // RENDERIZAR TABLA COMPLETA
    // -------------------------------------------------------

    function renderizarTablaCompleta() {
        var tbody = getTbodyInline();
        if (!tbody || debeBloquearPrecarga()) return;

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
    }

    // -------------------------------------------------------
    // SECCIÓN EXTRAS
    // -------------------------------------------------------

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

            chk.addEventListener('change', function () {
                if (this.checked) { _extrasSeleccionadas[prop.id] = prop; }
                else              { delete _extrasSeleccionadas[prop.id]; }
                renderizarTablaCompleta();
            });

            var lbl = document.createElement('label');
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            row.appendChild(chk);
            row.appendChild(lbl);
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
            lbl.style.cssText = 'cursor:pointer;font-size:13px;margin:0;';
            lbl.textContent   = prop.nombre_propiedad
                + (prop.unidad ? ' (' + prop.unidad + ')' : '')
                + (prop.tipo === 'CUALITATIVO' ? ' [Cualitativo]' : '');

            row.appendChild(chk);
            row.appendChild(lbl);
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
        setHidden('_hidden_extras',   '_propiedades_extra_ids',          Object.keys(_extrasSeleccionadas).join(','));
        setHidden('_hidden_excluidas','_propiedades_excluidas_nombres',  Object.keys(_excluidasSeleccionadas).join(','));
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
        var urlDisp  = '/admin_ext/propiedades_disponibles/?plantilla_id=' + plantillaId;

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
