# LabApp/tests.py

# PRUEBAS UNITARIAS — Sistema de Gestión de Laboratorio Clínico


from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db import IntegrityError
from datetime import date

from LabApp.models import (
    Laboratorio, Usuario, Paciente, Propiedad,
    IntervaloReferencia, Plantilla, PlantillaPropiedad,
    AnalisisPropiedadExtra, Analisis, ResultadoAnalisis,
)


# =============================================================================
# HELPERS
# =============================================================================

def crear_lab(nombre='Lab Test'):
    return Laboratorio.objects.create(nombre_laboratorio=nombre)


def crear_propiedad(nombre='HEMOGLOBINA', tipo='CUANTITATIVO', unidad='g/dL'):
    return Propiedad.objects.create(
        nombre_propiedad=nombre, tipo=tipo, unidad=unidad
    )


def crear_plantilla(titulo='BH COMPLETA'):
    return Plantilla.objects.create(titulo=titulo, tipo_formato='RESULTADOS')


def crear_paciente(lab, nombre='Juan', ap='Perez', am='Lopez',
                   nacimiento=date(1990, 6, 15), sexo='MASCULINO'):
    return Paciente.objects.create(
        laboratorio=lab,
        nombre=nombre,
        apellido_paterno=ap,
        apellido_materno=am,
        fecha_nacimiento=nacimiento,
        sexo=sexo,
    )


# =============================================================================
# PU01 — LOGIN DJANGO ADMIN
# =============================================================================

