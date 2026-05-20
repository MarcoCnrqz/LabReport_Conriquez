"""
===================================================================
  SUITE DE PRUEBAS — Sistema Laboratorio
  Equivalente Python del Postman: Integración (6.2.2),
  Sistema (6.2.3) e Interoperabilidad LOINC (6.2.4)
===================================================================

  Requisitos:
      pip install requests pytest

  Configuración:
      Edita las constantes de la sección CONFIG antes de correr.

  Ejecución:
      pytest test_laboratorio.py -v
      pytest test_laboratorio.py -v -k "PI"      # solo integración
      pytest test_laboratorio.py -v -k "PS"      # solo sistema
      pytest test_laboratorio.py -v -k "PIO"     # solo LOINC
===================================================================
"""

import re
import sqlite3
import pytest
import requests

# ──────────────────────────────────────────────
# CONFIG — ajusta estos valores antes de correr
# ──────────────────────────────────────────────
BASE_URL       = "http://127.0.0.1:8000"
CORREO_ADMIN   = "Admin@gmail.com"   # Correo del modelo Usuario (API REST)
PASSWORD_ADMIN = "Admin123"

# Usuario Django Admin (auth.User — distinto del modelo Usuario de la app).
# Corresponde al superusuario creado con: python manage.py createsuperuser
DJANGO_ADMIN_USERNAME = "Conriquez"
DJANGO_ADMIN_PASSWORD = "Markicio12"

# ──────────────────────────────────────────────
# ENDPOINTS  (todos apuntan al mismo BASE_URL)
# ──────────────────────────────────────────────
_EP_LOGIN      = f"{BASE_URL}/api/login/"          # POST → {access_token, refresh_token}
_EP_PLANTILLAS = f"{BASE_URL}/api/plantillas/"     # GET  → lista de plantillas
_EP_PLANTILLA  = f"{BASE_URL}/api/plantillas"      # /{id}/ → detalle con propiedades
_EP_PACIENTES  = f"{BASE_URL}/api/pacientes/"      # GET  → lista de pacientes
_EP_ANALISIS   = f"{BASE_URL}/api/analisis/"       # GET  → lista de análisis
_EP_RESULTADOS = f"{BASE_URL}/api/resultados/"     # GET  ?analisis_id=X
_EP_ADM_PROPS  = f"{BASE_URL}/admin_ext/plantilla" # /{id}/propiedades/

# ──────────────────────────────────────────────
# ESTADO COMPARTIDO ENTRE TODAS LAS PRUEBAS
# (un único dict para integración, sistema y LOINC)
# ──────────────────────────────────────────────
state: dict = {
    "access_token":  "",
    "refresh_token": "",
    "usuario_id":    1,
    "paciente_id":   1,
    "analisis_id":   1,
    "plantilla_id":  1,
}


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {state['access_token']}"}


# Alias usado por el bloque LOINC (mismo comportamiento)
def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {state.get('access_token', '')}",
        "Content-Type":  "application/json",
    }


# ================================================================
# 6.2.2 — PRUEBAS DE INTEGRACIÓN
# ================================================================

