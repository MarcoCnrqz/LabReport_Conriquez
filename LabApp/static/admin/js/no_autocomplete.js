/**
 * no_autocomplete.js
 *
 * Desactiva el autocompletado del historial del navegador en todos los
 * campos de texto del admin de Django.
 *
 * Los campos del widget SugerenciasDropdownWidget ya traen
 * autocomplete="new-password" (que fuerza al navegador a no sugerir).
 * Este script cubre el resto de inputs que no pasan por ese widget.
 *
 * Ubicación: static/admin/js/no_autocomplete.js
 */
(function () {
    'use strict';

    function desactivarAutocomplete() {
        var selectores = [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="number"]',
            'input[type="search"]',
            'input[type="tel"]',
            'input[type="url"]',
            'textarea',
        ].join(', ');

        document.querySelectorAll(selectores).forEach(function (el) {
            // Respetar los que ya tienen autocomplete configurado
            // (ej. SugerenciasDropdownWidget usa 'new-password')
            if (!el.getAttribute('autocomplete')) {
                el.setAttribute('autocomplete', 'off');
            }
        });
    }

    // Ejecutar en carga inicial
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', desactivarAutocomplete);
    } else {
        desactivarAutocomplete();
    }

    // Volver a ejecutar si Django Admin agrega filas dinámicas (inlines)
    document.addEventListener('formset:added', desactivarAutocomplete);
})();