class PU01_LoginDjangoAdmin(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_prueba',
            password='AdminTest123!',
            email='admin@test.com',
        )

    def test_login_correcto(self):
        """Login exitoso redirige al panel admin."""
        response = self.client.post('/admin/login/', {
            'username': 'admin_prueba',
            'password': 'AdminTest123!',
            'next': '/admin/',
        })
        self.assertRedirects(response, '/admin/')

    def test_login_credenciales_incorrectas(self):
        """Login fallido permanece en la página de login."""
        response = self.client.post('/admin/login/', {
            'username': 'admin_prueba',
            'password': 'contrasena_incorrecta',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Por favor introduza')

    def test_login_campos_vacios(self):
        """Login con campos vacíos no crea sesión."""
        response = self.client.post('/admin/login/', {
            'username': '',
            'password': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('sessionid', response.cookies)

    def test_login_usuario_inexistente(self):
        """Login con usuario que no existe no otorga acceso."""
        response = self.client.post('/admin/login/', {
            'username': 'no_existe',
            'password': 'cualquier_clave',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('sessionid', response.cookies)


# =============================================================================
# PU02 — LOGOUT / SESIÓN
# =============================================================================

class PU02_LogoutSesion(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_logout',
            password='Admin123!',
            email='logout@test.com',
        )
        self.client.force_login(self.admin_user)

    def test_sesion_activa_accede_admin(self):
        """Un usuario autenticado puede acceder al panel admin."""
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)

    def test_logout_destruye_sesion(self):
        """Después del logout el usuario no puede acceder al admin."""
        self.client.post('/admin/logout/')
        response = self.client.get('/admin/')
        # Debe redirigir al login, no mostrar el panel
        self.assertNotEqual(response.status_code, 200)

    def test_acceso_sin_login_redirige(self):
        """Sin autenticación, /admin/ redirige al login."""
        cliente_anonimo = Client()
        response = cliente_anonimo.get('/admin/')
        self.assertEqual(response.status_code, 302)


# =============================================================================
# PU03a — CREACIÓN SUPERUSUARIO DJANGO
# =============================================================================

class PU03a_CreacionUsuarioDjango(TestCase):

    def test_crear_superusuario(self):
        """El superusuario se crea con contraseña cifrada."""
        user = User.objects.create_superuser(
            username='NuevoAdmin',
            password='Admin1234!',
            email='nuevo@test.com',
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertNotEqual(user.password, 'Admin1234!')
        self.assertTrue(user.password.startswith('pbkdf2_sha256'))

    def test_verificacion_contrasena(self):
        """check_password valida correctamente la contraseña."""
        user = User.objects.create_superuser(
            username='AdminVerif', password='Pass5678!', email='v@test.com'
        )
        self.assertTrue(user.check_password('Pass5678!'))
        self.assertFalse(user.check_password('contrasena_mala'))

    def test_usuario_django_no_es_superusuario_por_defecto(self):
        """Un usuario normal de Django no tiene permisos de superusuario."""
        user = User.objects.create_user(
            username='usuario_normal', password='Normal123!'
        )
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)


# =============================================================================
# PU03b — CREACIÓN USUARIO LOCAL (modelo Usuario)
# =============================================================================

class PU03b_CreacionUsuarioLocal(TestCase):

    def test_crear_usuario_tecnico(self):
        """Crear usuario local con rol TECNICO."""
        usuario = Usuario.objects.create(
            nombre='TecnicoPrueba',
            correo_electronico='tecnico@gmail.com',
            num_telefono='4774509359',
            rol='TECNICO',
            is_active=True,
        )
        usuario.set_password('test1234')
        usuario.save()
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(usuario.rol, 'TECNICO')

    def test_contrasena_cifrada(self):
        """La contraseña se cifra correctamente."""
        usuario = Usuario.objects.create(
            nombre='Test',
            correo_electronico='test2@gmail.com',
        )
        usuario.set_password('miclave123')
        usuario.save()
        self.assertTrue(usuario.check_password('miclave123'))
        self.assertFalse(usuario.check_password('clave_mala'))

    def test_roles_permitidos(self):
        """Solo se aceptan roles NORMAL y TECNICO."""
        for rol in ['NORMAL', 'TECNICO']:
            u = Usuario.objects.create(
                nombre=f'User_{rol}',
                correo_electronico=f'{rol}@test.com',
                rol=rol,
            )
            self.assertEqual(u.rol, rol)

    def test_correo_unico(self):
        """No se permiten dos usuarios con el mismo correo electrónico."""
        Usuario.objects.create(
            nombre='Primero',
            correo_electronico='duplicado@test.com',
        )
        with self.assertRaises(IntegrityError):
            Usuario.objects.create(
                nombre='Segundo',
                correo_electronico='duplicado@test.com',
            )

    def test_str_usuario(self):
        """__str__ del usuario devuelve nombre y correo."""
        usuario = Usuario.objects.create(
            nombre='Ana Lopez',
            correo_electronico='ana@test.com',
        )
        self.assertIn('Ana Lopez', str(usuario))
        self.assertIn('ana@test.com', str(usuario))


# =============================================================================
# PU03c — EDITAR Y ELIMINAR USUARIO
# =============================================================================

class PU03c_EditarEliminarUsuario(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create(
            nombre='Carlos Ruiz',
            correo_electronico='carlos@test.com',
            rol='NORMAL',
        )

    def test_editar_nombre_usuario(self):
        """Se puede cambiar el nombre de un usuario."""
        self.usuario.nombre = 'Carlos Ruiz Editado'
        self.usuario.save()
        actualizado = Usuario.objects.get(pk=self.usuario.pk)
        self.assertEqual(actualizado.nombre, 'Carlos Ruiz Editado')

    def test_editar_rol_usuario(self):
        """Se puede cambiar el rol de NORMAL a TECNICO."""
        self.usuario.rol = 'TECNICO'
        self.usuario.save()
        actualizado = Usuario.objects.get(pk=self.usuario.pk)
        self.assertEqual(actualizado.rol, 'TECNICO')

    def test_cambiar_contrasena(self):
        """Cambiar contraseña con set_password invalida la anterior."""
        self.usuario.set_password('clave_vieja')
        self.usuario.save()
        self.usuario.set_password('clave_nueva')
        self.usuario.save()
        self.assertTrue(self.usuario.check_password('clave_nueva'))
        self.assertFalse(self.usuario.check_password('clave_vieja'))

    def test_eliminar_usuario(self):
        """Eliminar un usuario reduce el conteo a cero."""
        self.usuario.delete()
        self.assertEqual(Usuario.objects.count(), 0)

    def test_desactivar_usuario(self):
        """Se puede desactivar un usuario sin eliminarlo."""
        self.usuario.is_active = False
        self.usuario.save()
        self.assertFalse(Usuario.objects.get(pk=self.usuario.pk).is_active)


# =============================================================================
# PU04 — LABORATORIO (crear, editar, eliminar)
# =============================================================================

class PU04_Laboratorio(TestCase):

    def test_crear_laboratorio(self):
        """Laboratorio se crea con sus datos correctamente."""
        lab = Laboratorio.objects.create(
            nombre_laboratorio='Laboratorio Prueba',
            ciudad='León',
            estado='Guanajuato',
            codigo_postal='36987',
            pais='México',
        )
        self.assertEqual(Laboratorio.objects.count(), 1)
        self.assertEqual(lab.nombre_laboratorio, 'Laboratorio Prueba')
        self.assertEqual(str(lab), 'Laboratorio Prueba')

    def test_laboratorio_con_responsable(self):
        """Se puede asignar un responsable sanitario al laboratorio."""
        responsable = Usuario.objects.create(
            nombre='Dr. Responsable',
            correo_electronico='responsable@test.com',
            puesto='Responsable Sanitario',
            titulo_abreviado='E.H.D.L',
            cedula_profesional='35664',
        )
        lab = Laboratorio.objects.create(
            nombre_laboratorio='Lab Con Responsable',
            responsable_sanitario_principal=responsable,
        )
        self.assertEqual(lab.responsable_sanitario_principal, responsable)

    def test_editar_laboratorio(self):
        """Se puede cambiar el nombre y ciudad de un laboratorio."""
        lab = crear_lab('Lab Original')
        lab.nombre_laboratorio = 'Lab Editado'
        lab.ciudad = 'Guadalajara'
        lab.save()
        actualizado = Laboratorio.objects.get(pk=lab.pk)
        self.assertEqual(actualizado.nombre_laboratorio, 'Lab Editado')
        self.assertEqual(actualizado.ciudad, 'Guadalajara')

    def test_eliminar_laboratorio(self):
        """Eliminar laboratorio reduce el conteo a cero."""
        lab = crear_lab()
        lab.delete()
        self.assertEqual(Laboratorio.objects.count(), 0)

    def test_eliminar_laboratorio_elimina_pacientes(self):
        """Al eliminar el laboratorio sus pacientes se eliminan en cascada."""
        lab = crear_lab()
        crear_paciente(lab)
        lab.delete()
        self.assertEqual(Paciente.objects.count(), 0)

    def test_responsable_null_al_eliminar_usuario(self):
        """Si se borra el responsable, el laboratorio no se elimina (SET_NULL)."""
        responsable = Usuario.objects.create(
            nombre='Resp. Temporal',
            correo_electronico='temporal@test.com',
        )
        lab = Laboratorio.objects.create(
            nombre_laboratorio='Lab SET NULL',
            responsable_sanitario_principal=responsable,
        )
        responsable.delete()
        lab.refresh_from_db()
        self.assertIsNone(lab.responsable_sanitario_principal)


# =============================================================================
# PU05 — PACIENTE (crear, editar, eliminar, propiedades calculadas)
# =============================================================================

class PU05_Paciente(TestCase):

    def setUp(self):
        self.lab = crear_lab()

    def test_crear_paciente_completo(self):
        """Paciente se guarda con todos sus datos."""
        paciente = Paciente.objects.create(
            laboratorio=self.lab,
            nombre='PacientePrueba',
            apellido_paterno='ApellidoPaternoPrueba',
            apellido_materno='ApellidoMaternoPrueba',
            fecha_nacimiento=date(2003, 7, 5),
            sexo='MASCULINO',
            telefono='4771309560',
            correo_electronico='paciente@gmail.com',
        )
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(
            paciente.nombre_completo,
            'PacientePrueba ApellidoPaternoPrueba ApellidoMaternoPrueba',
        )

    def test_nombre_completo_sin_apellido_materno(self):
        """nombre_completo funciona sin apellido materno."""
        paciente = Paciente.objects.create(
            laboratorio=self.lab,
            nombre='Maria',
            apellido_paterno='Gonzalez',
        )
        self.assertEqual(paciente.nombre_completo, 'Maria Gonzalez')

    def test_calculo_edad_anos(self):
        """La propiedad edad calcula años correctamente."""
        paciente = Paciente.objects.create(
            laboratorio=self.lab,
            nombre='Adulto', apellido_paterno='Test',
            fecha_nacimiento=date(2000, 1, 1),
        )
        today = date.today()
        edad_esperada = today.year - 2000 - (
            (today.month, today.day) < (1, 1)
        )
        self.assertEqual(paciente.edad, edad_esperada)

    def test_calculo_edad_meses(self):
        """edad_en_meses es correcta para un paciente de exactamente 24 meses."""
        today = date.today()
        nacimiento = date(today.year - 2, today.month, today.day)
        paciente = Paciente.objects.create(
            laboratorio=self.lab,
            nombre='Nino', apellido_paterno='Test',
            fecha_nacimiento=nacimiento,
        )
        self.assertEqual(paciente.edad_en_meses, 24)

    def test_edad_cero_sin_fecha_nacimiento(self):
        """edad y edad_en_meses devuelven 0 cuando no hay fecha de nacimiento."""
        paciente = Paciente.objects.create(
            laboratorio=self.lab,
            nombre='Sin Fecha', apellido_paterno='Test',
        )
        self.assertEqual(paciente.edad, 0)
        self.assertEqual(paciente.edad_en_meses, 0)

    def test_str_paciente(self):
        """__str__ del paciente devuelve el nombre completo."""
        paciente = crear_paciente(self.lab, nombre='Luis', ap='Mendez', am='Ramos')
        self.assertEqual(str(paciente), 'Luis Mendez Ramos')

    # ── EDITAR ────────────────────────────────────────────────────────────────

    def test_editar_nombre_paciente(self):
        """Se puede cambiar el nombre de un paciente."""
        paciente = crear_paciente(self.lab)
        paciente.nombre = 'JuanEditado'
        paciente.save()
        self.assertEqual(Paciente.objects.get(pk=paciente.pk).nombre, 'JuanEditado')

    def test_editar_telefono_paciente(self):
        """Se puede actualizar el teléfono de un paciente."""
        paciente = crear_paciente(self.lab)
        paciente.telefono = '4771234567'
        paciente.save()
        self.assertEqual(Paciente.objects.get(pk=paciente.pk).telefono, '4771234567')

    def test_editar_fecha_nacimiento_actualiza_edad(self):
        """Cambiar la fecha de nacimiento recalcula la edad automáticamente."""
        paciente = crear_paciente(self.lab, nacimiento=date(1980, 1, 1))
        edad_original = paciente.edad
        paciente.fecha_nacimiento = date(2010, 1, 1)
        paciente.save()
        self.assertLess(paciente.edad, edad_original)

    def test_editar_sexo_paciente(self):
        """Se puede cambiar el sexo de un paciente."""
        paciente = crear_paciente(self.lab, sexo='MASCULINO')
        paciente.sexo = 'FEMENINO'
        paciente.save()
        self.assertEqual(Paciente.objects.get(pk=paciente.pk).sexo, 'FEMENINO')

    # ── ELIMINAR ──────────────────────────────────────────────────────────────

    def test_eliminar_paciente(self):
        """Eliminar un paciente reduce el conteo a cero."""
        paciente = crear_paciente(self.lab)
        paciente.delete()
        self.assertEqual(Paciente.objects.count(), 0)

    def test_eliminar_paciente_elimina_analisis(self):
        """Al eliminar un paciente se eliminan sus análisis en cascada."""
        paciente = crear_paciente(self.lab)
        plantilla = crear_plantilla()
        Analisis.objects.create(
            paciente=paciente, plantilla=plantilla, status='PENDIENTE'
        )
        paciente.delete()
        self.assertEqual(Analisis.objects.count(), 0)

    def test_eliminar_paciente_elimina_resultados(self):
        """Al eliminar el paciente también se eliminan sus ResultadoAnalisis."""
        paciente = crear_paciente(self.lab)
        plantilla = crear_plantilla()
        prop = crear_propiedad()
        PlantillaPropiedad.objects.create(
            plantilla=plantilla, propiedad=prop,
            seccion='PRUEBA', orden=1, orden_seccion=1,
        )
        Analisis.objects.create(
            paciente=paciente, plantilla=plantilla, status='PENDIENTE'
        )
        paciente.delete()
        self.assertEqual(ResultadoAnalisis.objects.count(), 0)


# =============================================================================
# PU05b — PROPIEDAD (crear, duplicado, opciones cualitativas)
# =============================================================================

class PU05b_Propiedad(TestCase):

    def test_crear_propiedad_cuantitativa(self):
        """Propiedad cuantitativa se guarda con unidad."""
        prop = crear_propiedad()
        self.assertEqual(prop.nombre_propiedad, 'HEMOGLOBINA')
        self.assertEqual(prop.unidad, 'g/dL')

    def test_crear_propiedad_cualitativa(self):
        """Propiedad cualitativa guarda sus opciones."""
        prop = Propiedad.objects.create(
            nombre_propiedad='RESULTADO_CULTIVO',
            tipo='CUALITATIVO',
            opciones_cualitativas='POSITIVO,NEGATIVO,INDETERMINADO',
        )
        opciones = prop.get_opciones_lista()
        self.assertIn('POSITIVO', opciones)
        self.assertIn('NEGATIVO', opciones)
        self.assertIn('INDETERMINADO', opciones)

    def test_no_permite_nombres_duplicados(self):
        """El sistema rechaza dos propiedades con el mismo nombre."""
        crear_propiedad()
        with self.assertRaises(IntegrityError):
            crear_propiedad()

    def test_editar_propiedad(self):
        """Se puede cambiar la unidad de una propiedad."""
        prop = crear_propiedad()
        prop.unidad = 'mg/dL'
        prop.save()
        self.assertEqual(Propiedad.objects.get(pk=prop.pk).unidad, 'mg/dL')

    def test_eliminar_propiedad(self):
        """Eliminar una propiedad reduce el conteo a cero."""
        prop = crear_propiedad()
        prop.delete()
        self.assertEqual(Propiedad.objects.count(), 0)

    def test_str_propiedad(self):
        """__str__ devuelve el nombre de la propiedad."""
        prop = crear_propiedad('GLUCOSA')
        self.assertEqual(str(prop), 'GLUCOSA')

    def test_opciones_lista_vacia_si_no_hay_opciones(self):
        """get_opciones_lista devuelve lista vacía para propiedad cuantitativa."""
        prop = crear_propiedad()
        self.assertEqual(prop.get_opciones_lista(), [])


# =============================================================================
# PU05c — INTERVALO DE REFERENCIA
# =============================================================================

class PU05c_IntervaloReferencia(TestCase):

    def setUp(self):
        self.prop = crear_propiedad()

    def test_crear_intervalo_adulto(self):
        """Intervalo para adulto (18-25 años = 220-300 meses) se guarda correctamente."""
        intervalo = IntervaloReferencia.objects.create(
            propiedad=self.prop,
            sexo='AMBOS',
            edad_min_meses=220,
            edad_max_meses=300,
            valor_min=4.5,
            valor_max=12.8,
        )
        self.assertEqual(intervalo.valor_min, 4.5)
        self.assertEqual(intervalo.valor_max, 12.8)

    def test_crear_intervalo_nino(self):
        """Intervalo para niños (0-100 meses) se crea correctamente."""
        intervalo = IntervaloReferencia.objects.create(
            propiedad=self.prop,
            sexo='AMBOS',
            edad_min_meses=0,
            edad_max_meses=100,
            valor_min=5.0,
            valor_max=6.0,
        )
        self.assertEqual(IntervaloReferencia.objects.count(), 1)
        self.assertEqual(intervalo.valor_min, 5.0)

    def test_propiedad_tiene_intervalos(self):
        """Los intervalos están asociados correctamente a la propiedad."""
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=220,
            valor_min=4.0, valor_max=11.0,
        )
        self.assertEqual(self.prop.intervalos.count(), 1)

    def test_intervalo_duplicado_rechazado(self):
        """No se permiten dos intervalos con misma propiedad, rango de edad y sexo."""
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=100,
            valor_min=4.0, valor_max=10.0,
        )
        with self.assertRaises(IntegrityError):
            IntervaloReferencia.objects.create(
                propiedad=self.prop, sexo='AMBOS',
                edad_min_meses=0, edad_max_meses=100,
                valor_min=5.0, valor_max=11.0,
            )

    def test_filtro_intervalo_por_edad_adulto(self):
        """Se recupera el intervalo correcto para un adulto de 276 meses."""
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=220, edad_max_meses=300,
            valor_min=4.5, valor_max=12.8,
        )
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=100,
            valor_min=5.0, valor_max=6.0,
        )
        intervalo = self.prop.intervalos.filter(
            edad_min_meses__lte=276,
            edad_max_meses__gte=276,
        ).first()
        self.assertIsNotNone(intervalo)
        self.assertEqual(intervalo.valor_min, 4.5)

    def test_filtro_intervalo_por_sexo(self):
        """Un intervalo FEMENINO no aplica a paciente MASCULINO."""
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='FEMENINO',
            edad_min_meses=0, edad_max_meses=500,
            valor_min=12.0, valor_max=16.0,
        )
        resultado = self.prop.intervalos.filter(sexo='MASCULINO').first()
        self.assertIsNone(resultado)

    def test_editar_intervalo(self):
        """Se puede editar los valores min/max de un intervalo."""
        intervalo = IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=200,
            valor_min=3.0, valor_max=8.0,
        )
        intervalo.valor_min = 3.5
        intervalo.valor_max = 9.0
        intervalo.save()
        actualizado = IntervaloReferencia.objects.get(pk=intervalo.pk)
        self.assertEqual(actualizado.valor_min, 3.5)
        self.assertEqual(actualizado.valor_max, 9.0)

    def test_eliminar_intervalo(self):
        """Eliminar un intervalo reduce el conteo a cero."""
        intervalo = IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=200,
            valor_min=3.0, valor_max=8.0,
        )
        intervalo.delete()
        self.assertEqual(IntervaloReferencia.objects.count(), 0)


