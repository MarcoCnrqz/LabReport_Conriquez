from django.db import models
from django.contrib.auth.hashers import make_password, check_password, is_password_usable
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q 

# =============================================================================
# 1. TABLAS PRINCIPALES (Laboratorio, Usuario, Paciente, Pago)
# =============================================================================

class Laboratorio(models.Model):
    nombre_laboratorio = models.CharField(max_length=150)
    ciudad = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=100, null=True, blank=True)
    codigo_postal = models.CharField(max_length=20, null=True, blank=True)
    pais = models.CharField(max_length=100, null=True, blank=True)
    logo = models.ImageField(upload_to='logos_laboratorios/', null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_laboratorio}"

class Usuario(models.Model):
    nombre = models.CharField(max_length=150)
    correo_electronico = models.EmailField(unique=True)
    num_telefono = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    
    laboratorios = models.ManyToManyField(Laboratorio, related_name='usuarios', blank=True)

    # --- CORRECCIÓN DE CONTRASEÑAS ---

    def save(self, *args, **kwargs):
        # Encripta automáticamente al guardar si la contraseña viene en texto plano
        if self.password and not is_password_usable(self.password):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        # Este método es OBLIGATORIO para que el Admin de Django pueda cambiar contraseñas
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        # Este método lo usa la API para validar el login
        if not self.password: return False
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.nombre} ({self.correo_electronico})"

class Paciente(models.Model):
    SEXO_CHOICES = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino")]
    
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.CASCADE, related_name="pacientes")
    nombre = models.CharField(max_length=150)
    edad = models.PositiveIntegerField()
    sexo = models.CharField(max_length=10, choices=SEXO_CHOICES, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    correo_electronico = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre}"

class Pago(models.Model):
    ESTADOS = [("PAGADO", "Pagado"), ("VENCIDO", "Vencido"), ("PENDIENTE", "Pendiente")]
    
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="pagos")
    fecha_pago = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, null=True, blank=True)

    def __str__(self):
        return f"Pago {self.estado} - {self.usuario.nombre}"

# =============================================================================
# 2. SISTEMA DE PLANTILLAS Y LOINC (CON SINCRONIZACIÓN)
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

    # 🌟 CAMPOS PARA SINCRONIZACIÓN 🌟
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    # ---------------------------------

    def __str__(self):
        return self.titulo

class PropiedadPlantilla(models.Model):
    plantilla = models.ForeignKey(Plantilla, on_delete=models.CASCADE, related_name="propiedades")
    nombre_propiedad = models.CharField(max_length=100)
    loinc_code = models.ForeignKey(LoincCode, on_delete=models.PROTECT, null=True, blank=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)

    # 🌟 CAMPOS PARA SINCRONIZACIÓN 🌟
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    # ---------------------------------

    def __str__(self):
        return f"{self.nombre_propiedad}"
    
    class Meta:
        unique_together = ('plantilla', 'nombre_propiedad') # Evita propiedades duplicadas en una misma plantilla

class IntervaloReferencia(models.Model):
    propiedad = models.ForeignKey(PropiedadPlantilla, on_delete=models.CASCADE, related_name="intervalos")
    
    EDADES = [("NINO", "Niño"), ("ADULTO", "Adulto"), ("ADULTO_MAYOR", "Adulto Mayor")]
    SEXOS = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino"), ("AMBOS", "Ambos")]
    
    grupo_edad = models.CharField(max_length=20, choices=EDADES, null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=SEXOS, default="AMBOS", null=True, blank=True)
    valor_min = models.FloatField(null=True, blank=True)
    valor_max = models.FloatField(null=True, blank=True)

    # 🌟 CAMPOS PARA SINCRONIZACIÓN 🌟
    sincronizado = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    # ---------------------------------
    
    class Meta:
        # Asegura que solo haya un intervalo por propiedad, edad y sexo
        unique_together = ('propiedad', 'grupo_edad', 'sexo')

# =============================================================================
# 3. ANÁLISIS, RESULTADOS Y REPORTES
# =============================================================================

class Analisis(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, related_name='analisis', null=True, blank=True)
    fecha_analisis = models.DateTimeField(auto_now_add=True)
    fecha_muestra = models.DateField(null=True, blank=True)
    hora_toma = models.TimeField(null=True, blank=True)
    hora_impresion = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"Análisis {self.id} - {self.paciente.nombre}"

class ResultadoAnalisis(models.Model):
    analisis = models.ForeignKey(Analisis, on_delete=models.CASCADE, related_name='resultados')
    loinc_code = models.ForeignKey(LoincCode, on_delete=models.PROTECT, null=True, blank=True)
    nombre_propiedad = models.CharField(max_length=100, null=True, blank=True)
    valor = models.CharField(max_length=100, blank=True, null=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    
    # Imagenes para la nube (Django maneja esto como rutas de archivos)
    valor_blob1 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)
    valor_blob2 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_propiedad}: {self.valor}"

class Reporte(models.Model):
    analisis = models.ForeignKey(Analisis, on_delete=models.CASCADE, related_name="reportes")
    generado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reporte {self.id}"

# =============================================================================
# 4. SEÑALES (Creación automática de resultados)
# =============================================================================

@receiver(post_save, sender=Analisis)
def crear_resultados_predeterminados(sender, instance, created, **kwargs):
    if created and instance.plantilla and instance.plantilla.tipo_formato != 'RECETA_JUSTIFICADA':
        paciente = instance.paciente
        sexo_paciente = paciente.sexo
        
        # Determinar grupo de edad
        if paciente.edad <= 18: 
            grupo_edad = "NINO"
        elif paciente.edad <= 59: 
            grupo_edad = "ADULTO"
        else: 
            grupo_edad = "ADULTO_MAYOR"

        for propiedad in instance.plantilla.propiedades.all():
            # Buscar el intervalo de referencia más específico para el paciente
            intervalo = propiedad.intervalos.filter(grupo_edad=grupo_edad).filter(
                Q(sexo=sexo_paciente) | Q(sexo="AMBOS")
            ).first()
            
            ResultadoAnalisis.objects.create(
                analisis=instance,
                loinc_code=propiedad.loinc_code,
                nombre_propiedad=propiedad.nombre_propiedad,
                valor='',
                unidad=propiedad.unidad
            )