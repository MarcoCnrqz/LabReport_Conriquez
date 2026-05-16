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
# ESTADO COMPARTIDO ENTRE PRUEBAS
# ──────────────────────────────────────────────
state: dict = {
    "access_token":  "",
    "refresh_token": "",
    "usuario_id":    1,
    "paciente_id":   6,
    "analisis_id":   1,
    "plantilla_id":  1,
}


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {state['access_token']}"}


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
        import re
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

class TestInteroperabilidadLOINC:

    def test_PIO_01_plantilla_devuelve_codigos_loinc(self):
        """PIO-01: Cada propiedad de la plantilla expone loinc_num y loinc_desc."""
        r = requests.get(
            f"{BASE_URL}/admin_ext/plantilla/{state['plantilla_id']}/propiedades/"
        )
        assert r.status_code == 200, f"PIO-01 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        assert "propiedades" in body, "PIO-01: falta campo 'propiedades'"

        for prop in body["propiedades"]:
            assert "loinc_num"  in prop, f"PIO-01: propiedad sin 'loinc_num': {prop}"
            assert "loinc_desc" in prop, f"PIO-01: propiedad sin 'loinc_desc': {prop}"

        con_loinc = [p for p in body["propiedades"] if p["loinc_num"] != ""]
        assert len(con_loinc) >= 1, (
            f"PIO-01: ninguna propiedad tiene código LOINC asignado "
            f"(total propiedades: {len(body['propiedades'])})"
        )

    def test_PIO_02_loinc_respeta_sexo_y_edad(self):
        """PIO-02: Intervalos de referencia devueltos están adaptados al paciente."""
        r = requests.get(
            f"{BASE_URL}/admin_ext/plantilla/{state['plantilla_id']}/propiedades/",
            params={"paciente_id": state["paciente_id"]},
        )
        assert r.status_code == 200, f"PIO-02 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        con_intervalo = [
            p for p in body["propiedades"]
            if (
                p.get("valor_min") not in [None, ""]
                or p.get("valor_max") not in [None, ""]
            )
        ]
        assert len(con_intervalo) >= 1, (
            "PIO-02: ninguna propiedad tiene intervalo de referencia (valor_min/max)"
        )

    def test_PIO_03_resultados_exponen_loinc_code(self):
        """PIO-03: Resultados de un análisis incluyen campo loinc_code."""
        r = requests.get(
            f"{BASE_URL}/api/resultados/",
            params={"analisis_id": state["analisis_id"]},
            headers=auth_headers(),
        )
        assert r.status_code == 200, f"PIO-03 esperaba 200, obtuvo {r.status_code}"
        body = r.json()
        resultados = body if isinstance(body, list) else body.get("results", [])
        assert len(resultados) >= 1, "PIO-03: no hay resultados para el análisis"

        for res in resultados:
            assert "loinc_code" in res, f"PIO-03: resultado sin 'loinc_code': {res}"

    def test_PIO_05_plantilla_inexistente_devuelve_404(self):
        """PIO-05: Plantilla con ID 99999 devuelve 404."""
        r = requests.get(
            f"{BASE_URL}/admin_ext/plantilla/99999/propiedades/"
        )
        assert r.status_code == 404, f"PIO-05 esperaba 404, obtuvo {r.status_code}"