# =============================================================================
# PU06 — PLANTILLA PROPIEDAD (orden y sección)
# =============================================================================

class PU06_PlantillaPropiedad(TestCase):

    def setUp(self):
        self.plantilla = crear_plantilla()
        self.prop1 = crear_propiedad('HEMOGLOBINA')
        self.prop2 = crear_propiedad('LEUCOCITOS', unidad='10^3/µL')

    def test_asociar_propiedad_a_plantilla(self):
        """Una propiedad se puede asociar a una plantilla con sección y orden."""
        pp = PlantillaPropiedad.objects.create(
            plantilla=self.plantilla,
            propiedad=self.prop1,
            seccion='FORMULA ROJA',
            orden=1,
            orden_seccion=1,
        )
        self.assertEqual(self.plantilla.propiedades.count(), 1)
        self.assertEqual(pp.seccion, 'FORMULA ROJA')

    def test_str_plantilla_propiedad(self):
        """__str__ de PlantillaPropiedad tiene formato correcto."""
        pp = PlantillaPropiedad.objects.create(
            plantilla=self.plantilla,
            propiedad=self.prop1,
            seccion='FORMULA ROJA',
            orden=1,
            orden_seccion=1,
        )
        self.assertEqual(str(pp), 'BH COMPLETA → HEMOGLOBINA (FORMULA ROJA)')

    def test_dos_propiedades_diferente_seccion(self):
        """Dos propiedades pueden estar en secciones distintas de la misma plantilla."""
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop1,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop2,
            seccion='FORMULA BLANCA', orden=1, orden_seccion=2,
        )
        self.assertEqual(self.plantilla.propiedades.count(), 2)

    def test_duplicado_propiedad_plantilla_rechazado(self):
        """No se puede agregar la misma propiedad dos veces a la misma plantilla."""
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop1,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )
        with self.assertRaises(IntegrityError):
            PlantillaPropiedad.objects.create(
                plantilla=self.plantilla, propiedad=self.prop1,
                seccion='FORMULA ROJA', orden=2, orden_seccion=1,
            )

    def test_eliminar_plantilla_propiedad(self):
        """Se puede quitar una propiedad de una plantilla."""
        pp = PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop1,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )
        pp.delete()
        self.assertEqual(self.plantilla.propiedades.count(), 0)