class TestAuth:

    def test_PI_01_login_exitoso(self):
        """PI-01: Login con credenciales válidas devuelve 200 y tokens."""
        r = requests.post(
            f"{BASE_URL}/api/login/",
            json={"correo": CORREO_ADMIN, "password": PASSWORD_ADMIN},
        )
        assert r.status_code == 200, f"PI-01 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        assert "access_token"  in body, "PI-01: falta access_token"
        assert "refresh_token" in body, "PI-01: falta refresh_token"
        state["access_token"]  = body["access_token"]
        state["refresh_token"] = body["refresh_token"]
        state["usuario_id"]    = body.get("id", state["usuario_id"])

    def test_PI_02_login_credenciales_incorrectas(self):
        """PI-02: Login con credenciales malas devuelve 401 y campo error."""
        r = requests.post(
            f"{BASE_URL}/api/login/",
            json={"correo": "noexiste@laboratorio.com", "password": "password_malo"},
        )
        assert r.status_code == 401, f"PI-02 esperaba 401, obtuvo {r.status_code}"
        assert "error" in r.json(), "PI-02: falta campo 'error' en respuesta"

    def test_PI_03_refresh_token(self):
        """PI-03: Refresh token válido genera nuevo access_token."""
        r = requests.post(
            f"{BASE_URL}/api/token/refresh/",
            json={"refresh_token": state["refresh_token"]},
        )
        assert r.status_code == 200, f"PI-03 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        assert "access_token" in body, "PI-03: falta access_token"
        state["access_token"] = body["access_token"]

    def test_PI_04_acceso_sin_token(self):
        """PI-04: Acceder a ruta protegida sin token devuelve 401."""
        r = requests.get(f"{BASE_URL}/api/mi_laboratorio/")
        assert r.status_code == 401, f"PI-04 esperaba 401, obtuvo {r.status_code}"
        body = r.json()
        assert "error" in body, "PI-04: falta campo 'error'"
        assert "Token" in body["error"], (
            f"PI-04: mensaje no menciona 'Token'. Got: {body['error']}"
        )

    def test_PI_05_mi_laboratorio_jwt_valido(self):
        """PI-05: Endpoint /mi_laboratorio/ con token válido devuelve datos del lab."""
        r = requests.get(f"{BASE_URL}/api/mi_laboratorio/", headers=auth_headers())
        assert r.status_code == 200, f"PI-05 esperaba 200, obtuvo {r.status_code}"
        assert "nombre_laboratorio" in r.json(), "PI-05: falta nombre_laboratorio"


