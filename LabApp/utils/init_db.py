import os
import sqlite3
import sys
from datetime import datetime 

# ===================================================================
# DEFINICIÓN DE RUTA PERMANENTE (APPDATA)
# ===================================================================

APP_NAME = "LabSistemConriquez" 
DB_FILENAME = "Labapp.db"

def obtener_ruta_db_permanente():
    """
    Obtiene la ruta a la carpeta de datos de la aplicación
    (AppData en Windows) y la devuelve.
    """
    if sys.platform == "win32":
        # Ruta estándar en Windows: C:\Users\<usuario>\AppData\Roaming\LabSistemConriquez
        db_dir = os.path.join(os.environ.get('APPDATA'), APP_NAME)
    else:
        # Ruta para macOS o Linux (por si acaso)
        db_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
    
    # Crea la carpeta si no existe
    os.makedirs(db_dir, exist_ok=True)
    
    # Esta es la RUTA FINAL Y PERMANENTE de tu base de datos
    return os.path.join(db_dir, DB_FILENAME)

# --- ¡ESTA ES LA RUTA CORRECTA PARA LA BD! ---
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
        # Estamos en el .exe. La base es el directorio temporal _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Estamos en desarrollo (ejecutando .py).
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    return os.path.join(base_path, relative_path)

# ===================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS (CORREGIDA CON CAMPOS DE SYNC)
# ===================================================================
def inicializar_bd():
    if not os.path.exists(DB_PATH):
        print(f"⌛ Creando nueva base de datos en {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH) 
        cursor = conn.cursor()

        # ==========================================================
        # TABLA LABORATORIO 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE laboratorio (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            nombre_laboratorio TEXT NOT NULL,
            ciudad TEXT,
            estado TEXT,
            codigo_postal TEXT,
            pais TEXT,
            logo BLOB
        )
        """)

        # ==========================================================
        # TABLA USUARIO
        # ==========================================================
        cursor.execute("""
        CREATE TABLE usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo_electronico TEXT UNIQUE NOT NULL,
            num_telefono TEXT,
            is_active INTEGER DEFAULT 1,
            password TEXT
        )
        """)

        # ==========================================================
        # TABLA M2M USUARIO-LABORATORIO
        # ==========================================================
        cursor.execute("""
        CREATE TABLE usuario_laboratorio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            laboratorio_id INTEGER NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuario(id),
            FOREIGN KEY(laboratorio_id) REFERENCES laboratorio(id)
        )
        """)

        # ==========================================================
        # TABLA PACIENTE 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE paciente (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            laboratorio_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            edad INTEGER,
            sexo TEXT,
            telefono TEXT,
            correo_electronico TEXT,
            FOREIGN KEY (laboratorio_id) REFERENCES laboratorio(id)
        )
        """)

        # ==========================================================
        # TABLA PAGO 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE pago (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            usuario_id INTEGER NOT NULL,
            fecha_pago TEXT,
            fecha_vencimiento TEXT,
            estado TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuario(id)
        )
        """)

        # ==========================================================
        # TABLA LOINC
        # ==========================================================
        cursor.execute("""
        CREATE TABLE loinc_code (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loinc_num TEXT UNIQUE,
            shortname TEXT,
            component TEXT,
            property TEXT,
            system TEXT,
            scale_typ TEXT
        )
        """)

        # ==========================================================
        # TABLA PLANTILLA 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE plantilla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id INTEGER, 
            titulo TEXT UNIQUE NOT NULL,
            tipo_formato TEXT DEFAULT 'RESULTADOS',
            texto_justificado_default TEXT,
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT
        )
        """)

        # ==========================================================
        # TABLA PROPIEDAD PLANTILLA 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE propiedad_plantilla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id INTEGER, 
            plantilla_id INTEGER NOT NULL,
            nombre_propiedad TEXT NOT NULL,
            loinc_code_id INTEGER,
            unidad TEXT,
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            FOREIGN KEY (plantilla_id) REFERENCES plantilla(id),
            FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id)
        )
        """)

        # ==========================================================
        # TABLA INTERVALO REFERENCIA 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE intervalo_referencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id INTEGER, 
            propiedad_id INTEGER NOT NULL,
            grupo_edad TEXT,
            sexo TEXT,
            valor_min REAL,
            valor_max REAL,
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            FOREIGN KEY (propiedad_id) REFERENCES propiedad_plantilla(id)
        )
        """)

        # ==========================================================
        # TABLA ANALISIS 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE analisis (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            paciente_id INTEGER NOT NULL,
            plantilla_id INTEGER,
            fecha_analisis TEXT,
            fecha_muestra TEXT,
            hora_toma TEXT,
            hora_impresion TEXT,
            FOREIGN KEY (paciente_id) REFERENCES paciente(id),
            FOREIGN KEY (plantilla_id) REFERENCES plantilla(id)
        )
        """)

        # ==========================================================
        # TABLA RESULTADO ANALISIS 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE resultado_analisis (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            analisis_id INTEGER NOT NULL,
            loinc_code_id INTEGER,
            nombre_propiedad TEXT,
            valor TEXT,
            unidad TEXT,
            valor_blob1 BLOB, 
            valor_blob2 BLOB, 
            FOREIGN KEY (analisis_id) REFERENCES analisis(id),
            FOREIGN KEY (loinc_code_id) REFERENCES loinc_code(id)
        )
        """)

        # ==========================================================
        # TABLA REPORTE 👈 CORREGIDA
        # ==========================================================
        cursor.execute("""
        CREATE TABLE reporte (
            id INTEGER PRIMARY KEY,
            remote_id INTEGER, 
            sincronizado INTEGER DEFAULT 1,
            fecha_modificacion TEXT,
            analisis_id INTEGER NOT NULL,
            generado_por INTEGER,
            fecha_generacion TEXT,
            FOREIGN KEY (analisis_id) REFERENCES analisis(id),
            FOREIGN KEY (generado_por) REFERENCES usuario(id)
        )
        """)

        # ==========================================================
        # USUARIO ADMIN Y LABORATORIO INICIAL
        # ==========================================================
        cursor.execute("""
        INSERT INTO laboratorio (nombre_laboratorio, ciudad, estado, codigo_postal, pais)
        VALUES (?, ?, ?, ?, ?)
        """, ("ICE Conriquez", "Guanajuato", "Guanajuato", "36000", "México"))
        laboratorio_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO usuario (nombre, correo_electronico, password)
        VALUES (?, ?, ?)
        """, ("Administrador", "admin@admin.com", "admin123"))
        usuario_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO usuario_laboratorio (usuario_id, laboratorio_id)
        VALUES (?, ?)
        """, (usuario_id, laboratorio_id))

        conn.commit()
        conn.close()
        print(f"✅ Base de datos 'Labapp.db' creada en {DB_PATH} con todas las tablas y usuario admin.")
    else:
        print(f"📂 Base de datos existente detectada en {DB_PATH}.")

if __name__ == "__main__":
    inicializar_bd()