# =============================================================================
# PU07 — PLANTILLA (crear, unicidad, desactivar, eliminar)
# =============================================================================

class PU07_Plantilla(TestCase):

    def test_crear_plantilla(self):
        """Plantilla se crea activa y con formato correcto."""
        plantilla = Plantilla.objects.create(
            titulo='PLANTILLAPRUEBA',
            tipo_formato='RESULTADOS',
            tipo_muestra='Sangre total con EDTA',
            metodo='Impedancia eléctrica y microscópica',
        )
        self.assertTrue(plantilla.activo)
        self.assertEqual(plantilla.titulo, 'PLANTILLAPRUEBA')
        self.assertEqual(str(plantilla), 'PLANTILLAPRUEBA')

    def test_titulo_unico_plantilla(self):
        """No se pueden crear dos plantillas con el mismo título."""
        crear_plantilla()
        with self.assertRaises(IntegrityError):
            crear_plantilla()

    def test_desactivar_plantilla(self):
        """Una plantilla se puede desactivar sin eliminarla."""
        plantilla = crear_plantilla()
        plantilla.activo = False
        plantilla.save()
        self.assertFalse(Plantilla.objects.get(pk=plantilla.pk).activo)

    def test_reactivar_plantilla(self):
        """Una plantilla desactivada puede volver a activarse."""
        plantilla = crear_plantilla()
        plantilla.activo = False
        plantilla.save()
        plantilla.activo = True
        plantilla.save()
        self.assertTrue(Plantilla.objects.get(pk=plantilla.pk).activo)

    def test_editar_titulo_plantilla(self):
        """Se puede cambiar el título de una plantilla."""
        plantilla = crear_plantilla('Titulo Original')
        plantilla.titulo = 'Titulo Nuevo'
        plantilla.save()
        self.assertEqual(Plantilla.objects.get(pk=plantilla.pk).titulo, 'Titulo Nuevo')

    def test_eliminar_plantilla_sin_analisis(self):
        """Se puede eliminar una plantilla que no tiene análisis."""
        plantilla = crear_plantilla()
        plantilla.delete()
        self.assertEqual(Plantilla.objects.count(), 0)


