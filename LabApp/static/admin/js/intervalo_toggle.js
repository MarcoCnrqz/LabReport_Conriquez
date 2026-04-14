/**
 * intervalo_toggle.js
 * Ubicación: LabApp/static/admin/js/intervalo_toggle.js
 *
 * Oculta / muestra según si el tipo de propiedad es Cualitativo o Cuantitativo:
 *
 *   CUANTITATIVO:
 *     ✅ Muestra  → Intervalos de referencia (#intervalos-group)
 *     ✅ Muestra  → Campo "Unidad" (.field-unidad)
 *     ❌ Oculta   → Campo "Opciones cualitativas" (.field-opciones_cualitativas)
 *
 *   CUALITATIVO:
 *     ❌ Oculta   → Intervalos de referencia (#intervalos-group)
 *     ❌ Oculta   → Campo "Unidad" (.field-unidad)
 *     ✅ Muestra  → Campo "Opciones cualitativas" (.field-opciones_cualitativas)
 *
 * Funciona tanto en modo CREACIÓN (select activo #id_tipo)
 * como en modo EDICIÓN (tipo renderizado como texto readonly en .field-tipo .readonly).
 * Se usa doble requestAnimationFrame + reintentos para cubrir temas admin
 * (Jazzmin, etc.) que renderizan el DOM de forma diferida.
 */

(function () {
    'use strict';

    var INLINE_GROUP_ID = 'intervalos-group';

    // ── Aviso informativo (cualitativo) ─────────────────────────────────────
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

    // ── Helpers de campo ────────────────────────────────────────────────────

    function getInlineGroup() {
        return document.getElementById(INLINE_GROUP_ID);
    }

    /**
     * Busca la fila de campo (.form-row) que contiene un elemento con la
     * clase dada. Funciona con el admin estándar de Django y con Jazzmin.
     * Prueba múltiples selectores para mayor robustez.
     */
    function getFieldRow(fieldClass) {
        // Intentar con el nombre exacto de clase (guiones bajos)
        var selectors = [
            '.' + fieldClass,
            // Django a veces usa guión medio en vez de guión bajo
            '.' + fieldClass.replace(/_/g, '-'),
        ];

        var el = null;
        for (var i = 0; i < selectors.length; i++) {
            el = document.querySelector(selectors[i]);
            if (el) break;
        }
        if (!el) return null;
        return el.closest('.form-row') || el.closest('tr') || el.parentElement;
    }

    // ── Lógica central ──────────────────────────────────────────────────────

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

        // 2. Campo "Unidad" — solo para cuantitativos
        var unidadRow = getFieldRow('field-unidad');
        if (unidadRow) {
            unidadRow.style.display = esCualitativo ? 'none' : '';
        } else {
            console.warn('[intervalo_toggle] No se encontró .field-unidad');
        }

        // 3. Campo "Opciones cualitativas" — solo para cualitativos
        //    Se busca por la clase del contenedor que genera Django admin.
        //    También se intenta localizar por el id del input como fallback.
        var opcionesRow = getFieldRow('field-opciones_cualitativas');

        // Fallback: buscar por el id del input que genera el widget
        if (!opcionesRow) {
            var inputOpciones = document.getElementById('id_opciones_cualitativas');
            if (inputOpciones) {
                opcionesRow = inputOpciones.closest('.form-row') ||
                              inputOpciones.closest('tr') ||
                              inputOpciones.closest('p') ||
                              inputOpciones.parentElement;
            }
        }

        if (opcionesRow) {
            opcionesRow.style.display = esCualitativo ? '' : 'none';
        } else {
            console.warn('[intervalo_toggle] No se encontró .field-opciones_cualitativas ni #id_opciones_cualitativas');
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
            // CREACIÓN: select activo.
            // Si el valor es vacío (opción "-------"), se trata como cuantitativo
            // (estado por defecto más seguro: mostrar intervalos, ocultar opciones cuali).
            var valInicial = selectTipo.value.trim().toLowerCase();
            var esCualiInicial = (valInicial === 'cualitativo');
            ajustar(esCualiInicial);

            selectTipo.addEventListener('change', function () {
                ajustar(this.value.trim().toLowerCase() === 'cualitativo');
            });

        } else {
            // EDICIÓN: tipo renderizado como texto readonly.
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
