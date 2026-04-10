import os
import sqlite3
import sys
from datetime import datetime

# ===================================================================
# DEFINICIÓN DE RUTA PERMANENTE (APPDATA)
# ===================================================================

APP_NAME    = "LabSistemConriquez"
DB_FILENAME = "Labapp.db"


def obtener_ruta_db_permanente():
    """
    Obtiene la ruta a la carpeta de datos de la aplicación
    (AppData en Windows) y la devuelve.
    """
    if sys.platform == "win32":
        db_dir = os.path.join(os.environ.get('APPDATA'), APP_NAME)
    else:
        db_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)

    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, DB_FILENAME)


DB_PATH = obtener_ruta_db_permanente()


# ===================================================================
# FUNCIÓN PARA ASSETS (Imágenes, Fuentes)
# ===================================================================
def resource_path(relative_path):
    """
    Obtiene la ruta absoluta de un recurso (asset),
    funciona en desarrollo y en .exe.
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path   = os.path.abspath(os.path.join(current_dir, "..", ".."))

    return os.path.join(base_path, relative_path)


# ===================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# ===================================================================
def inicializar_bd():
    if not os.path.exists(DB_PATH):
        print(f"⌛ Creando nueva base de datos en {DB_PATH}...")
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Activar FK enforcement en SQLite
        cursor.execute("PRAGMA foreign_keys = ON")

        # ------------------------------------------------------------------
        # LABORATORIO
        # Espejo de: class Laboratorio(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE laboratorio (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id                       INTEGER,
            sincronizado                    INTEGER DEFAULT 1,
            fecha_modificacion              TEXT,
            nombre_laboratorio              TEXT NOT NULL,
            ciudad                          TEXT,
            estado                          TEXT,
            codigo_postal                   TEXT,
            pais                            TEXT,
            -- Cloudinary: se almacena la URL pública devuelta por la API
            logo                            TEXT,
            -- FK: responsable_sanitario_principal → usuario.id
            responsable_sanitario_id        INTEGER,
            FOREIGN KEY (responsable_sanitario_id) REFERENCES usuario(id) ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # USUARIO
        # Espejo de: class Usuario(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE usuario (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id               INTEGER,
            sincronizado            INTEGER DEFAULT 1,
            fecha_modificacion      TEXT,
            nombre                  TEXT NOT NULL,
            correo_electronico      TEXT UNIQUE NOT NULL,
            num_telefono            TEXT,
            -- ROLES: NORMAL | TECNICO | ADMIN
            rol                     TEXT DEFAULT 'NORMAL',
            is_active               INTEGER DEFAULT 1,
            password                TEXT,
            -- Campos profesionales
            puesto                  TEXT,
            titulo_abreviado        TEXT,
            cedula_profesional      TEXT,
            cedula_especialidad     TEXT,
            registro_ssg            TEXT,
            universidad_egreso      TEXT,
            -- Cloudinary: se almacena la URL pública
            firma_digital           TEXT
        )
        """)

        # ------------------------------------------------------------------
        # USUARIO ↔ LABORATORIO  (ManyToMany de Django: Usuario.laboratorios)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE usuario_laboratorio (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id          INTEGER NOT NULL,
            laboratorio_id      INTEGER NOT NULL,
            UNIQUE (usuario_id, laboratorio_id),
            FOREIGN KEY (usuario_id)     REFERENCES usuario(id)     ON DELETE CASCADE,
            FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # PACIENTE
        # Espejo de: class Paciente(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE paciente (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id               INTEGER,
            sincronizado            INTEGER DEFAULT 1,
            fecha_modificacion      TEXT,
            laboratorio_id          INTEGER NOT NULL,
            nombre                  TEXT NOT NULL,
            apellido_paterno        TEXT NOT NULL,
            apellido_materno        TEXT,
            -- ISO 8601: YYYY-MM-DD
            fecha_nacimiento        TEXT,
            -- MASCULINO | FEMENINO
            sexo                    TEXT,
            telefono                TEXT,
            correo_electronico      TEXT,
            FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # LOINC CODE
        # Espejo de: class LoincCode(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE loinc_code (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            loinc_num   TEXT UNIQUE,
            shortname   TEXT,
            component   TEXT,
            property    TEXT,
            system      TEXT,
            scale_typ   TEXT
        )
        """)

        # ------------------------------------------------------------------
        # PROPIEDAD
        # Espejo de: class Propiedad(models.Model)
        # ⚠️ NOTA: Django no tiene loinc_code en Propiedad directamente;
        #    el LOINC por contexto de plantilla se maneja en PlantillaPropiedad.
        #    Se conserva aquí como campo opcional para compatibilidad local.
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE propiedad (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id               INTEGER,
            sincronizado            INTEGER DEFAULT 1,
            fecha_modificacion      TEXT,
            nombre_propiedad        TEXT UNIQUE NOT NULL,
            -- CUANTITATIVO | CUALITATIVO
            tipo                    TEXT DEFAULT 'CUANTITATIVO',
            -- Solo para CUANTITATIVO
            unidad                  TEXT,
            -- Solo para CUALITATIVO: opciones separadas por coma. Ej: "POSITIVO,NEGATIVO"
            opciones_cualitativas   TEXT
        )
        """)

        # ------------------------------------------------------------------
        # INTERVALO REFERENCIA
        # Espejo de: class IntervaloReferencia(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE intervalo_referencia (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id           INTEGER,
            sincronizado        INTEGER DEFAULT 1,
            fecha_modificacion  TEXT,
            propiedad_id        INTEGER NOT NULL,
            -- MASCULINO | FEMENINO | AMBOS
            sexo                TEXT DEFAULT 'AMBOS',
            -- Rango de edad en meses (null = sin límite)
            edad_min_meses      INTEGER,
            edad_max_meses      INTEGER,
            valor_min           REAL,
            valor_max           REAL,
            UNIQUE (propiedad_id, edad_min_meses, edad_max_meses, sexo),
            FOREIGN KEY (propiedad_id) REFERENCES propiedad(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # PLANTILLA
        # Espejo de: class Plantilla(models.Model)
        # ⚠️ NUEVO: loinc_code_id (FK opcional para interoperabilidad HL7/FHIR)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE plantilla (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id                   INTEGER,
            sincronizado                INTEGER DEFAULT 1,
            fecha_modificacion          TEXT,
            titulo                      TEXT UNIQUE NOT NULL,
            -- RESULTADOS | IMAGENES_RESULTADOS
            tipo_formato                TEXT DEFAULT 'RESULTADOS',
            texto_justificado_default   TEXT,
            -- ⚠️ NUEVO: LOINC del panel completo (ej. 58410-2 Biometría Hemática)
            loinc_code_id               INTEGER,
            FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id) ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # SECCIÓN DE PLANTILLA
        # Espejo de: class SeccionPlantilla(models.Model)
        # ⚠️ TABLA NUEVA: agrupa propiedades bajo un subtítulo en el reporte
        #    (ej. FÓRMULA ROJA, FÓRMULA BLANCA). Opcional por plantilla.
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE seccion_plantilla (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id    INTEGER NOT NULL,
            nombre          TEXT NOT NULL,
            -- Orden de aparición de la sección dentro de la plantilla
            orden           INTEGER DEFAULT 0,
            UNIQUE (plantilla_id, nombre),
            FOREIGN KEY (plantilla_id) REFERENCES plantilla(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # PLANTILLA ↔ PROPIEDAD  (ManyToMany de Django: Plantilla.propiedades)
        # Espejo de: class PlantillaPropiedad(models.Model)
        # ⚠️ CAMPOS NUEVOS vs versión anterior:
        #    - loinc_code_id : LOINC específico para esta propiedad en esta plantilla
        #    - seccion_id    : FK a seccion_plantilla (agrupación visual)
        #    - orden         : posición dentro de la sección
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE plantilla_propiedad (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id    INTEGER NOT NULL,
            propiedad_id    INTEGER NOT NULL,
            -- LOINC correcto para esta propiedad en el contexto de la plantilla
            loinc_code_id   INTEGER,
            -- Sección visual en el reporte (opcional)
            seccion_id      INTEGER,
            -- Orden dentro de la sección (o de la plantilla si no hay sección)
            orden           INTEGER DEFAULT 0,
            UNIQUE (plantilla_id, propiedad_id),
            FOREIGN KEY (plantilla_id)  REFERENCES plantilla(id)         ON DELETE CASCADE,
            FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id)         ON DELETE CASCADE,
            FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id)        ON DELETE SET NULL,
            FOREIGN KEY (seccion_id)    REFERENCES seccion_plantilla(id) ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # ANÁLISIS
        # Espejo de: class Analisis(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE analisis (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id           INTEGER,
            sincronizado        INTEGER DEFAULT 1,
            fecha_modificacion  TEXT,
            paciente_id         INTEGER NOT NULL,
            plantilla_id        INTEGER,
            creado_por_id       INTEGER,
            -- PENDIENTE | COMPLETADO | CANCELADO
            status              TEXT DEFAULT 'PENDIENTE',
            -- auto_now_add en Django → se asigna al insertar
            fecha_analisis      TEXT,
            fecha_muestra       TEXT,
            hora_toma           TEXT,
            hora_impresion      TEXT,
            tipo_muestra        TEXT,
            metodo              TEXT,
            -- Cloudinary: se almacena la URL pública
            imagen_resultado1   TEXT,
            imagen_resultado2   TEXT,
            FOREIGN KEY (paciente_id)   REFERENCES paciente(id)   ON DELETE CASCADE,
            FOREIGN KEY (plantilla_id)  REFERENCES plantilla(id)  ON DELETE RESTRICT,
            FOREIGN KEY (creado_por_id) REFERENCES usuario(id)    ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # ANÁLISIS ↔ PROPIEDAD EXTRA  (ManyToMany: Analisis.propiedades_extra)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE analisis_propiedad_extra (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            analisis_id     INTEGER NOT NULL,
            propiedad_id    INTEGER NOT NULL,
            UNIQUE (analisis_id, propiedad_id),
            FOREIGN KEY (analisis_id)   REFERENCES analisis(id)  ON DELETE CASCADE,
            FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # ANÁLISIS ↔ PROPIEDAD EXCLUIDA  (ManyToMany: Analisis.propiedades_excluidas)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE analisis_propiedad_excluida (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            analisis_id     INTEGER NOT NULL,
            propiedad_id    INTEGER NOT NULL,
            UNIQUE (analisis_id, propiedad_id),
            FOREIGN KEY (analisis_id)   REFERENCES analisis(id)  ON DELETE CASCADE,
            FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # RESULTADO ANÁLISIS
        # Espejo de: class ResultadoAnalisis(models.Model)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE resultado_analisis (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id           INTEGER,
            sincronizado        INTEGER DEFAULT 1,
            fecha_modificacion  TEXT,
            analisis_id         INTEGER NOT NULL,
            propiedad_id        INTEGER NOT NULL,
            loinc_code_id       INTEGER,
            -- Snapshot del nombre al momento de crear (histórico)
            nombre_propiedad    TEXT,
            valor               TEXT,
            unidad              TEXT,
            -- Campos extra locales para imágenes embebidas (no en Django)
            valor_blob1         BLOB,
            valor_blob2         BLOB,
            -- Evita duplicar la misma propiedad en el mismo análisis
            UNIQUE (analisis_id, propiedad_id),
            FOREIGN KEY (analisis_id)   REFERENCES analisis(id)   ON DELETE CASCADE,
            FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id)  ON DELETE RESTRICT,
            FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id) ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # REPORTE
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE reporte (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id           INTEGER,
            sincronizado        INTEGER DEFAULT 1,
            fecha_modificacion  TEXT,
            analisis_id         INTEGER NOT NULL,
            generado_por        INTEGER,
            fecha_generacion    TEXT,
            FOREIGN KEY (analisis_id) REFERENCES analisis(id) ON DELETE CASCADE,
            FOREIGN KEY (generado_por) REFERENCES usuario(id) ON DELETE SET NULL
        )
        """)

        # ------------------------------------------------------------------
        # PAGO  (tabla local, no tiene espejo en models.py de Django)
        # ------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE pago (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id           INTEGER,
            sincronizado        INTEGER DEFAULT 1,
            fecha_modificacion  TEXT,
            usuario_id          INTEGER NOT NULL,
            fecha_pago          TEXT,
            fecha_vencimiento   TEXT,
            estado              TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuario(id) ON DELETE CASCADE
        )
        """)

        # ------------------------------------------------------------------
        # DATOS INICIALES
        # ------------------------------------------------------------------
        cursor.execute("""
        INSERT INTO laboratorio (nombre_laboratorio, ciudad, estado, codigo_postal, pais)
        VALUES (?, ?, ?, ?, ?)
        """, ("ICE Conriquez", "Guanajuato", "Guanajuato", "36000", "México"))
        laboratorio_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO usuario (nombre, correo_electronico, password, rol)
        VALUES (?, ?, ?, ?)
        """, ("Administrador", "admin@admin.com", "admin123", "ADMIN"))
        usuario_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO usuario_laboratorio (usuario_id, laboratorio_id)
        VALUES (?, ?)
        """, (usuario_id, laboratorio_id))

        conn.commit()
        conn.close()
        print(f"✅ Base de datos '{DB_FILENAME}' creada en {DB_PATH}.")
    else:
        print(f"📂 Base de datos existente detectada en {DB_PATH}.")
        _migrar_si_necesario()