# =============================================================================
# PU08 — ANÁLISIS (crear, editar status, eliminación en cascada)
# =============================================================================

class PU08_Analisis(TestCase):

    def setUp(self):
        self.lab = crear_lab()
        self.paciente = crear_paciente(self.lab)
        self.plantilla = crear_plantilla()

    def test_crear_analisis_pendiente(self):
        """Un Análisis se crea con status PENDIENTE por defecto."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=self.plantilla,
        )
        self.assertEqual(analisis.status, 'PENDIENTE')

    def test_cambiar_status_a_completado(self):
        """El status del análisis se puede cambiar a COMPLETADO."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=self.plantilla,
        )
        analisis.status = 'COMPLETADO'
        analisis.save()
        self.assertEqual(Analisis.objects.get(pk=analisis.pk).status, 'COMPLETADO')

    def test_cambiar_status_a_cancelado(self):
        """El status del análisis se puede cambiar a CANCELADO."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=self.plantilla,
        )
        analisis.status = 'CANCELADO'
        analisis.save()
        self.assertEqual(Analisis.objects.get(pk=analisis.pk).status, 'CANCELADO')

    def test_str_analisis(self):
        """__str__ del análisis incluye el ID y el nombre del paciente."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=self.plantilla,
        )
        self.assertIn(str(analisis.id), str(analisis))
        self.assertIn(self.paciente.nombre, str(analisis))

    def test_eliminar_analisis(self):
        """Eliminar un análisis reduce el conteo a cero."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=self.plantilla,
        )
        analisis.delete()
        self.assertEqual(Analisis.objects.count(), 0)

    def test_eliminar_analisis_elimina_resultados(self):
        """Al eliminar un análisis sus ResultadoAnalisis se eliminan en cascada."""
        prop = crear_propiedad()
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=prop,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        self.assertGreater(ResultadoAnalisis.objects.count(), 0)
        analisis.delete()
        self.assertEqual(ResultadoAnalisis.objects.count(), 0)

    def test_analisis_sin_plantilla(self):
        """Se puede crear un análisis sin plantilla asignada."""
        analisis = Analisis.objects.create(
            paciente=self.paciente,
            plantilla=None,
        )
        self.assertIsNone(analisis.plantilla)

    def test_multiples_analisis_por_paciente(self):
        """Un mismo paciente puede tener varios análisis."""
        plantilla2 = Plantilla.objects.create(titulo='ORINA COMPLETA', tipo_formato='RESULTADOS')
        Analisis.objects.create(paciente=self.paciente, plantilla=self.plantilla)
        Analisis.objects.create(paciente=self.paciente, plantilla=plantilla2)
        self.assertEqual(Analisis.objects.filter(paciente=self.paciente).count(), 2)


# =============================================================================
# PU09 — RESULTADO ANÁLISIS (señal, herencia de sección, asignar valor)
# =============================================================================

class PU09_ResultadoAnalisis(TestCase):

    def setUp(self):
        self.lab = crear_lab()
        self.paciente = crear_paciente(
            self.lab,
            nacimiento=date(date.today().year - 23, 1, 1),
        )
        self.prop = crear_propiedad()
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=220, edad_max_meses=300,
            valor_min=4.5, valor_max=12.8,
        )
        self.plantilla = crear_plantilla()
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )

    def test_crear_analisis_genera_resultado(self):
        """Al crear un Análisis la señal genera automáticamente ResultadoAnalisis."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla, status='PENDIENTE'
        )
        resultados = ResultadoAnalisis.objects.filter(analisis=analisis)
        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first().propiedad, self.prop)

    def test_resultado_hereda_seccion(self):
        """El ResultadoAnalisis hereda la sección de PlantillaPropiedad."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        resultado = ResultadoAnalisis.objects.get(analisis=analisis)
        self.assertEqual(resultado.seccion, 'FORMULA ROJA')

    def test_resultado_hereda_orden_seccion(self):
        """El ResultadoAnalisis hereda el orden de sección de PlantillaPropiedad."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        resultado = ResultadoAnalisis.objects.get(analisis=analisis)
        self.assertEqual(resultado.orden_seccion, 1)

    def test_resultado_hereda_nombre_propiedad(self):
        """El campo nombre_propiedad se completa automáticamente al guardar."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        resultado = ResultadoAnalisis.objects.get(analisis=analisis)
        self.assertEqual(resultado.nombre_propiedad, 'HEMOGLOBINA')

    def test_asignar_valor_a_resultado(self):
        """Se puede asignar un valor numérico al ResultadoAnalisis."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        resultado = ResultadoAnalisis.objects.get(analisis=analisis)
        resultado.valor = '13.5'
        resultado.save()
        self.assertEqual(ResultadoAnalisis.objects.get(pk=resultado.pk).valor, '13.5')

    def test_str_resultado(self):
        """__str__ del resultado muestra nombre y valor."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        resultado = ResultadoAnalisis.objects.get(analisis=analisis)
        resultado.valor = '14.2'
        resultado.save()
        self.assertIn('14.2', str(resultado))

    def test_resultado_duplicado_rechazado(self):
        """No se pueden crear dos ResultadoAnalisis para el mismo análisis y propiedad."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        with self.assertRaises(IntegrityError):
            ResultadoAnalisis.objects.create(
                analisis=analisis, propiedad=self.prop, valor='1.0'
            )

    def test_senal_no_actua_en_actualizacion(self):
        """La señal solo se ejecuta al crear, no al actualizar el análisis."""
        analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )
        conteo_inicial = ResultadoAnalisis.objects.filter(analisis=analisis).count()
        analisis.status = 'COMPLETADO'
        analisis.save()
        self.assertEqual(
            ResultadoAnalisis.objects.filter(analisis=analisis).count(),
            conteo_inicial,
        )

    def test_intervalo_por_edad_adulto(self):
        """El intervalo 4.5-12.8 aplica a un adulto de 23 años (~276 meses)."""
        edad_meses = self.paciente.edad_en_meses
        intervalo = self.prop.intervalos.filter(
            edad_min_meses__lte=edad_meses,
            edad_max_meses__gte=edad_meses,
        ).first()
        self.assertIsNotNone(intervalo)
        self.assertEqual(intervalo.valor_min, 4.5)
        self.assertEqual(intervalo.valor_max, 12.8)

    def test_intervalo_por_edad_nino(self):
        """El intervalo 5.0-6.0 aplica a un niño de 5 años (~60 meses)."""
        IntervaloReferencia.objects.create(
            propiedad=self.prop, sexo='AMBOS',
            edad_min_meses=0, edad_max_meses=100,
            valor_min=5.0, valor_max=6.0,
        )
        paciente_nino = crear_paciente(
            self.lab, nombre='Nino', ap='Test',
            nacimiento=date(date.today().year - 5, 1, 1),
        )
        edad_meses = paciente_nino.edad_en_meses
        intervalo = self.prop.intervalos.filter(
            edad_min_meses__lte=edad_meses,
            edad_max_meses__gte=edad_meses,
        ).first()
        self.assertIsNotNone(intervalo)
        self.assertEqual(intervalo.valor_min, 5.0)
        self.assertEqual(intervalo.valor_max, 6.0)

    def test_sin_intervalo_para_edad_fuera_de_rango(self):
        """Un paciente con edad fuera de todos los rangos no obtiene intervalo."""
        paciente_centenario = crear_paciente(
            self.lab, nombre='Centenario', ap='Test',
            nacimiento=date(1900, 1, 1),
        )
        edad_meses = paciente_centenario.edad_en_meses
        intervalo = self.prop.intervalos.filter(
            edad_min_meses__lte=edad_meses,
            edad_max_meses__gte=edad_meses,
        ).first()
        self.assertIsNone(intervalo)


