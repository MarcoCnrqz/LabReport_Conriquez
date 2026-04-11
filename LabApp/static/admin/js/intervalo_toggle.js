/**
 * intervalo_toggle.js
 * Ubicación: LabApp/static/admin/js/intervalo_toggle.js
 *
 * Oculta / muestra:
 *   1. El inline "Intervalos de referencia" (#intervalos-group)
 *   2. El campo "Unidad" (.field-unidad)
 * …según si el tipo de propiedad es Cualitativo o Cuantitativo.
 *
 * Funciona tanto en modo CREACIÓN (select activo #id_tipo)
 * como en modo EDICIÓN (tipo renderizado como texto readonly en .field-tipo .readonly).
 * Se usa doble requestAnimationFrame + reintentos para cubrir temas admin
 * (Jazzmin, etc.) que renderizan el DOM de forma diferida.
 */

(function () {
    'use strict';

    var INLINE_GROUP_ID = 'intervalos-group';

    // ── Aviso informativo ────────────────────────────────────────────────────
    var AVISO_ID = '_intervalo_toggle_aviso';

    function mostrarAviso(refElement) {
        if (document.getElementById(AVISO_ID)) return;
        var div = document.createElement('div');
        div.id = AVISO_ID;
        div.style.cssText = (
            'margin:8px 0 16px;padding:10px 14px;' +
            'background:#fff8e1;border-left:4px solid #f9a825;' +
            'border-radius:4px;font-size:13px;color:#5d4037;'
        );
        div.textContent = (
            '⚠ Los intervalos de referencia y la unidad no aplican para propiedades ' +
            'cualitativas. Usa el campo "Opciones cualitativas" para definir los valores posibles.'
        );
        refElement.parentNode.insertBefore(div, refElement);
    }

    function ocultarAviso() {
        var aviso = document.getElementById(AVISO_ID);
        if (aviso) aviso.remove();
    }

    // ── Lógica central de mostrar / ocultar ─────────────────────────────────

    function getInlineGroup() {
        return document.getElementById(INLINE_GROUP_ID);
    }

    /**
     * Busca la fila de campo (.form-row) que contiene un elemento con la
     * clase dada. Funciona con el admin estándar de Django y con Jazzmin.
     */
    function getFieldRow(fieldClass) {
        // Intenta primero el selector directo de Django admin
        var el = document.querySelector('.' + fieldClass);
        if (!el) return null;
        // Sube hasta encontrar un <div> o <tr> que sea la fila del campo
        var row = el.closest('.form-row') || el.closest('tr') || el.parentElement;
        return row;
    }

    function ajustar(esCualitativo) {
        // 1. Inline de intervalos de referencia
        var group = getInlineGroup();
        if (group) {
            if (esCualitativo) {
                group.style.display = 'none';
                mostrarAviso(group);
            } else {
                group.style.display = '';
                ocultarAviso();
            }
        } else {
            console.warn('[intervalo_toggle] No se encontró id="' + INLINE_GROUP_ID + '".');
        }

        // 2. Campo "Unidad"
        var unidadRow = getFieldRow('field-unidad');
        if (unidadRow) {
            unidadRow.style.display = esCualitativo ? 'none' : '';
        } else {
            console.warn('[intervalo_toggle] No se encontró .field-unidad');
        }
    }

    // ── Lectura del tipo en modo edición (readonly) ──────────────────────────

    function leerTipoReadonly() {
        var el = document.querySelector('.field-tipo .readonly');
        if (el) {
            var val = el.textContent.trim().toLowerCase();
            console.log('[intervalo_toggle] Tipo leído (readonly):', val);
            return val;
        }
        console.warn('[intervalo_toggle] No se encontró .field-tipo .readonly');
        return null;
    }

    // ── Reintento con límite ─────────────────────────────────────────────────
    // Llama a fn() hasta que devuelva true o se agoten los intentos (~100 ms).

    function conReintentos(fn, maxIntentos, intervalo) {
        var intentos = 0;
        function intento() {
            if (fn()) return;
            intentos++;
            if (intentos < maxIntentos) {
                setTimeout(intento, intervalo);
            } else {
                console.warn('[intervalo_toggle] Se agotaron los reintentos sin encontrar el elemento.');
            }
        }
        intento();
    }

    // ── Inicialización ───────────────────────────────────────────────────────

    function init() {
        var selectTipo = document.getElementById('id_tipo');

        if (selectTipo) {
            // CREACIÓN: select activo
            var valInicial = selectTipo.value.trim().toLowerCase();
            ajustar(valInicial === 'cualitativo');

            selectTipo.addEventListener('change', function () {
                ajustar(this.value.trim().toLowerCase() === 'cualitativo');
            });

        } else {
            // EDICIÓN: tipo renderizado como texto readonly
            // Doble rAF para esperar a que el DOM esté completamente pintado,
            // incluyendo widgets custom (span + botón 📋).
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    var tipoValor = leerTipoReadonly();
                    if (tipoValor !== null) {
                        ajustar(tipoValor === 'cualitativo');
                    } else {
                        // Fallback: reintentar hasta 10 veces cada 100 ms
                        conReintentos(function () {
                            var val = leerTipoReadonly();
                            if (val !== null) {
                                ajustar(val === 'cualitativo');
                                return true;  // éxito
                            }
                            return false;     // seguir reintentando
                        }, 10, 100);
                    }
                });
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
