from django.db import models
from django.contrib.auth.hashers import make_password, check_password, is_password_usable
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q 
import os
from datetime import date

# =============================================================================
# 1. TABLAS PRINCIPALES
# =============================================================================

class Laboratorio(models.Model):
    nombre_laboratorio = models.CharField(max_length=150)
    ciudad = models.CharField(max_length=100, null=True, blank=True) 
    estado = models.CharField(max_length=100, null=True, blank=True)
    codigo_postal = models.CharField(max_length=20, null=True, blank=True)
    pais = models.CharField(max_length=100, null=True, blank=True)
    logo = models.ImageField(upload_to='logos_laboratorios/', null=True, blank=True)
    
    #Se agrego responsable sanitario principal para mostrarlo en el PDF.
    responsable_sanitario_principal = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='labs_bajo_cargo'
    )

    def save(self, *args, **kwargs):
        if self.logo:
            print(f"DEBUG: Intentando guardar logo para Laboratorio: {self.nombre_laboratorio}")
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            print(f"❌ ERROR CRÍTICO AL GUARDAR LABORATORIO: {e}")
            raise e

    def __str__(self):
        return f"{self.nombre_laboratorio}"

class Usuario(models.Model):
    ROLES = [("NORMAL", "Normal"), ("TECNICO", "Técnico"), ("ADMIN", "Administrador")]
    nombre = models.CharField(max_length=150)
    correo_electronico = models.EmailField(unique=True)
    num_telefono = models.CharField(max_length=20, null=True, blank=True)
    rol = models.CharField(max_length=10, choices=ROLES, default="NORMAL")
    is_active = models.BooleanField(default=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    laboratorios = models.ManyToManyField(Laboratorio, related_name='usuarios', blank=True)

    # ✅ PUNTO 2: Campos Profesionales para PDF
    puesto = models.CharField(max_length=100, blank=True, null=True) # Ej: Responsable Sanitario
    titulo_abreviado = models.CharField(max_length=20, blank=True, null=True) # Ej: Q.F.B.
    cedula_profesional = models.CharField(max_length=50, blank=True, null=True)
    cedula_especialidad = models.CharField(max_length=50, blank=True, null=True)
    registro_ssg = models.CharField(max_length=50, blank=True, null=True)
    universidad_egreso = models.CharField(max_length=150, blank=True, null=True)
    firma_digital = models.ImageField(upload_to='firmas/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.password and not is_password_usable(self.password):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password: return False
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.nombre} ({self.correo_electronico})"

class Paciente(models.Model):
    SEXO_CHOICES = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino")]
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.CASCADE, related_name="pacientes")
    
    # ✅ PUNTO 1: Nombres divididos
    nombre = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True, null=True)
    
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=SEXO_CHOICES, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    correo_electronico = models.EmailField(blank=True, null=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

    @property
    def edad(self):
        if self.fecha_nacimiento:
            today = date.today()
            return today.year - self.fecha_nacimiento.year - ((today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        return 0

    def __str__(self):
        return self.nombre_completo

# =============================================================================
# 2. SISTEMA DE PLANTILLAS Y LOINC
# =============================================================================

class LoincCode(models.Model):
    loinc_num = models.CharField(max_length=20, unique=True)
    shortname = models.CharField(max_length=255, null=True, blank=True)
    component = models.TextField(null=True, blank=True)
    property = models.CharField(max_length=50, null=True, blank=True)
    system = models.CharField(max_length=100, null=True, blank=True)
    scale_typ = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.loinc_num} - {self.shortname}"

class Plantilla(models.Model):
    FORMATOS = [
        ('RESULTADOS', 'Resultados (Solo propiedades y valores)'),
        ('IMAGENES_RESULTADOS', 'Imágenes y Resultados'),
        ('RECETA_JUSTIFICADA', 'Receta Justificada (Solo texto)'),
    ]
    titulo = models.CharField(max_length=150, unique=True)
    tipo_formato = models.CharField(max_length=50, choices=FORMATOS, default='RESULTADOS')
    texto_justificado_default = models.TextField(blank=True, null=True)
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo

class PropiedadPlantilla(models.Model):
    plantilla = models.ForeignKey(Plantilla, on_delete=models.CASCADE, related_name="propiedades")
    nombre_propiedad = models.CharField(max_length=100)
    loinc_code = models.ForeignKey(LoincCode, on_delete=models.PROTECT, null=True, blank=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre_propiedad}"
    
    class Meta:
        unique_together = ('plantilla', 'nombre_propiedad')

class IntervaloReferencia(models.Model):
    propiedad = models.ForeignKey(PropiedadPlantilla, on_delete=models.CASCADE, related_name="intervalos")
    EDADES = [("NINO", "Niño"), ("ADULTO", "Adulto"), ("ADULTO_MAYOR", "Adulto Mayor")]
    SEXOS = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino"), ("AMBOS", "Ambos")]
    grupo_edad = models.CharField(max_length=20, choices=EDADES, null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=SEXOS, default="AMBOS", null=True, blank=True)
    valor_min = models.FloatField(null=True, blank=True)
    valor_max = models.FloatField(null=True, blank=True)
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('propiedad', 'grupo_edad', 'sexo')

# =============================================================================
# 3. ANÁLISIS, RESULTADOS Y REPORTES
# =============================================================================

class Analisis(models.Model):
    STATUS_CHOICES = [("PENDIENTE", "Pendiente"), ("COMPLETADO", "Completado"), ("CANCELADO", "Cancelado")]
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, related_name='analisis', null=True, blank=True)
    creado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDIENTE")
    fecha_analisis = models.DateTimeField(auto_now_add=True)
    fecha_muestra = models.DateField(null=True, blank=True)
    hora_toma = models.TimeField(null=True, blank=True)
    hora_impresion = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"Análisis {self.id} - {self.paciente.nombre_completo}"

class ResultadoAnalisis(models.Model):
    analisis = models.ForeignKey(Analisis, on_delete=models.CASCADE, related_name='resultados')
    loinc_code = models.ForeignKey(LoincCode, on_delete=models.PROTECT, null=True, blank=True)
    nombre_propiedad = models.CharField(max_length=100, null=True, blank=True)
    valor = models.CharField(max_length=100, blank=True, null=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    valor_blob1 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)
    valor_blob2 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.valor_blob1 or self.valor_blob2:
            print(f"DEBUG: Intentando guardar imagen en ResultadoAnalisis ID: {self.id or 'Nuevo'}")
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            print(f"❌ ERROR CRÍTICO AL GUARDAR RESULTADO ANALISIS: {e}")
            raise e

    def __str__(self):
        return f"{self.nombre_propiedad}: {self.valor}"

class Reporte(models.Model):
    analisis = models.ForeignKey(Analisis, on_delete=models.CASCADE, related_name="reportes")
    generado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)

# =============================================================================
# 4. SEÑALES
# =============================================================================

@receiver(post_save, sender=Analisis)
def crear_resultados_predeterminados(sender, instance, created, **kwargs):
    if created and instance.plantilla and instance.plantilla.tipo_formato != 'RECETA_JUSTIFICADA':
        for propiedad in instance.plantilla.propiedades.all():
            ResultadoAnalisis.objects.create(
                analisis=instance,
                loinc_code=propiedad.loinc_code,
                nombre_propiedad=propiedad.nombre_propiedad,
                valor='',
                unidad=propiedad.unidad
            )  

