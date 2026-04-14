import os
import pandas as pd

from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

from LabApp.models import LoincCode


# =============================================================================
# CLASES LOINC DE LABORATORIO CLÍNICO HUMANO (lista blanca estricta)
# Fuente: https://loinc.org/kb/users-guide/loinc-classess/
# Solo se aceptan códigos cuya CLASS esté en esta lista.
# Esto es mucho más preciso que filtrar por SYSTEM, porque CLASS es la
# categoría oficial que LOINC asigna a cada código.
# =============================================================================
CLASES_LABORATORIO = {
    # ── Hematología ──────────────────────────────────────────────────────────
    'HEM/BC',       # Hematología / Biometría hemática
    'COAG',         # Coagulación
    'RETIC',        # Reticulocitos

    # ── Química clínica / Bioquímica ─────────────────────────────────────────
    'CHEM',         # Química clínica general
    'DRUG/TOX',     # Fármacos y toxicología
    'ABXBACT',      # Susceptibilidad antibiótica

    # ── Orina / Urianálisis ──────────────────────────────────────────────────
    'UA',           # Urianálisis

    # ── Microbiología ────────────────────────────────────────────────────────
    'MICRO',        # Microbiología general
    'BACT',         # Bacteriología
    'FUNG',         # Micología
    'VIRUS',        # Virología
    'PARA',         # Parasitología
    'BLDBK',        # Banco de sangre / Inmunohematología

    # ── Inmunología / Serología ──────────────────────────────────────────────
    'SERO',         # Serología
    'ALLERGY',      # Alergología
    'IMMUNOL',      # Inmunología clínica

    # ── Endocrinología / Hormonas ────────────────────────────────────────────
    'ENDC',         # Endocrinología (tiroides, hormonas reproductivas, etc.)

    # ── Líquidos corporales ──────────────────────────────────────────────────
    'LIQBOD',       # Líquidos corporales (LCR, pleural, sinovial, etc.)

    # ── Genética molecular / PCR ─────────────────────────────────────────────
    'MOLPATH',      # Patología molecular
    'GENETICS',     # Genética

    # ── Otros laboratorio ────────────────────────────────────────────────────
    'MISC',         # Misceláneos de laboratorio (marcadores tumorales, etc.)
    'CELLMARK',     # Marcadores celulares / citometría de flujo
}

# =============================================================================
# SISTEMAS (tipo de muestra) que confirman que es laboratorio clínico.
# Se usa como filtro SECUNDARIO de seguridad cuando CLASS no está definida.
# =============================================================================
SISTEMAS_LABORATORIO = {
    'Bld', 'BldA', 'BldC', 'BldV', 'BldMV',
    'Ser', 'Plas', 'Ser/Plas', 'Ser/Plas/Bld', 'Ser/Plas/Urine',
    'Urine', 'Ur',
    'CSF',
    'Stool', 'Feces',
    'Spt', 'Sputum',
    'Sweat',
    'Saliva',
    'Vag', 'Urth',
    'Wound', 'Abscess',
    'Plr fld', 'Asc fld', 'Synv fld', 'Pericard fld',
    'BAL', 'BronchWsh',
    'Nph', 'Thrt', 'Nose',
    'Tiss',         # Biopsia (solo si CLASS es MOLPATH/MICRO)
}

# =============================================================================
# SISTEMAS QUE EXCLUIR SIEMPRE (imagen, patología, no clínicos)
# =============================================================================
SISTEMAS_EXCLUIR = {
    'Abdom', 'Liver', 'Heart', 'Eye', 'Brain', 'Kidney', 'Lung',
    'Bone', 'Muscle', 'Skin', 'Nerve',
}


