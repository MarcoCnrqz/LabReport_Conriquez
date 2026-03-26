/**
 * analisis_imagenes_toggle.js
 * Ubicación: LabApp/static/admin/js/analisis_imagenes_toggle.js
 *
 * v12 — Unidad N/A para cualitativos:
 *   - Si la propiedad es CUALITATIVA:
 *       · El campo "valor" se renderiza como <select> con las opciones definidas.
 *       · El campo "unidad" se muestra deshabilitado con texto "N/A" en gris.
 *   - Si es CUANTITATIVA:
 *       · "valor" es input de texto normal.
 *       · "unidad" se muestra readonly con la unidad correspondiente.
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
        var tbody = getTbodyInline();
        var input = getInlineTotal();
        if (!tbody || !input) return;
        input.value = tbody.querySelectorAll('tr.dynamic-' + PREFIX).length;
    }

    // -------------------------------------------------------
    // Estilos compartidos
    // -------------------------------------------------------
    var ESTILO_READONLY =
        'background: transparent;' +
        'border: none;' +
        'outline: none;' +
        'box-shadow: none;' +
        'font-size: 13px;' +
        'color: inherit;' +
        'width: 100%;' +
        'padding: 0;' +
        'cursor: default;';

    var ESTILO_UNIDAD_DESHABILITADA =
        'background-color: #f0f0f0;' +
        'color: #999;' +
        'cursor: not-allowed;' +
        'border: 1px solid #ddd;' +
        'border-radius: 4px;' +
        'font-size: 13px;' +
        'width: 100%;' +
        'padding: 2px 6px;';

    // -------------------------------------------------------
    // CREAR FILA — clona el empty-form de Django
    // -------------------------------------------------------

    function crearFilaDesdeTemplate(index, prop) {
        var nombrePropiedad      = prop.nombre_propiedad;
        var tipo                 = prop.tipo || 'CUANTITATIVO';
        var unidad               = prop.unidad || '';
        var opcionesCualitativas = prop.opciones_cualitativas || '';
        var valorMin             = prop.valor_min;
        var valorMax             = prop.valor_max;

        var emptyRow = document.getElementById(PREFIX + '-empty');
        if (!emptyRow) {
            console.warn('[analisis_toggle] No se encontró #' + PREFIX + '-empty');
            return null;
        }

        var tr       = emptyRow.cloneNode(true);
        tr.id        = PREFIX + '-' + index;
        tr.className = 'form-row dynamic-' + PREFIX;
        tr.style.display = '';

        tr.innerHTML = tr.innerHTML.replace(/__prefix__/g, String(index));

        // ── nombre_propiedad: readonly visual ──────────────────────────
        var inputNombre = tr.querySelector(
            '[name="' + PREFIX + '-' + index + '-nombre_propiedad"]'
        );
        if (inputNombre) {
            inputNombre.value = nombrePropiedad;
            inputNombre.setAttribute('readonly', 'readonly');
            inputNombre.style.cssText = ESTILO_READONLY + 'font-weight: 600;';
            var tdNombre = inputNombre.closest('td');
            if (tdNombre) {
                var label = tdNombre.querySelector('label');
                if (label) label.style.display = 'none';
                tdNombre.style.verticalAlign = 'middle';
            }
        }

        // ── valor: input normal (cuantitativo) o select (cualitativo) ──
        var inputValor = tr.querySelector(
            '[name="' + PREFIX + '-' + index + '-valor"]'
        );
        var tipoNorm = (tipo || '').trim().toUpperCase();
        if (inputValor && tipoNorm === 'CUALITATIVO' && opcionesCualitativas) {
            var opciones = opcionesCualitativas
                .split(',')
                .map(function (o) { return o.trim(); })
                .filter(Boolean);

            if (opciones.length > 0) {
                var select = document.createElement('select');
                select.name = inputValor.name;
                select.id   = inputValor.id;
                select.style.cssText = 'width:100%;font-size:13px;';

                var optVacia = document.createElement('option');
                optVacia.value = '';
                optVacia.textContent = '---------';
                select.appendChild(optVacia);

                opciones.forEach(function (op) {
                    var opt = document.createElement('option');
                    opt.value = op;
                    opt.textContent = op;
                    select.appendChild(opt);
                });

                inputValor.parentNode.replaceChild(select, inputValor);
            }
        }

        // ── unidad ─────────────────────────────────────────────────────
        var inputUnidad = tr.querySelector(
            '[name="' + PREFIX + '-' + index + '-unidad"]'
        );
        if (inputUnidad) {
            var tdUnidad = inputUnidad.closest('td');

            if (tipoNorm === 'CUALITATIVO') {
                // Mostrar celda pero deshabilitar el input con "N/A"
                if (tdUnidad) {
                    tdUnidad.style.display = '';
                    var labelU = tdUnidad.querySelector('label');
                    if (labelU) labelU.style.display = 'none';
                    tdUnidad.style.verticalAlign = 'middle';
                }
                inputUnidad.removeAttribute('disabled');
                inputUnidad.removeAttribute('readonly');
                inputUnidad.value = 'N/A';
                inputUnidad.defaultValue = 'N/A';
                inputUnidad.setAttribute('disabled', 'disabled');
                inputUnidad.setAttribute('title', 'No aplica para propiedades cualitativas');
                inputUnidad.style.cssText = ESTILO_UNIDAD_DESHABILITADA;
                // Forzar repaint para que el valor sea visible pese a disabled
                requestAnimationFrame(function() { inputUnidad.value = 'N/A'; });

            } else {
                // CUANTITATIVO: mostrar unidad como readonly visual
                inputUnidad.value = unidad;
                inputUnidad.setAttribute('readonly', 'readonly');
                inputUnidad.style.cssText = ESTILO_READONLY;
                if (tdUnidad) {
                    var labelU2 = tdUnidad.querySelector('label');
                    if (labelU2) labelU2.style.display = 'none';
                    tdUnidad.style.verticalAlign = 'middle';
                }
            }
        }

        // ── intervalo de referencia / opciones ─────────────────────────
        var tdIntervalo = tr.querySelector('.field-intervalo_referencia');
        if (tdIntervalo) {
            if (tipoNorm === 'CUALITATIVO' && opcionesCualitativas) {
                tdIntervalo.textContent = opcionesCualitativas
                    .split(',')
                    .map(function (o) { return o.trim(); })
                    .join(' / ');
            } else if (
                tipoNorm === 'CUANTITATIVO' &&
                valorMin !== null && valorMin !== undefined &&
                valorMax !== null && valorMax !== undefined
            ) {
                tdIntervalo.textContent =
                    valorMin + ' \u2013 ' + valorMax + (unidad ? ' ' + unidad : '');
            }
        }

        return tr;
    }

    function precargarPropiedades(propiedades) {
        var tbody = getTbodyInline();
        if (!tbody) return;

        if (debeBloquearPrecarga()) return;

        limpiarFilasSinPk();

        var filasConPk  = tbody.querySelectorAll('tr.dynamic-' + PREFIX);
        var indexInicio = filasConPk.length;

        propiedades.forEach(function (prop, i) {
            var fila = crearFilaDesdeTemplate(indexInicio + i, prop);
            if (fila) tbody.appendChild(fila);
        });

        recalcularTotalForms();
    }

    // -------------------------------------------------------
    // CONSULTAS AL SERVIDOR
    // -------------------------------------------------------

    function getSelectValue(id) {
        var sel = document.getElementById(id);
        return sel ? sel.value : '';
    }

    function consultarPlantilla(plantillaId, callback) {
        if (!plantillaId) {
            limpiarFilasSinPk();
            recalcularTotalForms();
            callback('', []);
            return;
        }

        var pacienteId = getSelectValue('id_paciente');
        var urlTipo    = '/admin_ext/plantilla/' + plantillaId + '/tipo_formato/';
        var urlProps   = '/admin_ext/plantilla/' + plantillaId + '/propiedades/'
                         + (pacienteId ? '?paciente_id=' + pacienteId : '');

        Promise.all([
            fetch(urlTipo,  { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
            fetch(urlProps, { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.json(); }),
        ])
        .then(function (res) {
            callback(res[0].tipo_formato || '', res[1].propiedades || []);
        })
        .catch(function () { callback('', []); });
    }

    // -------------------------------------------------------
    // LÓGICA CENTRAL
    // -------------------------------------------------------

    function onSeleccionCambio() {
        if (debeBloquearPrecarga()) return;

        var plantillaId = getSelectValue('id_plantilla');
        consultarPlantilla(plantillaId, function (tipoFormato, propiedades) {
            mostrarOcultarImagenes(tipoFormato);
            if (propiedades.length > 0) {
                precargarPropiedades(propiedades);
            } else {
                limpiarFilasSinPk();
                recalcularTotalForms();
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
    // BIND SELECT2 con reintento cada 100 ms
    // -------------------------------------------------------

    function bindSelect2(selectId, handler) {
        var intentos = 0;
        function intentar() {
            if (window.django && window.django.jQuery) {
                var $sel = window.django.jQuery('#' + selectId);
                if ($sel.length) {
                    $sel.on('select2:select select2:clear', handler);
                    return;
                }
            }
            if (intentos++ < 50) setTimeout(intentar, 100);
        }
        intentar();
    }

    // -------------------------------------------------------
    // INIT
    // -------------------------------------------------------

    function init() {
        var seccion = getSectionImagen();
        if (seccion) {
            var fieldset = seccion.closest('fieldset') || seccion;
            fieldset.style.display = 'none';
        }

        bindSelect2('id_plantilla', function () {
            if (debeBloquearPrecarga()) return;
            onSeleccionCambio();
        });

        bindSelect2('id_paciente', function () {
            if (debeBloquearPrecarga()) return;
            onSeleccionCambio();
        });

        setTimeout(function () {
            var plantillaId = getSelectValue('id_plantilla');
            if (!plantillaId) return;

            if (debeBloquearPrecarga()) {
                onCargaInicialEdicion(plantillaId);
            } else {
                onSeleccionCambio();
            }
        }, 300);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