# =============================================================================
# PU10 — PROPIEDADES EXTRA (agregar, señal, get_propiedades_efectivas)
# =============================================================================

class PU10_PropiedadesExtra(TestCase):

    def setUp(self):
        self.lab = crear_lab()
        self.paciente = crear_paciente(
            self.lab, nacimiento=date(date.today().year - 30, 1, 1)
        )
        self.prop_base = crear_propiedad('HEMOGLOBINA')
        self.prop_extra = crear_propiedad('GLUCOSA', unidad='mg/dL')
        self.plantilla = crear_plantilla()
        PlantillaPropiedad.objects.create(
            plantilla=self.plantilla, propiedad=self.prop_base,
            seccion='FORMULA ROJA', orden=1, orden_seccion=1,
        )
        self.analisis = Analisis.objects.create(
            paciente=self.paciente, plantilla=self.plantilla,
        )

    def test_agregar_propiedad_extra(self):
        """Una propiedad extra se puede asociar a un análisis existente."""
        AnalisisPropiedadExtra.objects.create(
            analisis=self.analisis,
            propiedad=self.prop_extra,
            seccion='QUIMICA SANGUINEA',
            orden=1,
            orden_seccion=2,
        )
        self.assertEqual(self.analisis.propiedades_extra.count(), 1)

    def test_senal_crea_resultado_para_propiedad_extra(self):
        """La señal crea automáticamente un ResultadoAnalisis al agregar propiedad extra."""
        conteo_antes = ResultadoAnalisis.objects.filter(analisis=self.analisis).count()
        AnalisisPropiedadExtra.objects.create(
            analisis=self.analisis,
            propiedad=self.prop_extra,
            seccion='QUIMICA SANGUINEA',
            orden=1,
            orden_seccion=2,
        )
        conteo_despues = ResultadoAnalisis.objects.filter(analisis=self.analisis).count()
        self.assertEqual(conteo_despues, conteo_antes + 1)

    def test_get_propiedades_efectivas_incluye_base_y_extra(self):
        """get_propiedades_efectivas devuelve propiedades de plantilla y extra."""
        AnalisisPropiedadExtra.objects.create(
            analisis=self.analisis, propiedad=self.prop_extra,
            orden=1, orden_seccion=2,
        )
        efectivas = self.analisis.get_propiedades_efectivas()
        ids = list(efectivas.values_list('id', flat=True))
        self.assertIn(self.prop_base.id, ids)
        self.assertIn(self.prop_extra.id, ids)

    def test_propiedad_extra_duplicada_rechazada(self):
        """No se puede agregar la misma propiedad extra dos veces al mismo análisis."""
        AnalisisPropiedadExtra.objects.create(
            analisis=self.analisis, propiedad=self.prop_extra,
            orden=1, orden_seccion=2,
        )
        with self.assertRaises(IntegrityError):
            AnalisisPropiedadExtra.objects.create(
                analisis=self.analisis, propiedad=self.prop_extra,
                orden=2, orden_seccion=2,
            )


