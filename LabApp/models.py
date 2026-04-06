from django.db import models
from django.contrib.auth.hashers import make_password, check_password, is_password_usable
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q

from datetime import date


# =============================================================================
# LABORATORIO Y USUARIO
# =============================================================================

class Laboratorio(models.Model):
    nombre_laboratorio = models.CharField(max_length=150)
    ciudad             = models.CharField(max_length=100, null=True, blank=True)
    estado             = models.CharField(max_length=100, null=True, blank=True)
    codigo_postal      = models.CharField(max_length=20,  null=True, blank=True)
    pais               = models.CharField(max_length=100, null=True, blank=True)
    logo               = models.ImageField(upload_to='logos_laboratorios/', null=True, blank=True)

    responsable_sanitario_principal = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='labs_bajo_cargo'
    )

    def __str__(self):
        return self.nombre_laboratorio


class Usuario(models.Model):
    ROLES = [("NORMAL", "Normal"), ("TECNICO", "Técnico"), ("ADMIN", "Administrador")]

    nombre               = models.CharField(max_length=150)
    correo_electronico   = models.EmailField(unique=True)
    num_telefono         = models.CharField(max_length=20, null=True, blank=True)
    rol                  = models.CharField(max_length=10, choices=ROLES, default="NORMAL")
    is_active            = models.BooleanField(default=True)
    password             = models.CharField(max_length=255, null=True, blank=True)
    laboratorios         = models.ManyToManyField(Laboratorio, related_name='usuarios', blank=True)

    puesto               = models.CharField(max_length=100, blank=True, null=True)
    titulo_abreviado     = models.CharField(max_length=20,  blank=True, null=True)
    cedula_profesional   = models.CharField(max_length=50,  blank=True, null=True)
    cedula_especialidad  = models.CharField(max_length=50,  blank=True, null=True)
    registro_ssg         = models.CharField(max_length=50,  blank=True, null=True)
    universidad_egreso   = models.CharField(max_length=150, blank=True, null=True)
    firma_digital        = models.ImageField(upload_to='firmas/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.password and not is_password_usable(self.password):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.nombre} ({self.correo_electronico})"


# =============================================================================
# PACIENTE
# =============================================================================

class Paciente(models.Model):
    SEXO_CHOICES = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino")]

    laboratorio        = models.ForeignKey(Laboratorio, on_delete=models.CASCADE, related_name="pacientes")
    nombre             = models.CharField(max_length=100)
    apellido_paterno   = models.CharField(max_length=100)
    apellido_materno   = models.CharField(max_length=100, blank=True, null=True)
    fecha_nacimiento   = models.DateField(null=True, blank=True)
    sexo               = models.CharField(max_length=10, choices=SEXO_CHOICES, null=True, blank=True)
    telefono           = models.CharField(max_length=20, null=True, blank=True)
    correo_electronico = models.EmailField(blank=True, null=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

    @property
    def edad(self):
        if self.fecha_nacimiento:
            today = date.today()
            return (
                today.year - self.fecha_nacimiento.year
                - ((today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
            )
        return 0

    @property
    def edad_en_meses(self):
        if self.fecha_nacimiento:
            today  = date.today()
            meses  = (today.year - self.fecha_nacimiento.year) * 12
            meses += today.month - self.fecha_nacimiento.month
            if today.day < self.fecha_nacimiento.day:
                meses -= 1
            return max(meses, 0)
        return 0

    def __str__(self):
        return self.nombre_completo


# =============================================================================
# LOINC
# =============================================================================

class LoincCode(models.Model):
    loinc_num  = models.CharField(max_length=20, unique=True)
    shortname  = models.CharField(max_length=255, null=True, blank=True)
    component  = models.TextField(null=True, blank=True)
    property   = models.CharField(max_length=50,  null=True, blank=True)
    system     = models.CharField(max_length=100, null=True, blank=True)
    scale_typ  = models.CharField(max_length=20,  null=True, blank=True)

    def __str__(self):
        return f"{self.loinc_num} - {self.shortname}"


# =============================================================================
# PROPIEDAD
# =============================================================================

class Propiedad(models.Model):
    TIPO_CHOICES = [
        ('CUANTITATIVO', 'Cuantitativo'),
        ('CUALITATIVO',  'Cualitativo'),
    ]

    nombre_propiedad      = models.CharField(max_length=100, unique=True)
    loinc_code            = models.ForeignKey(
        LoincCode, on_delete=models.PROTECT, null=True, blank=True
    )
    tipo                  = models.CharField(
        max_length=15, choices=TIPO_CHOICES, default='CUANTITATIVO',
    )
    unidad                = models.CharField(max_length=20, null=True, blank=True)
    opciones_cualitativas = models.CharField(max_length=500, null=True, blank=True)
    sincronizado          = models.BooleanField(default=False)
    fecha_modificacion    = models.DateTimeField(auto_now=True)

    def get_opciones_lista(self):
        if self.opciones_cualitativas:
            return [o.strip() for o in self.opciones_cualitativas.split(',') if o.strip()]
        return []

    def __str__(self):
        return self.nombre_propiedad

    class Meta:
        verbose_name        = 'Propiedad'
        verbose_name_plural = 'Propiedades'
        ordering            = ['nombre_propiedad']


# =============================================================================
# INTERVALO DE REFERENCIA
# =============================================================================

class IntervaloReferencia(models.Model):
    SEXOS = [("MASCULINO", "Masculino"), ("FEMENINO", "Femenino"), ("AMBOS", "Ambos")]

    propiedad          = models.ForeignKey(Propiedad, on_delete=models.CASCADE, related_name="intervalos")
    sexo               = models.CharField(max_length=10, choices=SEXOS, default="AMBOS", null=True, blank=True)
    edad_min_meses     = models.PositiveSmallIntegerField(null=True, blank=True)
    edad_max_meses     = models.PositiveSmallIntegerField(null=True, blank=True)
    valor_min          = models.FloatField(null=True, blank=True)
    valor_max          = models.FloatField(null=True, blank=True)
    sincronizado       = models.BooleanField(default=False)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('propiedad', 'edad_min_meses', 'edad_max_meses', 'sexo')


# =============================================================================
# PLANTILLA
# =============================================================================

class Plantilla(models.Model):
    FORMATOS = [
        ('RESULTADOS',          'Resultados (Solo propiedades y valores)'),
        ('IMAGENES_RESULTADOS', 'Imágenes y Resultados'),
    ]

    titulo                    = models.CharField(max_length=150, unique=True)
    tipo_formato              = models.CharField(max_length=50, choices=FORMATOS, default='RESULTADOS')
    texto_justificado_default = models.TextField(blank=True, null=True)
    sincronizado              = models.BooleanField(default=False)
    fecha_modificacion        = models.DateTimeField(auto_now=True)

    propiedades = models.ManyToManyField(
        Propiedad,
        related_name='plantillas',
        blank=True,
    )

    def __str__(self):
        return self.titulo


# =============================================================================
# ANÁLISIS
# =============================================================================

class Analisis(models.Model):
    STATUS_CHOICES = [
        ("PENDIENTE",  "Pendiente"),
        ("COMPLETADO", "Completado"),
        ("CANCELADO",  "Cancelado"),
    ]

    paciente   = models.ForeignKey(Paciente,  on_delete=models.CASCADE)
    plantilla  = models.ForeignKey(Plantilla, on_delete=models.PROTECT, related_name='analisis', null=True, blank=True)
    creado_por = models.ForeignKey(Usuario,   on_delete=models.SET_NULL, null=True, blank=True)
    status     = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDIENTE")

    fecha_analisis = models.DateTimeField(auto_now_add=True)
    fecha_muestra  = models.DateField(null=True, blank=True)
    hora_toma      = models.TimeField(null=True, blank=True)
    hora_impresion = models.TimeField(null=True, blank=True)

    tipo_muestra = models.CharField(max_length=150, null=True, blank=True)
    metodo       = models.CharField(max_length=200, null=True, blank=True)

    imagen_resultado1 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)
    imagen_resultado2 = models.ImageField(upload_to='resultados_imagenes/', null=True, blank=True)

    propiedades_extra = models.ManyToManyField(
        Propiedad, related_name='analisis_extra', blank=True,
    )
    propiedades_excluidas = models.ManyToManyField(
        Propiedad, related_name='analisis_excluidos', blank=True,
    )

    def get_propiedades_efectivas(self):
        base          = self.plantilla.propiedades.all() if self.plantilla else Propiedad.objects.none()
        extra         = self.propiedades_extra.all()
        excluidas_ids = self.propiedades_excluidas.values_list('id', flat=True)
        return (base | extra).exclude(id__in=excluidas_ids).distinct()

    def __str__(self):
        return f"Análisis {self.id} - {self.paciente.nombre_completo}"


# =============================================================================
# RESULTADO ANÁLISIS
# =============================================================================

class ResultadoAnalisis(models.Model):
    analisis   = models.ForeignKey(Analisis,  on_delete=models.CASCADE,  related_name='resultados')
    propiedad  = models.ForeignKey(Propiedad, on_delete=models.PROTECT,   related_name='resultados')
    loinc_code = models.ForeignKey(LoincCode, on_delete=models.PROTECT,   null=True, blank=True)
    valor      = models.CharField(max_length=100, blank=True, null=True)
    unidad     = models.CharField(max_length=20,  null=True, blank=True)

    # ─── CORRECCIÓN BUG 1 ────────────────────────────────────────────────────
    # nombre_propiedad ahora es un campo real en la BD, no un @property.
    # Esto permite que el Admin lo muestre correctamente en el inline,
    # que se pueda filtrar/ordenar, y que la sincronización local sea exacta.
    # Se auto-puebla desde la FK en save() si no viene explícito.
    nombre_propiedad = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Nombre propiedad",
        help_text="Se completa automáticamente desde la FK propiedad al guardar."
    )
    # ─────────────────────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        # Siempre sincronizar nombre_propiedad con la FK para mantener consistencia.
        # Si la propiedad cambia de nombre en el futuro, los resultados históricos
        # conservan el nombre que tenían al momento de crearse (snapshot).
        # Para forzar actualización, pasar force_update_nombre=True.
        force_update = kwargs.pop('force_update_nombre', False)
        if (not self.nombre_propiedad or force_update) and self.propiedad_id:
            try:
                self.nombre_propiedad = self.propiedad.nombre_propiedad
            except Propiedad.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = self.nombre_propiedad or (self.propiedad.nombre_propiedad if self.propiedad_id else '?')
        return f"{nombre}: {self.valor}"

    class Meta:
        unique_together = ('analisis', 'propiedad')


# =============================================================================
# SEÑAL — crea ResultadoAnalisis al guardar un Análisis nuevo
# =============================================================================

@receiver(post_save, sender=Analisis)
def crear_resultados_predeterminados(sender, instance, created, **kwargs):
    """
    Crea ResultadoAnalisis automáticamente al guardar un Análisis nuevo.

    Se desactiva en dos casos:
      - skip_signal=True  → viene del admin de Django (el admin los crea manualmente)
      - _desde_api=True   → viene del serializer/API REST (el cliente manda los
                            resultados explícitamente, no hay que auto-generarlos)

    De esta forma las propiedades que el usuario excluyó en la app de escritorio
    NO aparecen como resultados vacíos en el admin.
    """
    # Guard 1: admin de Django lo maneja solo
    if getattr(instance, 'skip_signal', False):
        return

    # Guard 2: API REST / serializer — el cliente ya mandó los resultados exactos
    if getattr(instance, '_desde_api', False):
        return

    if not created:
        return

    if not instance.plantilla:
        return

    paciente   = instance.paciente
    edad_meses = paciente.edad_en_meses

    for propiedad in instance.plantilla.propiedades.all():
        total_intervalos = propiedad.intervalos.count()

        if total_intervalos == 0:
            crear = True
        else:
            crear = propiedad.intervalos.filter(
                Q(sexo=paciente.sexo) | Q(sexo="AMBOS")
            ).filter(
                Q(edad_min_meses__isnull=True) | Q(edad_min_meses__lte=edad_meses)
            ).filter(
                Q(edad_max_meses__isnull=True) | Q(edad_max_meses__gte=edad_meses)
            ).exists()

        if crear:
            ResultadoAnalisis.objects.get_or_create(
                analisis=instance,
                propiedad=propiedad,
                defaults={
                    'loinc_code':        propiedad.loinc_code,
                    'nombre_propiedad':  propiedad.nombre_propiedad,   # ← CORRECCIÓN BUG 1
                    'valor':             '',
                    'unidad':            propiedad.unidad,
                }
            )
