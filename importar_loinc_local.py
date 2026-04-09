"""
importar_loinc_a_local.py
════════════════════════════════════════════════════════════════
Copia los registros LOINC desde la BD de Django (db.sqlite3)
hacia la BD local de la app de escritorio (Labapp.db).

Ejecutar desde la raíz del proyecto Django:
    python importar_loinc_a_local.py

No requiere levantar Django ni manage.py.
════════════════════════════════════════════════════════════════
"""

import sqlite3
import os
import sys
import time

# ── Rutas ────────────────────────────────────────────────────────
# BD de Django (contiene los 53,524 registros LOINC)
DJANGO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sqlite3")

# BD local de la app de escritorio
try:
    from AplicacionLabV1.models.init_db import DB_PATH as LOCAL_DB
except ImportError:
    LOCAL_DB = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "LabSistemConriquez",
        "Labapp.db",
    )
    print(f"⚠️  init_db no importado. Usando ruta por defecto:\n   {LOCAL_DB}")

# ── Validaciones previas ─────────────────────────────────────────
print("=" * 60)
print("  IMPORTAR LOINC: Django DB → App local")
print("=" * 60)
print(f"\n  Origen : {DJANGO_DB}")
print(f"  Destino: {LOCAL_DB}\n")

if not os.path.exists(DJANGO_DB):
    print(f"❌ No se encontró db.sqlite3 en:\n   {DJANGO_DB}")
    print("   Asegúrate de ejecutar este script desde la raíz del proyecto Django.")
    sys.exit(1)

if not os.path.exists(LOCAL_DB):
    print(f"❌ No se encontró la BD local en:\n   {LOCAL_DB}")
    print("   Inicia la app de escritorio al menos una vez para crearla.")
    sys.exit(1)

# ── Verificar tabla origen ────────────────────────────────────────
print("[1/4] Verificando datos en Django DB...")
src = sqlite3.connect(DJANGO_DB)
src.row_factory = sqlite3.Row
src_cur = src.cursor()

# La tabla en Django se llama según el modelo LoincCode → app_loinccode
# Buscar el nombre real de la tabla
src_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%loinc%'")
tablas_loinc = [r[0] for r in src_cur.fetchall()]
print(f"   Tablas LOINC encontradas en Django DB: {tablas_loinc}")

if not tablas_loinc:
    print("❌ No hay ninguna tabla LOINC en db.sqlite3.")
    src.close()
    sys.exit(1)

# Usar la primera tabla encontrada (normalmente "laboratorio_loinccode" o similar)
tabla_origen = tablas_loinc[0]
print(f"   Usando tabla: {tabla_origen}")

src_cur.execute(f"SELECT COUNT(*) FROM {tabla_origen}")
total_origen = src_cur.fetchone()[0]
print(f"   Registros disponibles: {total_origen:,}")

if total_origen == 0:
    print("❌ La tabla de origen está vacía. Ejecuta loinc_render primero.")
    src.close()
    sys.exit(1)

# Ver columnas disponibles en origen
src_cur.execute(f"PRAGMA table_info({tabla_origen})")
cols_origen = {row["name"]: row for row in src_cur.fetchall()}
print(f"   Columnas en origen: {list(cols_origen.keys())}")

# ── Verificar tabla destino ───────────────────────────────────────
print("\n[2/4] Verificando tabla loinc_code en BD local...")
dst = sqlite3.connect(LOCAL_DB)
dst_cur = dst.cursor()
dst_cur.execute("SELECT COUNT(*) FROM loinc_code")
ya_tenia = dst_cur.fetchone()[0]
print(f"   Registros actuales en loinc_code local: {ya_tenia:,}")

if ya_tenia > 0:
    resp = input(f"\n   ⚠️  Ya hay {ya_tenia:,} registros. ¿Sobrescribir? (s/n): ").strip().lower()
    if resp != "s":
        print("   Cancelado.")
        src.close()
        dst.close()
        sys.exit(0)
    print("   Limpiando tabla local...")
    dst_cur.execute("DELETE FROM loinc_code")
    dst.commit()

# ── Mapeo de columnas origen → destino ───────────────────────────
# La tabla Django puede tener nombres distintos (id, loinc_num, shortname, etc.)
# Buscamos los nombres correctos de forma flexible.

def buscar_col(cols: dict, *candidatos) -> str | None:
    """Devuelve el primer candidato que exista como columna."""
    for c in candidatos:
        if c in cols:
            return c
    return None