# ===================================================================
# MIGRACIÓN AUTOMÁTICA (para instancias existentes)
# Agrega columnas/tablas nuevas sin destruir datos previos.
# ===================================================================
def _migrar_si_necesario():
    """
    Añade columnas/tablas que no existen en la BD local antigua
    para que coincidan con el schema actualizado.
    Seguro de ejecutar múltiples veces (usa IF NOT EXISTS / try-except).
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # TABLAS PREVIAS REQUERIDAS POR FK
    # Deben existir ANTES del loop de ALTER TABLE para que las FK
    # que referencian a ellas no produzcan errores en SQLite.
    # ------------------------------------------------------------------

    # LOINC CODE (puede no existir en BDs antiguas)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS loinc_code (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        loinc_num   TEXT UNIQUE,
        shortname   TEXT,
        component   TEXT,
        property    TEXT,
        system      TEXT,
        scale_typ   TEXT
    )
    """)

    # SECCION PLANTILLA — debe crearse antes de agregar seccion_id a
    # plantilla_propiedad, ya que SQLite valida la referencia en DDL.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seccion_plantilla (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        plantilla_id    INTEGER NOT NULL,
        nombre          TEXT NOT NULL,
        orden           INTEGER DEFAULT 0,
        UNIQUE (plantilla_id, nombre),
        FOREIGN KEY (plantilla_id) REFERENCES plantilla(id) ON DELETE CASCADE
    )
    """)

    # ------------------------------------------------------------------
    # COLUMNAS NUEVAS
    # ------------------------------------------------------------------
    migraciones_columnas = [
        # --- usuario ---
        ("usuario",             "remote_id",                "INTEGER"),
        ("usuario",             "sincronizado",             "INTEGER DEFAULT 1"),
        ("usuario",             "fecha_modificacion",       "TEXT"),
        ("usuario",             "rol",                      "TEXT DEFAULT 'NORMAL'"),
        ("usuario",             "puesto",                   "TEXT"),
        ("usuario",             "titulo_abreviado",         "TEXT"),
        ("usuario",             "cedula_profesional",       "TEXT"),
        ("usuario",             "cedula_especialidad",      "TEXT"),
        ("usuario",             "registro_ssg",             "TEXT"),
        ("usuario",             "universidad_egreso",       "TEXT"),
        # firma_digital ahora es TEXT (URL Cloudinary) en lugar de BLOB
        ("usuario",             "firma_digital",            "TEXT"),

        # --- laboratorio ---
        ("laboratorio",         "remote_id",                "INTEGER"),
        ("laboratorio",         "sincronizado",             "INTEGER DEFAULT 1"),
        ("laboratorio",         "fecha_modificacion",       "TEXT"),
        ("laboratorio",         "responsable_sanitario_id", "INTEGER"),
        # logo ahora es TEXT (URL Cloudinary) en lugar de BLOB
        ("laboratorio",         "logo",                     "TEXT"),

        # --- paciente ---
        ("paciente",            "apellido_paterno",         "TEXT"),
        ("paciente",            "apellido_materno",         "TEXT"),
        ("paciente",            "fecha_nacimiento",         "TEXT"),

        # --- plantilla ---
        # ⚠️ NUEVO: LOINC del panel completo
        ("plantilla",           "loinc_code_id",            "INTEGER"),

        # --- plantilla_propiedad ---
        # ⚠️ NUEVOS: campos que la tabla M2M no tenía antes
        ("plantilla_propiedad", "loinc_code_id",            "INTEGER"),
        ("plantilla_propiedad", "seccion_id",               "INTEGER"),
        ("plantilla_propiedad", "orden",                    "INTEGER DEFAULT 0"),

        # --- analisis ---
        ("analisis",            "status",                   "TEXT DEFAULT 'PENDIENTE'"),
        ("analisis",            "creado_por_id",            "INTEGER"),
        ("analisis",            "tipo_muestra",             "TEXT"),
        ("analisis",            "metodo",                   "TEXT"),
        # imagen_resultado ahora es TEXT (URL Cloudinary) en lugar de BLOB
        ("analisis",            "imagen_resultado1",        "TEXT"),
        ("analisis",            "imagen_resultado2",        "TEXT"),

        # --- propiedad ---
        ("propiedad",           "remote_id",                "INTEGER"),
        ("propiedad",           "sincronizado",             "INTEGER DEFAULT 1"),
        ("propiedad",           "fecha_modificacion",       "TEXT"),
        ("propiedad",           "tipo",                     "TEXT DEFAULT 'CUANTITATIVO'"),
        ("propiedad",           "opciones_cualitativas",    "TEXT"),

        # --- resultado_analisis ---
        ("resultado_analisis",  "propiedad_id",             "INTEGER"),
        ("resultado_analisis",  "valor_blob1",              "BLOB"),
        ("resultado_analisis",  "valor_blob2",              "BLOB"),

        # --- intervalo_referencia ---
        ("intervalo_referencia", "remote_id",               "INTEGER"),
        ("intervalo_referencia", "sincronizado",            "INTEGER DEFAULT 1"),
        ("intervalo_referencia", "fecha_modificacion",      "TEXT"),
    ]

    for tabla, columna, tipo in migraciones_columnas:
        try:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            print(f"  ✅ Migración columna: {tabla}.{columna} agregado.")
        except sqlite3.OperationalError:
            pass  # La columna ya existe, todo bien

    # ------------------------------------------------------------------
    # TABLAS NUEVAS  (si no existen)
    # loinc_code y seccion_plantilla ya se crearon arriba para que el
    # ALTER TABLE de las columnas FK no falle en BDs antiguas.
    # ------------------------------------------------------------------

    # PROPIEDAD (entidad independiente)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS propiedad (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        remote_id               INTEGER,
        sincronizado            INTEGER DEFAULT 1,
        fecha_modificacion      TEXT,
        nombre_propiedad        TEXT UNIQUE NOT NULL,
        tipo                    TEXT DEFAULT 'CUANTITATIVO',
        unidad                  TEXT,
        opciones_cualitativas   TEXT
    )
    """)

    # M2M Plantilla ↔ Propiedad (con campos extendidos)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plantilla_propiedad (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        plantilla_id    INTEGER NOT NULL,
        propiedad_id    INTEGER NOT NULL,
        loinc_code_id   INTEGER,
        seccion_id      INTEGER,
        orden           INTEGER DEFAULT 0,
        UNIQUE (plantilla_id, propiedad_id),
        FOREIGN KEY (plantilla_id)  REFERENCES plantilla(id)         ON DELETE CASCADE,
        FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id)         ON DELETE CASCADE,
        FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id)        ON DELETE SET NULL,
        FOREIGN KEY (seccion_id)    REFERENCES seccion_plantilla(id) ON DELETE SET NULL
    )
    """)

    # M2M Analisis.propiedades_extra
    cur.execute("""
    CREATE TABLE IF NOT EXISTS analisis_propiedad_extra (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        analisis_id     INTEGER NOT NULL,
        propiedad_id    INTEGER NOT NULL,
        UNIQUE (analisis_id, propiedad_id),
        FOREIGN KEY (analisis_id)   REFERENCES analisis(id)  ON DELETE CASCADE,
        FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id) ON DELETE CASCADE
    )
    """)

    # M2M Analisis.propiedades_excluidas
    cur.execute("""
    CREATE TABLE IF NOT EXISTS analisis_propiedad_excluida (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        analisis_id     INTEGER NOT NULL,
        propiedad_id    INTEGER NOT NULL,
        UNIQUE (analisis_id, propiedad_id),
        FOREIGN KEY (analisis_id)   REFERENCES analisis(id)  ON DELETE CASCADE,
        FOREIGN KEY (propiedad_id)  REFERENCES propiedad(id) ON DELETE CASCADE
    )
    """)

    print("  ✅ Tablas nuevas verificadas/creadas.")

    # ------------------------------------------------------------------
    # MIGRACIÓN DE DATOS: propiedad_plantilla → propiedad + plantilla_propiedad
    #
    # Si la BD antigua tiene datos en "propiedad_plantilla", los migramos
    # a la nueva estructura normalizada. Solo se ejecuta si la tabla vieja
    # existe y la nueva "propiedad" está vacía (primera migración).
    # ------------------------------------------------------------------
    tablas_existentes = {
        row[0] for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    if "propiedad_plantilla" in tablas_existentes:
        count_nueva = cur.execute("SELECT COUNT(*) FROM propiedad").fetchone()[0]
        if count_nueva == 0:
            print("  ⏳ Migrando datos de propiedad_plantilla → propiedad + plantilla_propiedad...")
            filas = cur.execute("""
                SELECT id, remote_id, plantilla_id, nombre_propiedad,
                       loinc_code_id, tipo, unidad, opciones_cualitativas,
                       sincronizado, fecha_modificacion
                FROM propiedad_plantilla
            """).fetchall()

            for fila in filas:
                (old_id, remote_id, plantilla_id, nombre_propiedad,
                 loinc_code_id, tipo, unidad, opciones_cualitativas,
                 sincronizado, fecha_modificacion) = fila

                cur.execute("""
                    INSERT OR IGNORE INTO propiedad
                        (remote_id, nombre_propiedad, tipo,
                         unidad, opciones_cualitativas, sincronizado, fecha_modificacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (remote_id, nombre_propiedad, tipo or 'CUANTITATIVO',
                      unidad, opciones_cualitativas, sincronizado or 1, fecha_modificacion))

                propiedad_id = cur.execute(
                    "SELECT id FROM propiedad WHERE nombre_propiedad = ?",
                    (nombre_propiedad,)
                ).fetchone()[0]

                cur.execute("""
                    INSERT OR IGNORE INTO plantilla_propiedad (plantilla_id, propiedad_id, loinc_code_id)
                    VALUES (?, ?, ?)
                """, (plantilla_id, propiedad_id, loinc_code_id))

                cur.execute("""
                    UPDATE resultado_analisis
                    SET propiedad_id = ?
                    WHERE nombre_propiedad = ? AND propiedad_id IS NULL
                """, (propiedad_id, nombre_propiedad))

            print(f"    Migrados {len(filas)} registros de propiedad_plantilla.")
        else:
            print("    Tabla 'propiedad' ya tiene datos; migración de propiedad_plantilla omitida.")

    conn.commit()
    conn.close()
    print("✅ Migraciones locales completadas.")


if __name__ == "__main__":
    inicializar_bd()