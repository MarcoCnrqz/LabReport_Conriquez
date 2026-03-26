/**
 * propiedad_tipo_toggle.js
 * Ubicación: LabApp/static/admin/js/propiedad_tipo_toggle.js
 *
 * CORRECCIONES en esta versión:
 *
 *  1. Todas las comparaciones usan .trim().toLowerCase() para manejar
 *     "Cualitativo" (como lo renderiza Django) en lugar de "CUALITATIVO".
 *
 *  2. Para el formulario individual (EDICIÓN), el selector confirmado es:
 *       .field-tipo .readonly   →  texto: "Cualitativo" o "Cuantitativo"
 *
 *  3. Para el inline en PlantillaAdmin, el selector del grupo depende
 *     del ID real. Si el querySelector del inline devuelve null, se loguea
 *     el ID real encontrado para facilitar diagnóstico.
 *     Ejecuta en consola para verificar:
 *       document.querySelectorAll('[id$="-group"]').forEach(e => console.log(e.id))
 */

(function () {
    'use strict';

    // -------------------------------------------------------
    // Helper: el elemento está dentro de un <tr> del inline
    // -------------------------------------------------------
    function dentroDeInline(el) {
        return !!el.closest('tr');
    }

    // -------------------------------------------------------
    // Helper: leer tipo readonly con el selector confirmado
    // -------------------------------------------------------
    function leerTipoReadonly() {
        var el = document.querySelector('.field-tipo .readonly');
        if (el) {
            var val = el.textContent.trim().toLowerCase();
            console.log('[tipo_toggle] Tipo readonly leído:', val);
            return val;
        }
        console.warn('[tipo_toggle] No se encontró .field-tipo .readonly');
        return null;
    }

    // -------------------------------------------------------
    // CONTEXTO 1: fila del inline en PlantillaAdmin
    // -------------------------------------------------------
    function ajustarFilaInline(fila) {
        var selectTipo = fila.querySelector('select[name$="-tipo"]');
        if (!selectTipo) return;

        var inputPk = fila.querySelector('input[name$="-id"]');
        var esExistente = !!(inputPk && inputPk.value !== '');

        if (esExistente) {
            selectTipo.disabled = true;
            selectTipo.title = 'El tipo no puede modificarse una vez guardado';
        }

        var tdUnidad   = fila.querySelector('.field-unidad');
        var tdOpciones = fila.querySelector('.field-opciones_cualitativas');

        function actualizar() {
            // El value del select puede ser "CUALITATIVO" o "CUANTITATIVO"
            // dependiendo del choices del modelo — usar toLowerCase por seguridad
            var esCual = selectTipo.value.trim().toLowerCase() === 'cualitativo';

            if (tdUnidad) {
                tdUnidad.style.display = esCual ? 'none' : '';
                if (esCual) {
                    var inp = tdUnidad.querySelector('input[type="text"]');
                    if (inp) inp.value = '';
                }
            }
            if (tdOpciones) {
                tdOpciones.style.display = esCual ? '' : 'none';
                if (!esCual) {
                    var inp2 = tdOpciones.querySelector('input[type="text"]');
                    if (inp2) inp2.value = '';
                }
            }
        }

        actualizar();

        if (!esExistente && !selectTipo._tipoBoundInline) {
            selectTipo._tipoBoundInline = true;
            selectTipo.addEventListener('change', actualizar);
        }
    }

    // -------------------------------------------------------
    // Buscar el tbody del inline probando varios IDs posibles
    // -------------------------------------------------------
    function encontrarFilasInline() {
        // Intentar selectores conocidos
        var selectores = [
            '#propiedadplantilla_set-group tr.dynamic-propiedadplantilla_set',
            '#propiedades-group tr.dynamic-propiedades',
        ];
        var filas = [];
        selectores.forEach(function (sel) {
            document.querySelectorAll(sel).forEach(function (f) {
                filas.push(f);
            });
        });

        // Si no encontró nada, loguear todos los grupos disponibles para diagnóstico
        if (filas.length === 0) {
            console.warn('[tipo_toggle] No se encontraron filas de inline. Grupos disponibles:');
            document.querySelectorAll('[id$="-group"]').forEach(function (g) {
                console.log('  id:', g.id);
            });
        }
        return filas;
    }

    function encontrarTbodiesInline() {
        var tbodies = [];
        var selectores = [
            '#propiedadplantilla_set-group tbody',
            '#propiedades-group tbody',
        ];
        selectores.forEach(function (sel) {
            var el = document.querySelector(sel);
            if (el) tbodies.push(el);
        });

        // Fallback: si no encontró ninguno, buscar cualquier inline relacionado
        if (tbodies.length === 0) {
            document.querySelectorAll('[id$="-group"] tbody').forEach(function (tb) {
                tbodies.push(tb);
                console.log('[tipo_toggle] Tbody fallback encontrado en:', tb.closest('[id$="-group"]').id);
            });
        }
        return tbodies;
    }

    function ajustarTodasLasFilasInline() {
        encontrarFilasInline().forEach(ajustarFilaInline);
    }

    function observarInline() {
        encontrarTbodiesInline().forEach(function (tbody) {
            new MutationObserver(function (mutations) {
                mutations.forEach(function (m) {
                    m.addedNodes.forEach(function (node) {
                        if (node.nodeType === 1 && node.tagName === 'TR') {
                            // Esperar a que los widgets custom terminen de renderizar
                            requestAnimationFrame(function () {
                                requestAnimationFrame(function () {
                                    ajustarFilaInline(node);
                                });
                            });
                        }
                    });
                });
            }).observe(tbody, { childList: true });
        });
    }

    // -------------------------------------------------------
    // CONTEXTO 2: formulario individual (PropiedadPlantillaAdmin)
    // Busca campos fuera de <tr> para no confundir con el inline
    // -------------------------------------------------------
    function obtenerRowFormPrincipal(clase) {
        var todos = document.querySelectorAll('.' + clase);
        for (var i = 0; i < todos.length; i++) {
            if (!dentroDeInline(todos[i])) return todos[i];
        }
        return null;
    }

    function ajustarFormIndividual() {
        var rowUnidad   = obtenerRowFormPrincipal('field-unidad');
        var rowOpciones = obtenerRowFormPrincipal('field-opciones_cualitativas');

        if (!rowUnidad && !rowOpciones) return;

        function aplicar(esCual) {
            if (rowUnidad)   rowUnidad.style.display   = esCual ? 'none' : '';
            if (rowOpciones) rowOpciones.style.display = esCual ? ''     : 'none';
        }

        var selectTipo = document.getElementById('id_tipo');

        if (selectTipo) {
            // CREACIÓN
            aplicar(selectTipo.value.trim().toLowerCase() === 'cualitativo');
            if (!selectTipo._tipoBoundForm) {
                selectTipo._tipoBoundForm = true;
                selectTipo.addEventListener('change', function () {
                    aplicar(this.value.trim().toLowerCase() === 'cualitativo');
                });
            }
        } else {
            // EDICIÓN: tipo readonly — selector confirmado: .field-tipo .readonly
            var tipoValor = leerTipoReadonly();
            if (tipoValor !== null) {
                aplicar(tipoValor === 'cualitativo');
            }
        }
    }

    // -------------------------------------------------------
    // INIT — doble requestAnimationFrame para asegurar que
    // los widgets custom (span + botón 📋) ya estén en el DOM
    // -------------------------------------------------------
    function init() {
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                ajustarTodasLasFilasInline();
                observarInline();
                ajustarFormIndividual();
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
