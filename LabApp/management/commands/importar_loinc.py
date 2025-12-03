import csv
from django.core.management.base import BaseCommand
from labApp.models import LoincCode


#Aqui defino un comando donde busco el archivo CSV y lo importo a la base de datos, el archivo lo tengo en la carpeta loinc_documentos
#Descargado desde la pagina de LOINC 
class Command(BaseCommand):
    help = 'Importa los códigos LOINC desde un CSV'

    def handle(self, *args, **kwargs):
        with open('loinc_documentos/LoincTableCore/LoincTableCore.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            count = 0
            for row in reader:
                LoincCode.objects.update_or_create(
                    loinc_num=row['LOINC_NUM'],
                    defaults={
                        'component': row.get('COMPONENT', ''),
                        'property': row.get('PROPERTY', ''),
                        'time_aspct': row.get('TIME_ASPCT', ''),
                        'system': row.get('SYSTEM', ''),
                        'scale_typ': row.get('SCALE_TYP', ''),
                        'method_typ': row.get('METHOD_TYP', ''),
                        'shortname': row.get('SHORTNAME', ''),
                        'long_common_name': row.get('LONG_COMMON_NAME', ''),
                    }
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Importados {count} códigos LOINC'))