col_loinc_num = buscar_col(cols_origen, "loinc_num", "LOINC_NUM", "loincnum")
col_shortname = buscar_col(cols_origen, "shortname",  "SHORTNAME",  "short_name")
col_component = buscar_col(cols_origen, "component",  "COMPONENT")
col_property  = buscar_col(cols_origen, "property",   "PROPERTY",   "prop")
col_system    = buscar_col(cols_origen, "system",     "SYSTEM")
col_scale_typ = buscar_col(cols_origen, "scale_typ",  "SCALE_TYP",  "scale")

print(f"\n   Mapeo de columnas detectado:")
print(f"     loinc_num → {col_loinc_num}")
print(f"     shortname → {col_shortname}")
print(f"     component → {col_component}")
print(f"     property  → {col_property}")
print(f"     system    → {col_system}")
print(f"     scale_typ → {col_scale_typ}")

if not col_loinc_num:
    print("\n❌ No se encontró la columna loinc_num en la tabla origen.")
    print(f"   Columnas disponibles: {list(cols_origen.keys())}")
    src.close()
    dst.close()
    sys.exit(1)

# ── Construcción dinámica del SELECT ─────────────────────────────
def col_o_null(col):
    return col if col else "NULL"

select_cols = ", ".join([
    col_o_null(col_loinc_num),
    col_o_null(col_shortname),
    col_o_null(col_component),
    col_o_null(col_property),
    col_o_null(col_system),
    col_o_null(col_scale_typ),
])

query_origen = f"SELECT {select_cols} FROM {tabla_origen}"

# ── Copia en bloques ──────────────────────────────────────────────
print("\n[3/4] Copiando registros...")
BLOQUE = 5000
insertados  = 0
rechazados  = 0
inicio      = time.time()

src_cur.execute(query_origen)

while True:
    filas = src_cur.fetchmany(BLOQUE)
    if not filas:
        break

    registros = []
    for fila in filas:
        loinc_num, shortname, component, property_, system, scale_typ = fila
        if not loinc_num:          # loinc_num es obligatorio
            rechazados += 1
            continue
        registros.append((
            str(loinc_num).strip(),
            str(shortname).strip()  if shortname  else None,
            str(component).strip()  if component  else None,
            str(property_).strip()  if property_  else None,
            str(system).strip()     if system     else None,
            str(scale_typ).strip()  if scale_typ  else None,
        ))

    if registros:
        dst_cur.executemany("""
            INSERT OR IGNORE INTO loinc_code
                (loinc_num, shortname, component, property, system, scale_typ)
            VALUES (?, ?, ?, ?, ?, ?)
        """, registros)
        dst.commit()
        insertados += len(registros)
        rechazados += (len(filas) - len(registros))
        elapsed = time.time() - inicio
        print(f"   Insertados: {insertados:,} / {total_origen:,}  "
              f"({insertados/total_origen*100:.1f}%)  —  {elapsed:.1f}s", end="\r")

print()  # salto de línea tras el progreso

# ── Verificación final ────────────────────────────────────────────
print("\n[4/4] Verificando resultado...")
dst_cur.execute("SELECT COUNT(*) FROM loinc_code")
total_final = dst_cur.fetchone()[0]

# Prueba de búsqueda rápida
dst_cur.execute("""
    SELECT loinc_num, shortname, component
    FROM loinc_code
    WHERE LOWER(component) LIKE '%glucose%'
    LIMIT 3
""")
prueba = dst_cur.fetchall()

src.close()
dst.close()

print(f"   Registros en loinc_code local ahora: {total_final:,}")
print(f"   Insertados en esta ejecución      : {insertados:,}")
print(f"   Rechazados (sin loinc_num)         : {rechazados:,}")
print(f"   Tiempo total                       : {time.time() - inicio:.1f}s")

print("\n   Prueba de búsqueda 'glucose':")
if prueba:
    for r in prueba:
        print(f"     {r[0]}  —  {r[1] or r[2]}")
else:
    print("     (sin resultados — revisa el mapeo de columnas)")

print("\n" + "=" * 60)
if total_final > 0 and prueba:
    print("  ✅ ¡LISTO! La app de escritorio ya puede buscar códigos LOINC.")
    print("     Abre la app, crea una propiedad, escribe el nombre y")
    print("     presiona Tab (o haz clic en otro campo) para ver sugerencias.")
elif total_final > 0:
    print("  ⚠️  Datos copiados pero la búsqueda de 'glucose' no devolvió")
    print("     resultados. Revisa el mapeo de columnas arriba.")
else:
    print("  ❌ No se insertaron registros. Revisa los errores anteriores.")
print("=" * 60)
