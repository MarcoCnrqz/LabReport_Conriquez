import os
import pandas as pd

from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.conf import settings

from LabApp.models import LoincCode


# =============================
# FILTROS
# =============================
SISTEMAS_PERMITIDOS = [
    "BLOOD", "BLD", "SER", "PLAS", "SER/PLAS",
    "URINE", "UR", "CSF", "BODY FLD",
    "STOOL", "FECES", "SWEAT", "SPUTUM",
    "SALIVA", "VAGINAL", "SEMEN", "MICRO"
]

SISTEMAS_EXCLUIR = [
    "ABDOMEN", "LIVER", "HEART", "EYE",
    "KIDNEY", "LUNG", "BRAIN", "TISSUE",
    "BIOPSY", "PATHOLOGY", "IMAGING", "XRAY"
]


def es_laboratorio(data):
    system = str(data.get("SYSTEM", "")).upper().strip()
    class_type = str(data.get("CLASS", "")).upper()

    if any(bad in system for bad in SISTEMAS_EXCLUIR):
        return False

    if any(ok in system for ok in SISTEMAS_PERMITIDOS):
        return True

    if any(x in class_type for x in ["CHEM", "HEM", "LAB"]):
        return True

    return False


# =============================
# COMANDO DJANGO
# =============================
class Command(BaseCommand):
    help = "Importa LOINC filtrado (compatible local y Render)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help='No borra la tabla antes de insertar'
        )

    def handle(self, *args, **options):

        self.stdout.write("🚀 Iniciando importación de LOINC...\n")

        # =============================
        # DETECTAR BD
        # =============================
        db_engine = settings.DATABASES['default']['ENGINE']

        if "postgresql" in db_engine:
            self.stdout.write(self.style.WARNING(" Usando PostgreSQL (Render)"))
        else:
            self.stdout.write(" Usando base de datos local")

        # =============================
        # RUTA CSV
        # =============================
        BASE_DIR = settings.BASE_DIR

        csv_file = os.path.join(
            BASE_DIR,
            "loinc_documentos",
            "LoincTable",
            "loinc.csv"
        )

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f"Archivo no encontrado:\n{csv_file}"))
            return

        # =============================
        # LIMPIAR TABLA (OPCIONAL)
        # =============================
        if not options['no_delete']:
            self.stdout.write(" Limpiando tabla LoincCode...")
            LoincCode.objects.all().delete()
        else:
            self.stdout.write(" Modo sin borrado activado")

        total_insertados = 0
        aceptados = 0
        rechazados = 0

        CHUNK_SIZE = 5000

        self.stdout.write(" Procesando CSV por bloques...\n")

        # =============================
        # PROCESAMIENTO
        # =============================
        for chunk in pd.read_csv(csv_file, chunksize=CHUNK_SIZE, low_memory=False):

            batch = []

            for row in chunk.to_dict(orient="records"):

                if es_laboratorio(row):
                    aceptados += 1

                    batch.append(LoincCode(
                        loinc_num=row.get("LOINC_NUM", ""),
                        shortname=row.get("SHORTNAME", ""),
                        component=row.get("COMPONENT", ""),
                        property=row.get("PROPERTY", ""),
                        system=row.get("SYSTEM", ""),
                        scale_typ=row.get("SCALE_TYP", "")
                    ))
                else:
                    rechazados += 1

            # =============================
            # INSERT MASIVO
            # =============================
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

        # =============================
        # RESULTADO FINAL
        # =============================
        self.stdout.write("\nRESUMEN:")
        self.stdout.write(f"Aceptados: {aceptados}")
        self.stdout.write(f"Rechazados: {rechazados}")
        self.stdout.write(self.style.SUCCESS(f"Total insertados: {total_insertados}"))

        self.stdout.write(self.style.SUCCESS("\nIMPORTACIÓN COMPLETADA"))