# =============================================================================
# PU11 — GENERACIÓN PDF
# =============================================================================

class PU11_GeneracionPDF(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_pdf', password='Admin123!', email='pdf@test.com'
        )
        self.client.force_login(self.admin_user)

        lab = crear_lab()
        paciente = crear_paciente(lab, nacimiento=date(2000, 1, 1))
        plantilla = crear_plantilla('PLANTILLA PDF')
        self.analisis = Analisis.objects.create(
            paciente=paciente, plantilla=plantilla, status='PENDIENTE'
        )

    def test_url_pdf_existe(self):
        """La URL de generación de PDF responde sin error 404."""
        response = self.client.get(
            f'/admin_ext/analisis/{self.analisis.pk}/generar_pdf/'
        )
        self.assertNotEqual(response.status_code, 404)

    def test_url_pdf_requiere_login(self):
        """Sin autenticación la URL del PDF redirige al login."""
        cliente_sin_login = Client()
        response = cliente_sin_login.get(
            f'/admin_ext/analisis/{self.analisis.pk}/generar_pdf/'
        )
        self.assertEqual(response.status_code, 302)

    def test_pdf_analisis_inexistente_retorna_404(self):
        """Solicitar PDF de un análisis que no existe debe retornar 404."""
        response = self.client.get('/admin_ext/analisis/99999/generar_pdf/')
        self.assertEqual(response.status_code, 404)