class TestPacientes:

    def test_PI_06_crear_paciente(self):
        """PI-06: Crear paciente devuelve 201 con ID."""
        payload = {
            "nombre":           "Juan",
            "apellido_paterno": "Pérez",
            "apellido_materno": "García",
            "fecha_nacimiento": "2003-05-15",
            "sexo":             "MASCULINO",
            "laboratorio_id":   1,
        }
        r = requests.post(
            f"{BASE_URL}/api/pacientes/",
            json=payload,
            headers=auth_headers(),
        )
        assert r.status_code == 201, f"PI-06 esperaba 201, obtuvo {r.status_code}: {r.text}"
        body = r.json()
        assert "id" in body, "PI-06: falta campo 'id'"
        state["paciente_id"] = body["id"]

    def test_PI_07_listar_pacientes(self):
        """PI-07: Listar pacientes devuelve 200 con lista o paginado."""
        r = requests.get(f"{BASE_URL}/api/pacientes/", headers=auth_headers())
        assert r.status_code == 200, f"PI-07 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        assert isinstance(body, list) or "results" in body, (
            "PI-07: respuesta no es lista ni tiene 'results'"
        )

    def test_PI_08_listar_pacientes_filtrado_por_usuario(self):
        """PI-08: Filtro ?usuario_id= devuelve 200."""
        r = requests.get(
            f"{BASE_URL}/api/pacientes/",
            params={"usuario_id": state["usuario_id"]},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PI-08 esperaba 200, obtuvo {r.status_code}"

    def test_PI_09_obtener_paciente_por_id(self):
        """PI-09: GET /pacientes/{id}/ devuelve el nombre del paciente."""
        r = requests.get(
            f"{BASE_URL}/api/pacientes/{state['paciente_id']}/",
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PI-09 esperaba 200, obtuvo {r.status_code}"
        assert "nombre" in r.json(), "PI-09: falta campo 'nombre'"

    def test_PI_10_actualizar_paciente_patch(self):
        """PI-10: PATCH parcial actualiza el nombre correctamente."""
        r = requests.patch(
            f"{BASE_URL}/api/pacientes/{state['paciente_id']}/",
            json={"nombre": "Juan Carlos"},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PI-10 esperaba 200, obtuvo {r.status_code}"
        assert r.json()["nombre"] == "Juan Carlos", (
            f"PI-10: nombre esperado 'Juan Carlos', obtuvo {r.json().get('nombre')}"
        )

    def test_PI_11_buscar_paciente_en_nube(self):
        """PI-11: Búsqueda por apellido devuelve lista."""
        r = requests.get(
            f"{BASE_URL}/api/pacientes/buscar_nube/",
            params={"usuario_id": state["usuario_id"], "apellido_paterno": "Pérez"},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PI-11 esperaba 200, obtuvo {r.status_code}"
        assert isinstance(r.json(), list), "PI-11: respuesta no es lista"

    def test_PI_12_buscar_sin_parametros_falla(self):
        """PI-12: Búsqueda sin nombre ni apellido devuelve 400 con error."""
        r = requests.get(
            f"{BASE_URL}/api/pacientes/buscar_nube/",
            params={"usuario_id": state["usuario_id"]},
            headers=auth_headers(),
        )
        assert r.status_code == 400, f"PI-12 esperaba 400, obtuvo {r.status_code}"
        assert "error" in r.json(), "PI-12: falta campo 'error'"

    def test_PI_13_eliminar_paciente(self):
        """PI-13: DELETE /pacientes/{id}/ devuelve 204."""
        r = requests.delete(
            f"{BASE_URL}/api/pacientes/{state['paciente_id']}/",
            headers=auth_headers(),
        )
        assert r.status_code == 204, f"PI-13 esperaba 204, obtuvo {r.status_code}"


class TestAnalisis:

    def test_PI_14_listar_analisis(self):
        """PI-14: GET /analisis/ devuelve 200 y guarda un ID real en state."""
        r = requests.get(f"{BASE_URL}/api/analisis/", headers=auth_headers())
        assert r.status_code == 200, f"PI-14 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        lista = body if isinstance(body, list) else body.get("results", [])
        assert len(lista) >= 1, (
            "PI-14: no hay analisis en la BD — crea al menos uno antes de correr la suite"
        )
        state["analisis_id"] = lista[0]["id"]

    def test_PI_15_actualizar_resultado_parcial(self):
        """PI-15: PATCH parcial de resultado actualiza valor y unidad."""
        r_list = requests.get(
            f"{BASE_URL}/api/resultados/",
            params={"analisis_id": state["analisis_id"]},
            headers=auth_headers(),
        )
        assert r_list.status_code == 200, f"PI-15 (lista) esperaba 200, obtuvo {r_list.status_code}"
        body = r_list.json()
        resultados = body if isinstance(body, list) else body.get("results", [])
        assert len(resultados) >= 1, (
            "PI-15: el analisis no tiene resultados — verifica que existan en la BD"
        )
        resultado_id = resultados[0]["id"]
        state["resultado_id"] = resultado_id

        r = requests.patch(
            f"{BASE_URL}/api/resultados/{resultado_id}/",
            json={"valor": "14.5", "unidad": "g/dL"},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PI-15 esperaba 200, obtuvo {r.status_code}"
        assert "valor" in r.json(), "PI-15: falta campo 'valor' en respuesta"


# ================================================================
# 6.2.3 — PRUEBAS DE SISTEMA (FLUJO COMPLETO)
# ================================================================

class TestSistemaFlujoCompleto:

    def test_PS_01_login(self):
        """PS-01 [PASO 1]: Login exitoso."""
        r = requests.post(
            f"{BASE_URL}/api/login/",
            json={"correo": CORREO_ADMIN, "password": PASSWORD_ADMIN},
        )
        assert r.status_code == 200, f"PS-01 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        state["access_token"]  = body["access_token"]
        state["refresh_token"] = body["refresh_token"]
        state["usuario_id"]    = body.get("id", state["usuario_id"])

    def test_PS_02_obtener_laboratorio(self):
        """PS-02 [PASO 2]: Datos del laboratorio del usuario autenticado."""
        r = requests.get(f"{BASE_URL}/api/mi_laboratorio/", headers=auth_headers())
        assert r.status_code == 200, f"PS-02 esperaba 200, obtuvo {r.status_code}"
        assert "nombre_laboratorio" in r.json(), "PS-02: falta nombre_laboratorio"

    def test_PS_03_registrar_paciente(self):
        """PS-03 [PASO 3]: Registrar un nuevo paciente."""
        payload = {
            "nombre":           "María",
            "apellido_paterno": "López",
            "apellido_materno": "Torres",
            "fecha_nacimiento": "2003-03-20",
            "sexo":             "FEMENINO",
            "laboratorio_id":   1,
        }
        r = requests.post(
            f"{BASE_URL}/api/pacientes/",
            json=payload,
            headers=auth_headers(),
        )
        assert r.status_code == 201, f"PS-03 esperaba 201, obtuvo {r.status_code}: {r.text}"
        state["paciente_id"] = r.json()["id"]

    def test_PS_04_buscar_paciente_registrado(self):
        """PS-04 [PASO 4]: El paciente recién registrado aparece en la búsqueda."""
        r = requests.get(
            f"{BASE_URL}/api/pacientes/buscar_nube/",
            params={"usuario_id": state["usuario_id"], "apellido_paterno": "López"},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PS-04 esperaba 200, obtuvo {r.status_code}"
        resultados = r.json()
        assert isinstance(resultados, list) and len(resultados) >= 1, (
            f"PS-04: se esperaba al menos 1 resultado, obtuvo {len(resultados)}"
        )

    def test_PS_05_propiedades_plantilla(self):
        """PS-05 [PASO 5]: Plantilla devuelve sus propiedades para el paciente."""
        r = requests.get(
            f"{BASE_URL}/admin_ext/plantilla/{state['plantilla_id']}/propiedades/",
            params={"paciente_id": state["paciente_id"]},
        )
        assert r.status_code == 200, f"PS-05 esperaba 200, obtuvo {r.status_code}"
        assert "propiedades" in r.json(), "PS-05: falta campo 'propiedades'"

    def test_PS_06_generar_pdf_analisis(self):
        """PS-06 [PASO 6]: Generar PDF devuelve 200 con Content-Type application/pdf."""
        r = requests.get(
            f"{BASE_URL}/admin_ext/analisis/{state['analisis_id']}/generar_pdf/",
            headers=auth_headers(),
        )
        assert r.status_code == 200, (
            f"PS-06 esperaba 200, obtuvo {r.status_code}: {r.text}"
        )
        content_type = r.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, (
            f"PS-06: Content-Type esperado 'application/pdf', obtuvo '{content_type}'"
        )

    def test_PS_07_admin_django_crear_plantilla(self):
        """PS-07 [PASO 7]: El administrador crea una Plantilla desde el panel Django Admin."""
        import time

        session = requests.Session()

        # ── 1. Obtener CSRF del formulario de login ──────────────────────────
        login_get = session.get(f"{BASE_URL}/admin/login/")
        assert login_get.status_code == 200, (
            f"PS-07: no se pudo acceder a /admin/login/ ({login_get.status_code})"
        )
        csrf_match = re.search(
            r'csrfmiddlewaretoken[^>]*value=["\']([^"\']+)', login_get.text
        )
        assert csrf_match, "PS-07: no se encontró csrfmiddlewaretoken en el formulario de login"
        csrf_token = csrf_match.group(1)

        # ── 2. Iniciar sesión en Django Admin ────────────────────────────────
        login_resp = session.post(
            f"{BASE_URL}/admin/login/",
            data={
                "username":            DJANGO_ADMIN_USERNAME,
                "password":            DJANGO_ADMIN_PASSWORD,
                "csrfmiddlewaretoken": csrf_token,
                "next":                "/admin/",
            },
            headers={"Referer": f"{BASE_URL}/admin/login/"},
            allow_redirects=True,
        )
        assert login_resp.status_code in (200, 302), (
            f"PS-07: login admin esperaba 200/302, obtuvo {login_resp.status_code}"
        )
        assert "sessionid" in session.cookies, (
            "PS-07: no se obtuvo sessionid tras login en Django Admin"
        )

        # ── 3. Obtener CSRF del formulario de creación de Plantilla ──────────
        add_get = session.get(f"{BASE_URL}/admin/LabApp/plantilla/add/")
        assert add_get.status_code == 200, (
            f"PS-07: no se pudo acceder a /admin/LabApp/plantilla/add/ "
            f"({add_get.status_code})"
        )
        csrf_match2 = re.search(
            r'csrfmiddlewaretoken[^>]*value=["\']([^"\']+)', add_get.text
        )
        assert csrf_match2, (
            "PS-07: no se encontró csrfmiddlewaretoken en el formulario de Plantilla"
        )
        csrf_token2 = csrf_match2.group(1)

        # ── 4. Enviar formulario para crear la Plantilla ─────────────────────
        titulo_prueba = f"Plantilla de Prueba PS-07 {int(time.time())}"

        create_resp = session.post(
            f"{BASE_URL}/admin/LabApp/plantilla/add/",
            data={
                "csrfmiddlewaretoken":       csrf_token2,
                "titulo":                    titulo_prueba,
                "tipo_formato":              "RESULTADOS",
                "activo":                    "on",
                "loinc_code":                "",
                "texto_justificado_default": "PLANTILLA DE PRUEBAS DE SISTEMA PS-07",
                "tipo_muestra":              "interpretada",
                "metodo":                    "AUTOMÁTICO",
                # Management form — prefix viene del related_name='plantilla_propiedades'
                "plantilla_propiedades-TOTAL_FORMS":    "1",
                "plantilla_propiedades-INITIAL_FORMS":  "0",
                "plantilla_propiedades-MIN_NUM_FORMS":  "0",
                "plantilla_propiedades-MAX_NUM_FORMS":  "1000",
                # Fila extra vacía (form-0) — Django la ignora si todos los campos están vacíos
                "plantilla_propiedades-0-id":            "",
                "plantilla_propiedades-0-plantilla":     "",
                "plantilla_propiedades-0-propiedad":     "",
                "plantilla_propiedades-0-loinc_code":    "",
                "plantilla_propiedades-0-seccion":       "",
                "plantilla_propiedades-0-orden":         "0",
                "plantilla_propiedades-0-orden_seccion": "0",
                "plantilla_propiedades-0-DELETE":        "",
                "_save":                     "Guardar",
            },
            headers={"Referer": f"{BASE_URL}/admin/LabApp/plantilla/add/"},
            allow_redirects=True,
        )

        # ── DIAGNÓSTICO: muestra errores de validación si los hay ─────────────
        errores = re.findall(r'<ul class="errorlist.*?</ul>', create_resp.text, re.DOTALL)
        if errores:
            print("\n=== ERRORES EN EL FORMULARIO ===")
            for e in errores:
                print(e)
            print("=== FIN ERRORES ===\n")

        # ── Validaciones ──────────────────────────────────────────────────────
        assert create_resp.status_code in (200, 302), (
            f"PS-07: esperaba 200/302, obtuvo {create_resp.status_code}"
        )
        assert "add" not in create_resp.url, (
            f"PS-07: plantilla NO guardada — Django devolvió el formulario con errores. "
            f"URL: {create_resp.url}"
        )


# ================================================================
# 6.2.4 — PRUEBAS DE INTEROPERABILIDAD LOINC
# ================================================================

# =============================================================================
# HELPERS LOINC
# =============================================================================

def _login():
    """
    Obtiene access_token desde la API JWT de Django y actualiza el state global.
    Usa el mismo endpoint y credenciales que el resto de la suite.
    """
    r = requests.post(
        _EP_LOGIN,
        json={"correo": CORREO_ADMIN, "password": PASSWORD_ADMIN},
        timeout=10,
    )
    assert r.status_code == 200, (
        f"Login falló ({r.status_code}). "
        f"Verifica BASE_URL, CORREO_ADMIN y PASSWORD_ADMIN.\n{r.text}"
    )
    data = r.json()
    state["access_token"]  = data["access_token"]
    state["refresh_token"] = data.get("refresh_token", "")


def _primera_plantilla_con_loinc() -> dict | None:
    """
    Busca la primera plantilla que tenga al menos una propiedad con loinc_num.
    Retorna el dict completo o None si no encuentra ninguna.
    """
    r = requests.get(_EP_PLANTILLAS, headers=_auth_headers(), timeout=10)
    if r.status_code != 200:
        return None
    body   = r.json()
    lista  = body if isinstance(body, list) else body.get("results", [])
    for pl in lista:
        detalle = requests.get(
            f"{_EP_PLANTILLA}/{pl['id']}/",
            headers=_auth_headers(),
            timeout=10,
        )
        if detalle.status_code != 200:
            continue
        data  = detalle.json()
        props = data.get("propiedades", [])
        if any(p.get("loinc_num", "").strip() for p in props):
            return data
    return None


# =============================================================================
# SETUP DEL MÓDULO  — se ejecuta una sola vez antes de todos los tests
# =============================================================================

def setup_module(module):
    """
    1. Login  → access_token
    2. Busca una plantilla con propiedades LOINC
    3. Obtiene un paciente de prueba
    4. Obtiene un análisis de prueba
    """
    _login()

    # ── Plantilla ──────────────────────────────────────────────────────────
    r_pl = requests.get(_EP_PLANTILLAS, headers=_auth_headers(), timeout=10)
    assert r_pl.status_code == 200, (
        f"No se pudo obtener la lista de plantillas: {r_pl.status_code}"
    )
    lista_pl = r_pl.json() if isinstance(r_pl.json(), list) else r_pl.json().get("results", [])
    assert len(lista_pl) >= 1, (
        "setup_module: no hay plantillas en Django. "
        "Crea al menos una plantilla con propiedades."
    )
    state["plantilla_id"] = lista_pl[0]["id"]

    # ── Paciente ───────────────────────────────────────────────────────────
    r_pac = requests.get(_EP_PACIENTES, headers=_auth_headers(), timeout=10)
    if r_pac.status_code == 200:
        pacs = r_pac.json() if isinstance(r_pac.json(), list) else r_pac.json().get("results", [])
        state["paciente_id"] = pacs[0]["id"] if pacs else None
    else:
        state["paciente_id"] = None

    # ── Análisis ───────────────────────────────────────────────────────────
    r_an = requests.get(_EP_ANALISIS, headers=_auth_headers(), timeout=10)
    if r_an.status_code == 200:
        ans = r_an.json() if isinstance(r_an.json(), list) else r_an.json().get("results", [])
        state["analisis_id"] = ans[0]["id"] if ans else None
    else:
        state["analisis_id"] = None


# =============================================================================
# FIXTURE  — BD SQLite temporal para PIO-06
# =============================================================================

@pytest.fixture(scope="module")
def db_loinc(tmp_path_factory):
    """
    BD SQLite temporal con el esquema mínimo para verificar que la
    sincronización local persiste datos LOINC correctamente.
    Las tablas coinciden con las definidas en init_db.py del proyecto.
    """
    db_file = tmp_path_factory.mktemp("loinc") / "test_loinc.db"
    conn    = sqlite3.connect(str(db_file))
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE loinc_code (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            loinc_num TEXT UNIQUE NOT NULL,
            shortname TEXT,
            component TEXT,
            property  TEXT,
            system    TEXT,
            scale_typ TEXT,
            method_typ TEXT
        );

        CREATE TABLE plantilla (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id                 INTEGER,
            titulo                    TEXT UNIQUE NOT NULL,
            tipo_formato              TEXT DEFAULT 'RESULTADOS',
            texto_justificado_default TEXT,
            loinc_code_id             INTEGER,
            tipo_muestra              TEXT,
            metodo                    TEXT,
            sincronizado              INTEGER DEFAULT 1,
            fecha_modificacion        TEXT,
            activo                    INTEGER DEFAULT 1
        );

        CREATE TABLE propiedad (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id             INTEGER,
            nombre_propiedad      TEXT UNIQUE NOT NULL,
            tipo                  TEXT DEFAULT 'CUANTITATIVO',
            unidad                TEXT,
            opciones_cualitativas TEXT,
            sincronizado          INTEGER DEFAULT 1,
            fecha_modificacion    TEXT
        );

        CREATE TABLE plantilla_propiedad (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_id    INTEGER NOT NULL,
            propiedad_id    INTEGER NOT NULL,
            loinc_code_id   INTEGER,
            seccion         TEXT,
            orden           INTEGER DEFAULT 0,
            orden_seccion   INTEGER DEFAULT 0,
            UNIQUE (plantilla_id, propiedad_id)
        );

        CREATE TABLE intervalo_referencia (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id          INTEGER,
            propiedad_id       INTEGER NOT NULL,
            sexo               TEXT DEFAULT 'AMBOS',
            edad_min_meses     INTEGER,
            edad_max_meses     INTEGER,
            valor_min          REAL,
            valor_max          REAL,
            sincronizado       INTEGER DEFAULT 1,
            fecha_modificacion TEXT
        );
    """)
    conn.commit()
    conn.close()
    return str(db_file)


# =============================================================================
# PRUEBAS DE INTEROPERABILIDAD LOINC
# =============================================================================

class TestInteroperabilidadLOINC:
    """
    Pruebas de interoperabilidad LOINC entre Django (nube) y la app local.

    ID       Descripción breve
    ───────  ─────────────────────────────────────────────────────────────────
    PIO-01   Plantilla expone campos loinc_num y loinc_desc en cada propiedad
    PIO-02   Intervalos de referencia filtrados por edad y sexo del paciente
    PIO-03   Resultados de análisis incluyen campo loinc_code en la respuesta
    PIO-04   Plantilla inexistente devuelve 404
    PIO-05   Todos los loinc_num no vacíos tienen formato oficial (digits-digit)
    PIO-06   La sincronización local persiste loinc_num en la BD SQLite
    PIO-08   Campo loinc_code siempre presente en resultados (null, no ausente)
    """

    # ─── PIO-01 ───────────────────────────────────────────────────────────────

    def test_PIO_01_plantilla_devuelve_codigos_loinc(self):
        """PIO-01: Cada propiedad de la plantilla expone loinc_num y loinc_desc."""
        r = requests.get(
            f"{_EP_ADM_PROPS}/{state['plantilla_id']}/propiedades/",
            timeout=10,
        )
        assert r.status_code == 200, (
            f"PIO-01 esperaba 200, obtuvo {r.status_code}"
        )
        body = r.json()

        assert "propiedades" in body, "PIO-01: falta el campo 'propiedades' en la respuesta"

        for prop in body["propiedades"]:
            assert "loinc_num"  in prop, f"PIO-01: propiedad sin 'loinc_num': {prop}"
            assert "loinc_desc" in prop, f"PIO-01: propiedad sin 'loinc_desc': {prop}"

        con_loinc = [p for p in body["propiedades"] if p["loinc_num"] != ""]
        assert len(con_loinc) >= 1, (
            f"PIO-01: ninguna propiedad tiene código LOINC asignado "
            f"(total propiedades: {len(body['propiedades'])}). "
            f"Asigna al menos un loinc_num desde el admin de Django."
        )

        # Guarda para no repetir la petición en PIO-05
        state["propiedades_pio01"] = body["propiedades"]

    # ─── PIO-02 ───────────────────────────────────────────────────────────────

    def test_PIO_02_intervalos_adaptados_al_paciente(self):
        """
        PIO-02: Cuando se pasa paciente_id, la API devuelve valor_min/valor_max
        filtrados para ese paciente (edad + sexo).

        Nota: LOINC *no* define rangos de referencia — eso es responsabilidad
        del sistema clínico. Este test verifica que Django aplica el filtrado
        correcto de sus propios intervalos de referencia, no que LOINC lo haga.
        """
        if not state.get("paciente_id"):
            pytest.skip("PIO-02: no hay paciente de prueba en Django")

        r = requests.get(
            f"{_EP_ADM_PROPS}/{state['plantilla_id']}/propiedades/",
            params={"paciente_id": state["paciente_id"]},
            timeout=10,
        )
        assert r.status_code == 200, (
            f"PIO-02 esperaba 200, obtuvo {r.status_code}"
        )
        body = r.json()

        con_intervalo = [
            p for p in body["propiedades"]
            if (
                p.get("valor_min") not in [None, ""]
                or p.get("valor_max") not in [None, ""]
            )
        ]
        assert len(con_intervalo) >= 1, (
            "PIO-02: ninguna propiedad devuelve valor_min/valor_max para el paciente. "
            "Verifica que los intervalos de referencia están cargados en Django."
        )

        # Verificar coherencia interna: min <= max, y ambos presentes a la vez
        for prop in con_intervalo:
            nombre = prop.get("nombre_propiedad", "?")
            v_min  = prop.get("valor_min")
            v_max  = prop.get("valor_max")

            assert v_min is not None, (
                f"PIO-02: '{nombre}' tiene valor_max pero valor_min es null"
            )
            assert v_max is not None, (
                f"PIO-02: '{nombre}' tiene valor_min pero valor_max es null"
            )
            assert float(v_min) <= float(v_max), (
                f"PIO-02: intervalo inválido en '{nombre}': {v_min} > {v_max}"
            )

    # ─── PIO-03 ───────────────────────────────────────────────────────────────

    def test_PIO_03_resultados_exponen_loinc_code(self):
        """PIO-03: Resultados de un análisis incluyen el campo loinc_code."""
        if not state.get("analisis_id"):
            pytest.skip("PIO-03: no hay análisis de prueba en Django")

        r = requests.get(
            _EP_RESULTADOS,
            params={"analisis_id": state["analisis_id"]},
            headers=_auth_headers(),
            timeout=10,
        )
        assert r.status_code == 200, (
            f"PIO-03 esperaba 200, obtuvo {r.status_code}"
        )
        body       = r.json()
        resultados = body if isinstance(body, list) else body.get("results", [])
        assert len(resultados) >= 1, (
            "PIO-03: no hay resultados para el análisis. "
            "Asegúrate de que el análisis tiene resultados cargados."
        )

        for res in resultados:
            assert "loinc_code" in res, (
                f"PIO-03: resultado sin campo 'loinc_code': {res}"
            )

    # ─── PIO-04 ───────────────────────────────────────────────────────────────

    def test_PIO_04_plantilla_inexistente_devuelve_404(self):
        """PIO-04: Solicitar propiedades de la plantilla ID 99999 devuelve 404."""
        r = requests.get(
            f"{_EP_ADM_PROPS}/99999/propiedades/",
            timeout=10,
        )
        assert r.status_code == 404, (
            f"PIO-04 esperaba 404, obtuvo {r.status_code}"
        )

    # ─── PIO-05 ───────────────────────────────────────────────────────────────

    def test_PIO_05_formato_loinc_num_es_valido(self):
        """
        PIO-05: Todos los loinc_num no vacíos cumplen el formato oficial del
        estándar LOINC: uno o más dígitos, guion, exactamente un dígito
        verificador.

        Formato regex: ^\\d+-\\d$
        Ejemplos válidos : 718-7 | 2339-0 | 26453-1 | 789-8
        Ejemplos inválidos: 718 | 7187 | 718-77 | ABC-1 | 718 - 7
        """
        # Reutiliza los datos de PIO-01 si ya se ejecutó; si no, los consulta
        propiedades = state.get("propiedades_pio01")
        if not propiedades:
            r = requests.get(
                f"{_EP_ADM_PROPS}/{state['plantilla_id']}/propiedades/",
                timeout=10,
            )
            assert r.status_code == 200, (
                f"PIO-05: no se pudo obtener propiedades ({r.status_code})"
            )
            propiedades = r.json().get("propiedades", [])

        patron_loinc = re.compile(r"^\d+-\d$")
        invalidos    = []

        for prop in propiedades:
            loinc_num = prop.get("loinc_num", "").strip()
            if loinc_num and not patron_loinc.match(loinc_num):
                invalidos.append({
                    "propiedad": prop.get("nombre_propiedad", "?"),
                    "loinc_num": loinc_num,
                })

        assert not invalidos, (
            f"PIO-05: {len(invalidos)} código(s) LOINC con formato inválido "
            f"(se esperaba el patrón dígitos-dígito, ej. 718-7, 26453-1):\n"
            + "\n".join(
                f"  • {x['propiedad']}: '{x['loinc_num']}'"
                for x in invalidos
            )
        )

    # ─── PIO-06 ───────────────────────────────────────────────────────────────

    def test_PIO_06_loinc_code_siempre_presente_en_resultados(self):
        """
        PIO-06: El campo 'loinc_code' debe existir en TODOS los objetos resultado,
        incluso cuando su valor es null.

        Diferencia clave:
          {"loinc_code": null}  → CORRECTO  (código no asignado, campo presente)
          {}                    → INCORRECTO (campo ausente, rompe el contrato JSON
                                              y falla en clientes que lo esperan)
        """
        if not state.get("analisis_id"):
            pytest.skip("PIO-06: no hay análisis de prueba en Django")

        r = requests.get(
            _EP_RESULTADOS,
            params={"analisis_id": state["analisis_id"]},
            headers=_auth_headers(),
            timeout=10,
        )
        assert r.status_code == 200, (
            f"PIO-06 esperaba 200, obtuvo {r.status_code}"
        )
        body       = r.json()
        resultados = body if isinstance(body, list) else body.get("results", [])
        assert len(resultados) >= 1, "PIO-06: no hay resultados para verificar"

        # Campo ausente → fallo real
        ausentes = [res for res in resultados if "loinc_code" not in res]
        assert not ausentes, (
            f"PIO-06: {len(ausentes)} resultado(s) no contienen el campo "
            f"'loinc_code' (ni como null). El serializador debe incluirlo siempre.\n"
            f"Ejemplo del resultado problemático: {ausentes[0]}"
        )

        # Campo presente con valor null → aceptable, solo informativo
        nulos = [res for res in resultados if res.get("loinc_code") is None]
        if nulos:
            print(
                f"\n  [PIO-06 info] {len(nulos)}/{len(resultados)} resultado(s) "
                f"tienen loinc_code=null (propiedad sin código LOINC — aceptable)."
            )