def es_laboratorio_clinico(row):
    """
    Devuelve True si el código LOINC pertenece a laboratorio clínico humano.

    Lógica:
      1. Si CLASS está en la lista blanca → aceptar (más confiable).
      2. Si CLASS no está pero SYSTEM es un espécimen de laboratorio → aceptar
         (cubre códigos sin CLASS definida).
      3. Si SYSTEM está en la lista de exclusión → rechazar siempre.
    """
    loinc_class  = str(row.get("CLASS",  "")).strip()
    system_raw   = str(row.get("SYSTEM", "")).strip()
    system_upper = system_raw.upper()

    # Exclusión dura por sistema (imagen, patología, etc.)
    for excluir in SISTEMAS_EXCLUIR:
        if excluir.upper() in system_upper:
            return False

    # Aceptación por CLASS (más precisa)
    if loinc_class in CLASES_LABORATORIO:
        return True

    # Aceptación secundaria por SYSTEM cuando CLASS no está en la lista
    for sys_ok in SISTEMAS_LABORATORIO:
        if sys_ok.upper() in system_upper:
            return True

    return False


def _val(row, col):
    """Normaliza un valor del CSV: NaN o vacío → None."""
    v = row.get(col, None)
    if v is None:
        return None
    v = str(v).strip()
    if v.lower() in ("nan", ""):
        return None
    return v


# =============================
# COMANDO DJANGO
# =============================
class Command(BaseCommand):
    help = "Importa LOINC filtrado para laboratorio clínico (compatible local y Render)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help='No borra la tabla antes de insertar'
        )

    def handle(self, *args, **options):

        self.stdout.write("🚀 Iniciando importación de LOINC...\n")

        # ── Detectar BD ──────────────────────────────────────────────────────
        db_engine = settings.DATABASES['default']['ENGINE']
        if "postgresql" in db_engine:
            self.stdout.write(self.style.WARNING(" Usando PostgreSQL (Render)"))
        else:
            self.stdout.write(" Usando base de datos local")

        # ── Ruta CSV ─────────────────────────────────────────────────────────
        csv_file = os.path.join(
            settings.BASE_DIR,
            "loinc_documentos",
            "LoincTable",
            "loinc.csv"
        )

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f"Archivo no encontrado:\n{csv_file}"))
            return

        # ── Limpiar tabla ────────────────────────────────────────────────────
        if not options['no_delete']:
            self.stdout.write(" Limpiando tabla LoincCode...")
            LoincCode.objects.all().delete()
        else:
            self.stdout.write(" Modo sin borrado activado")

        total_insertados = 0
        aceptados        = 0
        rechazados       = 0
        CHUNK_SIZE       = 5000

        # Contadores por clase (para el resumen final)
        clases_vistas = {}

        self.stdout.write(" Procesando CSV por bloques...\n")

        for chunk in pd.read_csv(csv_file, chunksize=CHUNK_SIZE, low_memory=False):

            batch = []

            for row in chunk.to_dict(orient="records"):

                if es_laboratorio_clinico(row):
                    aceptados += 1

                    # Contar clases para el resumen
                    cls = str(row.get("CLASS", "")).strip() or "(sin clase)"
                    clases_vistas[cls] = clases_vistas.get(cls, 0) + 1

                    batch.append(LoincCode(
                        loinc_num  = _val(row, "LOINC_NUM") or "",
                        shortname  = _val(row, "SHORTNAME"),
                        component  = _val(row, "COMPONENT"),
                        property   = _val(row, "PROPERTY"),
                        system     = _val(row, "SYSTEM"),
                        scale_typ  = _val(row, "SCALE_TYP"),
                        method_typ = _val(row, "METHOD_TYP"),
                    ))
                else:
                    rechazados += 1

            if batch:
                try:
                    with transaction.atomic():
                        LoincCode.objects.bulk_create(
                            batch,
                            batch_size=1000,
                            ignore_conflicts=True
                        )
                    total_insertados += len(batch)
                    self.stdout.write(f"Insertados acumulados: {total_insertados}")

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error en inserción: {e}"))

        # ── Resumen final ────────────────────────────────────────────────────
        self.stdout.write("\nRESUMEN:")
        self.stdout.write(f"Aceptados:        {aceptados}")
        self.stdout.write(f"Rechazados:       {rechazados}")
        self.stdout.write(f"Total en tabla:   {total_insertados}")

        self.stdout.write("\nCódigos por clase:")
        for cls, cnt in sorted(clases_vistas.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {cls:<20} {cnt:>6}")

        self.stdout.write(self.style.SUCCESS("\nIMPORTACIÓN COMPLETADA"))