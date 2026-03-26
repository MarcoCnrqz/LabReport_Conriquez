/**
 * intervalo_toggle.js
 * Ubicación: LabApp/static/admin/js/intervalo_toggle.js
 *
 * CORRECCIÓN:
 *   En modo edición el tipo aparece como texto readonly.
 *   Se agregó doble requestAnimationFrame (igual que propiedad_tipo_toggle.js)
 *   para garantizar que el DOM esté completamente renderizado antes de leer
 *   el valor, incluyendo los widgets custom (span + botón 📋).
 *
 *   También se agrega un mecanismo de reintento (retry) por si el elemento
 *   aún no existe tras el primer rAF — esto cubre casos con Django Jazzmin
 *   u otros temas admin que cargan el DOM de forma diferida.
 */

(function () {
    'use strict';

    var INLINE_GROUP_ID = 'intervalos-group';

    function getInlineGroup() {
        return document.getElementById(INLINE_GROUP_ID);
    }

    function ajustar(esCualitativo) {
        var group = getInlineGroup();
        if (!group) {
            console.warn('[intervalo_toggle] No se encontró id="' + INLINE_GROUP_ID + '".');
            return;
        }
        if (esCualitativo) {
            group.style.display = 'none';
            mostrarAviso(group);
        } else {
            group.style.display = '';
            ocultarAviso();
        }
    }

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
            '⚠ Los intervalos de referencia no aplican para propiedades cualitativas. ' +
            'Usa el campo "Opciones cualitativas" para definir los valores posibles.'
        );
        refElement.parentNode.insertBefore(div, refElement);
    }

    function ocultarAviso() {
        var aviso = document.getElementById(AVISO_ID);
        if (aviso) aviso.remove();
    }

    function leerTipoReadonly() {
        // Selector confirmado: .field-tipo .readonly
        // Django renderiza "Cualitativo" o "Cuantitativo" (con mayúscula inicial)
        var el = document.querySelector('.field-tipo .readonly');
        if (el) {
            var val = el.textContent.trim().toLowerCase();
            console.log('[intervalo_toggle] Tipo leído:', val);
            return val;
        }
        console.warn('[intervalo_toggle] No se encontró .field-tipo .readonly');
        return null;
    }

    // -------------------------------------------------------
    // Reintento con límite: llama a fn() hasta que devuelva
    // true o se agoten los intentos (cada ~100 ms).
    // Cubre temas admin que renderizan el DOM de forma diferida.
    // -------------------------------------------------------
    function conReintentos(fn, maxIntentos, intervalo) {
        var intentos = 0;
        function intento() {
            if (fn()) return;           // éxito
            intentos++;
            if (intentos < maxIntentos) {
                setTimeout(intento, intervalo);
            } else {
                console.warn('[intervalo_toggle] Se agotaron los reintentos sin encontrar el elemento.');
            }
        }
        intento();
    }

    function init() {
        var selectTipo = document.getElementById('id_tipo');

        if (selectTipo) {
            // ── CREACIÓN: select activo ──────────────────────────
            var valInicial = selectTipo.value.trim().toLowerCase();
            ajustar(valInicial === 'cualitativo');
            selectTipo.addEventListener('change', function () {
                ajustar(this.value.trim().toLowerCase() === 'cualitativo');
            });
        } else {
            // ── EDICIÓN: tipo readonly ───────────────────────────
            // Usar doble rAF (igual que propiedad_tipo_toggle.js) +
            // reintentos para garantizar que el DOM esté listo.
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
                                return true;  // éxito, detener reintentos
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
