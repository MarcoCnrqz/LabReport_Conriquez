/**
 * plantilla_propiedades_picker.js
 * Coloca en: <tu_app>/static/admin/js/plantilla_propiedades_picker.js
 *
 * Mejoras v2:
 *  - Orden automático al ir seleccionando propiedades
 *  - Buscador LOINC como dropdown inline (sin modal flotante)
 *  - Columna "Serie" para asignar SeccionPlantilla a cada propiedad
 *  - Inputs ocultos: pp_picker_ids, pp_picker_loinc_ids,
 *                    pp_picker_ordenes, pp_picker_seccion_ids
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

    var allProps   = propsEl     ? JSON.parse(propsEl.textContent)     : [];
    var secciones  = seccionesEl ? JSON.parse(seccionesEl.textContent) : [];

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
        propId:       String(e.propId),
        nombre:       e.nombre,
        loincId:      String(e.loincId      || ''),
        loincNum:     String(e.loincNum     || ''),
        loincDesc:    String(e.loincDesc    || ''),
        orden:        parseInt(e.orden, 10) || 1,
        seccionId:    String(e.seccionId    || ''),
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
    var hiddenIds       = addHidden('pp_picker_ids');
    var hiddenLoincIds  = addHidden('pp_picker_loinc_ids');
    var hiddenOrdenes   = addHidden('pp_picker_ordenes');
    var hiddenSeccionIds = addHidden('pp_picker_seccion_ids');

    function addHidden(name) {
      var inp  = document.createElement('input');
      inp.type = 'hidden';
      inp.name = name;
      container.appendChild(inp);
      return inp;
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

        /* Celda LOINC */
        var loincDisplay = s.loincNum
          ? escHtml(s.loincNum) + (s.loincDesc
              ? ' <span class="pp-loinc-desc">— ' + escHtml(s.loincDesc) + '</span>'
              : '')
          : '<span class="pp-loinc-empty">Sin asignar</span>';

        /* Celda Serie (sección) — dropdown select */
        var seccionOptions = '<option value="">— Sin serie —</option>';
        secciones.forEach(function (sec) {
          var sel = (String(sec.id) === String(s.seccionId)) ? ' selected' : '';
          seccionOptions += '<option value="' + sec.id + '"' + sel + '>' + escHtml(sec.nombre) + '</option>';
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
          /* LOINC — valor + botón buscador inline */
          '<td class="pp-td-loinc">' +
            '<div class="pp-loinc-wrap">' +
              '<div class="pp-loinc-display" id="pp-lv-' + idx + '">' + loincDisplay + '</div>' +
              '<div class="pp-loinc-search-wrap" id="pp-ls-wrap-' + idx + '">' +
                '<input type="text"' +
                  ' id="pp-ls-' + idx + '"' +
                  ' class="pp-loinc-search-inp"' +
                  ' placeholder="Buscar LOINC..."' +
                  ' autocomplete="off"' +
                  ' data-idx="' + idx + '" />' +
                '<div class="pp-loinc-dropdown" id="pp-lsd-' + idx + '">' +
                  '<div class="pp-lm-hint">Escribe para buscar…</div>' +
                '</div>' +
              '</div>' +
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
          /* Orden (solo lectura — se asigna automáticamente) */
          '<td class="pp-td-orden">' +
            '<span class="pp-orden-num">' + s.orden + '</span>' +
          '</td>' +
          /* Quitar */
          '<td>' +
            '<button type="button" class="pp-remove" data-idx="' + idx + '" title="Quitar propiedad">&#x2715;</button>' +
          '</td>';

        tbody.appendChild(tr);
      });

      /* ── Eventos: buscador LOINC inline ────────────────────────────────── */
      tbody.querySelectorAll('.pp-loinc-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          var idx = parseInt(btn.dataset.idx, 10);
          toggleLoincSearch(idx);
        });
      });

      tbody.querySelectorAll('.pp-loinc-search-inp').forEach(function (inp) {
        var debounce = null;
        inp.addEventListener('input', function () {
          var q = inp.value.trim();
          var idx = parseInt(inp.dataset.idx, 10);
          var dropdown = document.getElementById('pp-lsd-' + idx);
          if (!dropdown) return;
          if (q.length < 2) {
            dropdown.innerHTML = '<div class="pp-lm-hint">Escribe al menos 2 caracteres…</div>';
            return;
          }
          clearTimeout(debounce);
          debounce = setTimeout(function () { doLoincSearch(q, idx); }, 280);
        });
        inp.addEventListener('keydown', function (e) {
          if (e.key === 'Escape') {
            var idx = parseInt(inp.dataset.idx, 10);
            hideLoincSearch(idx);
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
          renderTable();
        });
      });

      /* ── Eventos: cambiar serie ─────────────────────────────────────────── */
      tbody.querySelectorAll('.pp-sel-serie').forEach(function (sel) {
        sel.addEventListener('change', function () {
          var i = parseInt(sel.dataset.idx, 10);
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
          selected.splice(i, 1);
          /* Reasignar orden automático */
          recalcOrden();
          renderList(document.getElementById('pp-search').value);
          renderTable();
        });
      });

      syncHiddens();
    }

    /* ── Toggle buscador LOINC inline ───────────────────────────────────── */
    function toggleLoincSearch(idx) {
      var wrap = document.getElementById('pp-ls-wrap-' + idx);
      if (!wrap) return;
      var isOpen = wrap.classList.contains('pp-loinc-search-open');

      /* Cerrar todos los demás */
      document.querySelectorAll('.pp-loinc-search-wrap').forEach(function (w) {
        w.classList.remove('pp-loinc-search-open');
      });

      if (!isOpen) {
        wrap.classList.add('pp-loinc-search-open');
        var inp = document.getElementById('pp-ls-' + idx);
        if (inp) { inp.value = ''; inp.focus(); }
        var drop = document.getElementById('pp-lsd-' + idx);
        if (drop) drop.innerHTML = '<div class="pp-lm-hint">Escribe para buscar…</div>';
      }
    }

    function hideLoincSearch(idx) {
      var wrap = document.getElementById('pp-ls-wrap-' + idx);
      if (wrap) wrap.classList.remove('pp-loinc-search-open');
    }

    /* Cerrar buscador LOINC al hacer clic fuera */
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.pp-loinc-search-wrap') && !e.target.closest('.pp-loinc-btn')) {
        document.querySelectorAll('.pp-loinc-search-wrap').forEach(function (w) {
          w.classList.remove('pp-loinc-search-open');
        });
      }
    });

    /* ── Búsqueda LOINC via AJAX ─────────────────────────────────────────── */
    function doLoincSearch(q, idx) {
      var dropdown = document.getElementById('pp-lsd-' + idx);
      if (!dropdown) return;
      dropdown.innerHTML = '<div class="pp-lm-hint">Buscando…</div>';

      var url = '/admin/LabApp/plantilla/loinc-buscar/?q=' + encodeURIComponent(q);
      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!dropdown) return;
          if (!data.results || data.results.length === 0) {
            dropdown.innerHTML = '<div class="pp-lm-hint">Sin resultados para "' + escHtml(q) + '"</div>';
            return;
          }
          dropdown.innerHTML = '';
          data.results.forEach(function (lc) {
            var row = document.createElement('div');
            row.className = 'pp-lm-row';
            row.innerHTML =
              '<span class="pp-lm-num">'  + escHtml(lc.loinc_num) + '</span>' +
              '<span class="pp-lm-name">' + escHtml(lc.shortname || lc.component || '') + '</span>' +
              (lc.system ? '<span class="pp-lm-sys">' + escHtml(lc.system) + '</span>' : '');
            row.addEventListener('click', function () {
              selected[idx].loincId   = String(lc.id);
              selected[idx].loincNum  = lc.loinc_num;
              selected[idx].loincDesc = lc.shortname || lc.component || '';
              hideLoincSearch(idx);
              renderTable();
            });
            dropdown.appendChild(row);
          });
        })
        .catch(function () {
          if (dropdown)
            dropdown.innerHTML = '<div class="pp-lm-hint" style="color:#c0392b;">Error al buscar. Intenta de nuevo.</div>';
        });
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
      } else {
        var p = getProp(id);
        selected.push({
          propId:        id,
          nombre:        p ? p.nombre : ('Propiedad #' + id),
          loincId:       '',
          loincNum:      '',
          loincDesc:     '',
          orden:         selected.length + 1,  /* automático */
          seccionId:     '',
          seccionNombre: '',
        });
      }
      recalcOrden();
      renderList(document.getElementById('pp-search').value);
      renderTable();
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
      /* Aviso si no hay series definidas aún */
      var sinSeries = secciones.length === 0
        ? '<p class="pp-hint" style="color:#c0392b;">⚠ No hay series de plantilla definidas. Guarda primero la plantilla con las series, luego asigna cada propiedad a su serie.</p>'
        : '';

      return [
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
              '<p class="pp-hint">* <strong>LOINC</strong>: haz clic en &#128269; y escribe para buscar en la base de datos.</p>',
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
