/**
 * plantilla_propiedades_picker.js
 * Coloca en: <tu_app>/static/admin/js/plantilla_propiedades_picker.js
 *
 * FIXES v4:
 *  - BUG FIX: el dropdown de búsqueda LOINC se renderizaba DENTRO de un
 *    <td> de <table>, lo que causaba que el overflow de la tabla lo
 *    recortara visualmente y bloqueara los clics. Ahora se usa un popup
 *    único con `position: fixed` anclado a <body> (igual que
 *    SugerenciasDropdownWidget), por lo que funciona sin importar la
 *    estructura de la tabla.
 *  - Búsqueda LOINC contextual: lee tipo_muestra y metodo del formulario.
 *  - Pre-rellena el input con el nombre de la propiedad al abrir.
 *  - Badge visual cuando los resultados están filtrados por contexto.
 *  - Inputs ocultos: pp_picker_ids, pp_picker_loinc_ids,
 *                    pp_picker_ordenes, pp_picker_secciones.
 */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {

    /* ── Solo actuar en la página de Plantilla ─────────────────────────── */
    var inlineGroup = document.querySelector('#plantilla_propiedades-group');
    if (!inlineGroup) return;

    /* ── Leer datos JSON inyectados por get_fieldsets ──────────────────── */
    var propsEl     = document.querySelector('script#pp-props-data');
    var existEl     = document.querySelector('script#pp-existing-data');
    var seccionesEl = document.querySelector('script#pp-secciones-data');

    var allProps  = propsEl     ? JSON.parse(propsEl.textContent)     : [];
    var secciones = seccionesEl ? JSON.parse(seccionesEl.textContent) : [];

    var existentes = [];
    if (existEl) {
      try {
        var parsed = JSON.parse(existEl.textContent);
        if (Array.isArray(parsed)) existentes = parsed;
      } catch(e) { existentes = []; }
    }

    /* ── Estado en memoria ─────────────────────────────────────────────── */
    var selected = existentes.map(function (e) {
      return {
        propId:        String(e.propId),
        nombre:        e.nombre,
        loincId:       String(e.loincId       || ''),
        loincNum:      String(e.loincNum      || ''),
        loincDesc:     String(e.loincDesc     || ''),
        orden:         parseInt(e.orden, 10)  || 1,
        seccionId:     String(e.seccionId     || ''),
        seccionNombre: String(e.seccionNombre || ''),
      };
    });

    /* ── Ocultar inline original ────────────────────────────────────────── */
    inlineGroup.style.display = 'none';

    /* ── Construir widget ───────────────────────────────────────────────── */
    var container = document.createElement('div');
    container.id  = 'pp-picker-root';
    container.innerHTML = buildHTML();
    inlineGroup.parentNode.insertBefore(container, inlineGroup.nextSibling);

    /* Inputs ocultos para save_model */
    var hiddenIds        = addHidden('pp_picker_ids');
    var hiddenLoincIds   = addHidden('pp_picker_loinc_ids');
    var hiddenOrdenes    = addHidden('pp_picker_ordenes');
    var hiddenSeccionIds = addHidden('pp_picker_secciones');

    function addHidden(name) {
      var inp  = document.createElement('input');
      inp.type = 'hidden';
      inp.name = name;
      container.appendChild(inp);
      return inp;
    }

    /* ══════════════════════════════════════════════════════════════════════
       POPUP LOINC — único, position:fixed, anclado a <body>
       FIX: antes se renderizaba dentro del <td>, donde overflow:hidden de
       la tabla cortaba el dropdown e impedía los clics en los resultados.
    ══════════════════════════════════════════════════════════════════════ */

    var loincPopup     = null;   // el elemento DOM del popup
    var loincDebounce  = null;   // timeout de debounce de búsqueda
    var currentLoincIdx = -1;   // índice de selected[] que está editando

    /**
     * Crea el popup LOINC una sola vez y lo añade al body.
     * Usa position:fixed para que no quede limitado por overflow de la tabla.
     */
    function createLoincPopup() {
      var popup = document.createElement('div');
      popup.id = 'pp-loinc-popup';
      popup.style.cssText = [
        'display:none',
        'position:fixed',
        'z-index:999999',
        'background:#fff',
        'border:1px solid #bbb',
        'border-radius:6px',
        'box-shadow:0 4px 20px rgba(0,0,0,.22)',
        'padding:8px',
        'min-width:380px',
        'max-width:620px',
        'box-sizing:border-box',
      ].join(';');

      popup.innerHTML = [
        '<div style="display:flex;gap:6px;align-items:center;margin-bottom:6px;">',
        '<input id="pp-loinc-popup-inp" type="text" autocomplete="off"',
        ' placeholder="Buscar código LOINC..."',
        ' style="flex:1;box-sizing:border-box;padding:6px 10px;',
        'border:1px solid #bbb;border-radius:4px;font-size:13px;">',
        '<a id="pp-loinc-ext-btn" href="https://loinc.org/search/" target="_blank"',
        ' title="Buscar en loinc.org" style="',
        'display:inline-flex;align-items:center;gap:3px;padding:5px 8px;',
        'background:#1a6fa8;color:#fff;border-radius:4px;text-decoration:none;',
        'font-size:12px;white-space:nowrap;flex-shrink:0;',
        '">🌐 LOINC.org</a>',
        '</div>',
        '<div id="pp-loinc-popup-results"',
        ' style="max-height:260px;overflow-y:auto;border-top:1px solid #eee;padding-top:4px;">',
        '<div class="pp-lm-hint">Escribe para buscar…</div>',
        '</div>',
      ].join('');

      document.body.appendChild(popup);

      /* Eventos del input del popup */
      var inp = popup.querySelector('#pp-loinc-popup-inp');
      inp.addEventListener('input', function () {
        var q = inp.value.trim();
        // Actualizar link de LOINC.org con el término actual
        var extBtn = document.getElementById('pp-loinc-ext-btn');
        if (extBtn) {
          extBtn.href = q
            ? 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(q)
            : 'https://loinc.org/search/';
        }
        clearTimeout(loincDebounce);
        if (q.length < 2) {
          document.getElementById('pp-loinc-popup-results').innerHTML =
            '<div class="pp-lm-hint">Escribe al menos 2 caracteres…</div>';
          return;
        }
        loincDebounce = setTimeout(function () {
          doLoincSearch(q, currentLoincIdx);
        }, 280);
      });

      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') hideLoincPopup();
      });

      return popup;
    }

    /** Muestra el popup anclado al botón que lo abrió. */
    function showLoincPopup(idx, btnEl) {
      if (!loincPopup) loincPopup = createLoincPopup();

      currentLoincIdx = idx;

      /* Posicionar cerca del botón, igual que SugerenciasDropdownWidget */
      var rect    = btnEl.getBoundingClientRect();
      var popup   = loincPopup;
      var popupW  = 400;
      var popupH  = 320;

      popup.style.display = 'block';

      var top = (window.innerHeight - rect.bottom >= popupH || rect.top < popupH)
        ? rect.bottom + 4
        : rect.top - popupH - 4;

      var left = Math.min(rect.left, window.innerWidth - popupW - 8);

      popup.style.top  = top  + 'px';
      popup.style.left = left + 'px';

      /* Pre-rellenar con el nombre de la propiedad y buscar automáticamente */
      var inp = document.getElementById('pp-loinc-popup-inp');
      var nombreProp = (selected[idx] && selected[idx].nombre) ? selected[idx].nombre : '';
      inp.value = nombreProp;
      inp.focus();
      inp.select();
      // Sincronizar el link de LOINC.org con el nombre pre-llenado
      var extBtn2 = document.getElementById('pp-loinc-ext-btn');
      if (extBtn2 && nombreProp) {
        extBtn2.href = 'https://loinc.org/search/?t=1&q=' + encodeURIComponent(nombreProp);
      }

      var resultsEl = document.getElementById('pp-loinc-popup-results');
      if (nombreProp.length >= 2) {
        resultsEl.innerHTML = '<div class="pp-lm-hint">Buscando…</div>';
        doLoincSearch(nombreProp, idx);
      } else {
        resultsEl.innerHTML = '<div class="pp-lm-hint">Escribe para buscar…</div>';
      }
    }

    /** Oculta el popup LOINC. */
    function hideLoincPopup() {
      if (loincPopup) {
        loincPopup.style.display = 'none';
      }
      currentLoincIdx = -1;
    }

    /* Cerrar popup al hacer clic fuera */
    document.addEventListener('click', function (e) {
      if (!loincPopup || loincPopup.style.display === 'none') return;
      if (!e.target.closest('#pp-loinc-popup') && !e.target.closest('.pp-loinc-btn')) {
        hideLoincPopup();
      }
    });

    /* Cerrar popup al hacer scroll/resize — pero NO si el scroll ocurre
       dentro del propio popup (el usuario scrollea la lista de resultados).
       FIX: la versión anterior usaba `true` como tercer argumento (capture),
       lo que capturaba TODOS los eventos scroll del documento incluyendo el
       del div interno de resultados, cerrando el popup al intentar scrollear
       la lista. Ahora verificamos que el target no sea el popup ni un hijo. */
    ['scroll', 'resize'].forEach(function (ev) {
      window.addEventListener(ev, function (e) {
        if (!loincPopup || loincPopup.style.display === 'none') return;
        // Si el scroll es dentro del popup (lista de resultados), ignorar
        if (loincPopup.contains(e.target)) return;
        hideLoincPopup();
      }, true);
    });

    /* ══════════════════════════════════════════════════════════════════════
       HELPERS — leer tipo_muestra y metodo del formulario de la plantilla
    ══════════════════════════════════════════════════════════════════════ */

    function getMuestra() {
      var el = document.getElementById('id_tipo_muestra');
      return el ? el.value.trim() : '';
    }

    function getMetodo() {
      var el = document.getElementById('id_metodo');
      return el ? el.value.trim() : '';
    }

    /* ═══════════════════════════════════════════════════════════════════
       BÚSQUEDA LOINC via AJAX
    ═══════════════════════════════════════════════════════════════════ */
    function doLoincSearch(q, idx) {
      var resultsEl = document.getElementById('pp-loinc-popup-results');
      if (!resultsEl) return;
      resultsEl.innerHTML = '<div class="pp-lm-hint">Buscando…</div>';

      var muestra = getMuestra();
      var metodo  = getMetodo();

      // Construir el URL del endpoint de forma dinámica usando la URL actual
      // (/admin/LabApp/plantilla/add/ → /admin/LabApp/plantilla/loinc-buscar/)
      // Esto evita errores si la app usa distinto caso (LabApp vs labapp).
      var adminBase = (function () {
        var m = window.location.pathname.match(/^(\/admin\/[^/]+\/plantilla\/)/i);
        return m ? m[1] : '/admin/LabApp/plantilla/';
      })();
      var url = adminBase + 'loinc-buscar/?q=' + encodeURIComponent(q);
      if (muestra) url += '&muestra=' + encodeURIComponent(muestra);
      if (metodo)  url += '&metodo='  + encodeURIComponent(metodo);

      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) {
          if (!r.ok) {
            return r.text().then(function (txt) {
              console.error('[LOINC popup] HTTP', r.status, url, txt.slice(0, 400));
              throw new Error('HTTP ' + r.status);
            });
          }
          return r.json();
        })
        .then(function (data) {
          /* Ignorar respuesta obsoleta si el usuario abrió otra fila */
          if (currentLoincIdx !== idx) return;

          resultsEl = document.getElementById('pp-loinc-popup-results');
          if (!resultsEl) return;

          if (!data.results || data.results.length === 0) {
            resultsEl.innerHTML =
              '<div class="pp-lm-hint">Sin resultados para "' + escHtml(q) + '"' +
              (data.filtrado ? ' con el filtro de muestra/método actual' : '') +
              '</div>';
            return;
          }

          resultsEl.innerHTML = '';

          /* Badge de contexto */
          if (data.filtrado && (data.muestra || data.metodo)) {
            var badge = document.createElement('div');
            badge.className = 'pp-lm-context-badge';
            var partes = [];
            if (data.muestra) partes.push('🧪 ' + escHtml(data.muestra));
            if (data.metodo)  partes.push('⚙️ '  + escHtml(data.metodo));
            badge.innerHTML =
              '<span class="pp-lm-ctx-label">Filtrado por contexto:</span> ' +
              partes.join(' · ');
            resultsEl.appendChild(badge);
          }

          /* Nivel de filtrado en consola (útil para debugging) */
          if (data.nivel_filtrado) {
            console.debug('[LOINC] nivel_filtrado:', data.nivel_filtrado,
              '| resultados:', data.results.length);
          }

          data.results.forEach(function (lc) {
            var row = document.createElement('div');
            row.className = 'pp-lm-row';

            var nombre = lc.shortname || lc.component || '';
            var meta = [];
            if (lc.system)     meta.push(lc.system);
            if (lc.property)   meta.push(lc.property);
            if (lc.scale_typ)  meta.push(lc.scale_typ);
            if (lc.method_typ) meta.push('⚙ ' + lc.method_typ);

            row.innerHTML =
              '<span class="pp-lm-num">'  + escHtml(lc.loinc_num) + '</span>' +
              '<span class="pp-lm-name">' + escHtml(nombre) + '</span>' +
              (meta.length
                ? '<span class="pp-lm-sys">' + escHtml(meta.join(' · ')) + '</span>'
                : '');

            row.addEventListener('click', function (e) {
              /* FIX: stopPropagation evita que el document listener cierre el
                 popup antes de que terminemos de procesar la selección. */
              e.stopPropagation();
              selected[idx].loincId      = String(lc.id);
              selected[idx].loincNum     = lc.loinc_num;
              selected[idx].loincDesc    = lc.shortname || lc.component || '';
              delete selected[idx].loincSugerido;   // el usuario eligió manualmente
              delete selected[idx].loincPendiente;
              hideLoincPopup();
              renderTable();
            });

            resultsEl.appendChild(row);
          });
        })
        .catch(function (err) {
          var el = document.getElementById('pp-loinc-popup-results');
          if (el)
            el.innerHTML =
              '<div class="pp-lm-hint" style="color:#c0392b;">Error al buscar (' + (err.message || 'red') + '). Revisa la consola del navegador (F12).</div>';
        });
    }

    /* ═══════════════════════════════════════════════════════════════════
       RENDER — Lista izquierda
    ═══════════════════════════════════════════════════════════════════ */
    function renderList(filter) {
      filter   = (filter || '').toLowerCase();
      var list = document.getElementById('pp-list');
      list.innerHTML = '';

      var visible = allProps.filter(function (p) {
        return p.nombre.toLowerCase().indexOf(filter) >= 0;
      });

      if (visible.length === 0) {
        list.innerHTML = '<div class="pp-empty-msg">Sin resultados</div>';
        return;
      }

      visible.forEach(function (p) {
        var isSel  = selected.some(function (s) { return s.propId === String(p.id); });
        var div    = document.createElement('div');
        div.className = 'pp-item' + (isSel ? ' pp-item--sel' : '');
        var dotCls = p.tipo === 'CUANTITATIVO' ? 'pp-dot--c' : 'pp-dot--q';
        div.innerHTML =
          '<span class="pp-dot ' + dotCls + '"></span>' +
          '<span class="pp-item-name">' + escHtml(p.nombre) + '</span>' +
          (isSel ? '<span class="pp-check">&#10003;</span>' : '');
        div.addEventListener('click', function () { toggleProp(String(p.id)); });
        list.appendChild(div);
      });
    }

    /* ═══════════════════════════════════════════════════════════════════
       RENDER — Tabla derecha
       FIX: se eliminó el bloque pp-loinc-search-wrap / pp-loinc-dropdown
       de dentro del <td>. Ahora solo hay un botón que abre el popup
       global de position:fixed (loincPopup) definido arriba.
    ═══════════════════════════════════════════════════════════════════ */
    function renderTable() {
      var tbody   = document.getElementById('pp-tbody');
      var empty   = document.getElementById('pp-empty');
      var table   = document.getElementById('pp-table');
      var countEl = document.getElementById('pp-count');

      countEl.textContent = selected.length ? '(' + selected.length + ')' : '';

      if (selected.length === 0) {
        table.style.display = 'none';
        empty.style.display = 'block';
        syncHiddens();
        return;
      }
      table.style.display = '';
      empty.style.display = 'none';
      tbody.innerHTML     = '';

      selected.forEach(function (s, idx) {
        var p       = getProp(s.propId) || { nombre: s.nombre, tipo: '' };
        var isCuant = p.tipo === 'CUANTITATIVO';
        var tr      = document.createElement('tr');
        tr.dataset.idx = idx;

        /* Celda LOINC — solo muestra el valor actual + botón de abrir popup */
        var loincDisplay;
        if (s.loincPendiente) {
          loincDisplay = '<span class="pp-loinc-buscando">⏳ Buscando…</span>';
        } else if (s.loincNum) {
          loincDisplay =
            (s.loincSugerido
              ? '<span class="pp-loinc-badge-sug" title="Asignado automáticamente. Haz clic en 🔍 para cambiarlo.">✨ sugerido</span> '
              : '') +
            escHtml(s.loincNum) + (s.loincDesc
              ? ' <span class="pp-loinc-desc">— ' + escHtml(s.loincDesc) + '</span>'
              : '');
        } else {
          loincDisplay = '<span class="pp-loinc-empty">Sin asignar</span>';
        }

        /* Celda Serie (sección) */
        var seccionOptions = '<option value="">— Sin serie —</option>';
        secciones.forEach(function (sec) {
          var sel = (String(sec.id) === String(s.seccionId)) ? ' selected' : '';
          seccionOptions +=
            '<option value="' + escHtml(sec.id) + '"' + sel + '>' +
            escHtml(sec.nombre) + '</option>';
        });

        tr.innerHTML =
          /* Nombre */
          '<td class="pp-td-name">' + escHtml(p.nombre || s.nombre) + '</td>' +
          /* Tipo */
          '<td>' +
            '<span class="pp-badge ' + (isCuant ? 'pp-badge--c' : 'pp-badge--q') + '">' +
              (isCuant ? 'Cuant.' : 'Cual.') +
            '</span>' +
          '</td>' +
          /* LOINC — valor actual + botón que abre el popup global */
          '<td class="pp-td-loinc">' +
            '<div class="pp-loinc-wrap">' +
              '<div class="pp-loinc-display" id="pp-lv-' + idx + '">' + loincDisplay + '</div>' +
              '<div class="pp-loinc-actions">' +
                '<button type="button" class="pp-loinc-btn" data-idx="' + idx + '" title="Buscar código LOINC">&#128269;</button>' +
                (s.loincNum
                  ? '<button type="button" class="pp-loinc-clear" data-idx="' + idx + '" title="Quitar LOINC">&#x2715;</button>'
                  : '') +
              '</div>' +
            '</div>' +
          '</td>' +
          /* Serie */
          '<td class="pp-td-serie">' +
            '<select class="pp-sel-serie" data-idx="' + idx + '">' +
              seccionOptions +
            '</select>' +
          '</td>' +
          /* Orden */
          '<td class="pp-td-orden">' +
            '<span class="pp-orden-num">' + s.orden + '</span>' +
          '</td>' +
          /* Quitar */
          '<td>' +
            '<button type="button" class="pp-remove" data-idx="' + idx + '" title="Quitar propiedad">&#x2715;</button>' +
          '</td>';

        tbody.appendChild(tr);
      });

      /* ── Eventos: abrir popup LOINC ─────────────────────────────────────── */
      tbody.querySelectorAll('.pp-loinc-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          var idx = parseInt(btn.dataset.idx, 10);
          /* Si el popup ya está abierto para esta fila, cerrarlo */
          if (currentLoincIdx === idx && loincPopup && loincPopup.style.display !== 'none') {
            hideLoincPopup();
          } else {
            showLoincPopup(idx, btn);
          }
        });
      });

      /* ── Eventos: limpiar LOINC ─────────────────────────────────────────── */
      tbody.querySelectorAll('.pp-loinc-clear').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var i = parseInt(btn.dataset.idx, 10);
          selected[i].loincId   = '';
          selected[i].loincNum  = '';
          selected[i].loincDesc = '';
          delete selected[i].loincSugerido;
          delete selected[i].loincPendiente;
          renderTable();
        });
      });

      /* ── Eventos: cambiar serie ─────────────────────────────────────────── */
      tbody.querySelectorAll('.pp-sel-serie').forEach(function (sel) {
        sel.addEventListener('change', function () {
          var i     = parseInt(sel.dataset.idx, 10);
          var secId = sel.value;
          var secNombre = '';
          if (secId) {
            var found = secciones.find(function (s) { return String(s.id) === String(secId); });
            if (found) secNombre = found.nombre;
          }
          selected[i].seccionId     = secId;
          selected[i].seccionNombre = secNombre;
          syncHiddens();
        });
      });

      /* ── Eventos: quitar propiedad ──────────────────────────────────────── */
      tbody.querySelectorAll('.pp-remove').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var i = parseInt(btn.dataset.idx, 10);
          /* Cerrar popup si estaba abierto para esta fila */
          if (currentLoincIdx === i) hideLoincPopup();
          selected.splice(i, 1);
          recalcOrden();
          renderList(document.getElementById('pp-search').value);
          renderTable();
        });
      });

      syncHiddens();
    }

    /* ═══════════════════════════════════════════════════════════════════
       ORDEN AUTOMÁTICO
    ═══════════════════════════════════════════════════════════════════ */
    function recalcOrden() {
      selected.forEach(function (s, i) {
        s.orden = i + 1;
      });
    }

    /* ═══════════════════════════════════════════════════════════════════
       SYNC — inputs ocultos → POST
    ═══════════════════════════════════════════════════════════════════ */
    function syncHiddens() {
      hiddenIds.value        = selected.map(function (s) { return s.propId;    }).join(',');
      hiddenLoincIds.value   = selected.map(function (s) { return s.loincId;   }).join(',');
      hiddenOrdenes.value    = selected.map(function (s) { return s.orden;     }).join(',');
      hiddenSeccionIds.value = selected.map(function (s) { return s.seccionId; }).join(',');
    }

    /* ═══════════════════════════════════════════════════════════════════
       TOGGLE selección en lista izquierda
    ═══════════════════════════════════════════════════════════════════ */
    function toggleProp(id) {
      var idx = selected.findIndex(function (s) { return s.propId === id; });
      if (idx >= 0) {
        selected.splice(idx, 1);
        recalcOrden();
        renderList(document.getElementById('pp-search').value);
        renderTable();
      } else {
        var p = getProp(id);
        var newEntry = {
          propId:        id,
          nombre:        p ? p.nombre : ('Propiedad #' + id),
          loincId:       '',
          loincNum:      '',
          loincDesc:     '',
          loincPendiente: true,   // marca visual de "buscando…"
          orden:         selected.length + 1,
          seccionId:     '',
          seccionNombre: '',
        };
        selected.push(newEntry);
        var newIdx = selected.length - 1;
        recalcOrden();
        renderList(document.getElementById('pp-search').value);
        renderTable();
        // Intentar asignar LOINC automáticamente si hay muestra/método definidos
        autoAsignarLoinc(newIdx, newEntry.nombre);
      }
    }

    /* ═══════════════════════════════════════════════════════════════════
       AUTO-ASIGNACIÓN LOINC al agregar una propiedad
       ─────────────────────────────────────────────────────────────────
       Busca el mejor código LOINC usando el nombre de la propiedad +
       el tipo_muestra y método del formulario (igual que la búsqueda
       manual). Estrategia corregida:

         • 1 resultado  → asigna automáticamente (certeza total).
         • 2–4 resultados CON filtro estricto activo (system+method sin
           nulls, nivel 'system+method_estricto') → asigna el 1º y
           marca badge "sugerido". El filtro estricto garantiza que
           todos los candidatos son contextualmente correctos.
         • Cualquier otro caso → NO asigna; el botón 🔍 queda disponible.

       La diferencia clave respecto a la versión anterior es que ahora
       solo se auto-asigna cuando el backend usó el nivel MÁS ESTRICTO
       de filtrado (method_typ real, no nulls), lo que hace la señal
       confiable. Con el filtro relax (que incluía nulls) no se asigna
       automáticamente porque los resultados son ambiguos.
    ═══════════════════════════════════════════════════════════════════ */
    function autoAsignarLoinc(idx, nombreProp) {
      var muestra = getMuestra();
      var metodo  = getMetodo();

      // Sin contexto (ni muestra ni método) no hay base para auto-asignar.
      if (!muestra && !metodo) {
        if (selected[idx]) {
          delete selected[idx].loincPendiente;
          renderTable();
        }
        return;
      }

      if (!nombreProp || nombreProp.length < 2) {
        if (selected[idx]) {
          delete selected[idx].loincPendiente;
          renderTable();
        }
        return;
      }

      var adminBase2 = (function () {
        var m = window.location.pathname.match(/^(\/admin\/[^/]+\/plantilla\/)/i);
        return m ? m[1] : '/admin/LabApp/plantilla/';
      })();
      var url = adminBase2 + 'loinc-buscar/?q=' + encodeURIComponent(nombreProp);
      if (muestra) url += '&muestra=' + encodeURIComponent(muestra);
      if (metodo)  url += '&metodo='  + encodeURIComponent(metodo);

      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!selected[idx]) return;

          delete selected[idx].loincPendiente;

          if (!data.results || data.results.length === 0) {
            renderTable();
            return;
          }

          var lc            = data.results[0];
          var total         = data.results.length;
          var nivelFiltrado = data.nivel_filtrado || '';

          // Asignación automática solo con certeza alta:
          //   • 1 resultado exacto (cualquier nivel de filtrado)
          //   • 2–4 resultados SOLO si el filtro estricto (method real) estuvo activo.
          //     Con el filtro relax o sin contexto los resultados son ambiguos.
          var filtroEstricto = (nivelFiltrado === 'system+method_estricto' ||
                                nivelFiltrado === 'solo_method_estricto');

          if (total === 1) {
            selected[idx].loincId   = String(lc.id);
            selected[idx].loincNum  = lc.loinc_num;
            selected[idx].loincDesc = lc.shortname || lc.component || '';
            // 1 resultado → certeza total, sin badge de sugerido
          } else if (total <= 4 && filtroEstricto) {
            selected[idx].loincId      = String(lc.id);
            selected[idx].loincNum     = lc.loinc_num;
            selected[idx].loincDesc    = lc.shortname || lc.component || '';
            selected[idx].loincSugerido = true;  // badge amarillo → usuario puede cambiar
          }
          // Con >4 resultados, o filtro no estricto: no asignar.
          // El botón 🔍 sigue disponible para elección manual.

          renderTable();
          syncHiddens();
        })
        .catch(function () {
          if (selected[idx]) {
            delete selected[idx].loincPendiente;
            renderTable();
          }
        });
    }

    /* ── Búsqueda de propiedades ─────────────────────────────────────────── */
    document.getElementById('pp-search').addEventListener('input', function (e) {
      renderList(e.target.value);
    });

    /* ── Helpers ─────────────────────────────────────────────────────────── */
    function getProp(id) {
      return allProps.find(function (p) { return String(p.id) === String(id); });
    }

    function escHtml(str) {
      return String(str)
        .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    /* ── HTML estático del widget ────────────────────────────────────────── */
    function buildHTML() {
      var sinSeries = secciones.length === 0
        ? '<p class="pp-hint" style="color:#c0392b;">⚠ No hay series de plantilla definidas. Guarda primero la plantilla con las series, luego asigna cada propiedad a su serie.</p>'
        : '';

      return [
        '<style>',
          '.pp-loinc-buscando{color:#999;font-style:italic;font-size:12px;}',
          '.pp-loinc-badge-sug{',
            'display:inline-block;',
            'background:#fff3cd;color:#856404;',
            'border:1px solid #ffc107;border-radius:3px;',
            'font-size:10px;padding:1px 5px;vertical-align:middle;',
            'cursor:default;',
          '}',
        '</style>',
        '<div class="pp-root">',
          '<h2 class="pp-title">Propiedades de la plantilla</h2>',
          sinSeries,
          '<div class="pp-layout">',

            '<div class="pp-col-left">',
              '<p class="pp-col-label">Disponibles</p>',
              '<div class="pp-panel">',
                '<input id="pp-search" class="pp-search" placeholder="Buscar propiedad..." />',
                '<div class="pp-list" id="pp-list"></div>',
              '</div>',
            '</div>',

            '<div class="pp-col-right">',
              '<p class="pp-col-label">Seleccionadas <span id="pp-count"></span></p>',
              '<div class="pp-panel">',
                '<div class="pp-table-wrap">',
                  '<table id="pp-table" style="display:none">',
                    '<thead><tr>',
                      '<th>Propiedad</th>',
                      '<th>Tipo</th>',
                      '<th>Código LOINC</th>',
                      '<th>Serie</th>',
                      '<th>Orden</th>',
                      '<th></th>',
                    '</tr></thead>',
                    '<tbody id="pp-tbody"></tbody>',
                  '</table>',
                '</div>',
                '<div id="pp-empty" class="pp-empty">',
                  'Haz clic en una propiedad de la izquierda para agregarla',
                '</div>',
              '</div>',
              '<p class="pp-hint">* El <strong>Orden</strong> se asigna automáticamente según el orden en que se seleccionan.</p>',
              '<p class="pp-hint">* <strong>LOINC</strong>: haz clic en &#128269; para buscar. Si la plantilla tiene <em>Tipo de muestra</em> y <em>Método</em> definidos, los resultados se pre-filtran por contexto automáticamente.</p>',
              '<p class="pp-hint">* <strong>Serie</strong>: agrupa las propiedades (ej. Serie Roja, Serie Blanca) en el reporte PDF.</p>',
            '</div>',

          '</div>',
        '</div>',
      ].join('');
    }

    /* ── Render inicial ──────────────────────────────────────────────────── */
    renderList('');
    renderTable();

  });

})();
