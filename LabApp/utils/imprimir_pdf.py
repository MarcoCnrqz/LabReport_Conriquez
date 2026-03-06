import os
from io import BytesIO
from datetime import datetime
from PIL import Image

# ReportLab imports
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# Django imports
from django.conf import settings

# =============================================================================
# 1. REGISTRO DE FUENTES
# =============================================================================
def registrar_fuentes():
    ruta_base = os.path.dirname(__file__)
    # Asegúrate de que esta carpeta exista: LabApp/utils/fonts/
    fuentes = {
        "Roboto": "Roboto-Regular.ttf",
        "Roboto-Italic": "Roboto-Italic.ttf"
    }
    
    for nombre, archivo in fuentes.items():
        ruta_font = os.path.join(ruta_base, "fonts", archivo)
        if os.path.exists(ruta_font):
            try:
                pdfmetrics.registerFont(TTFont(nombre, ruta_font))
            except Exception as e:
                print(f"⚠️ Error al registrar {nombre}: {e}")
        else:
            print(f"⚠️ Fuente {archivo} no encontrada en {ruta_font}. Se usará Helvetica.")

# Ejecutar registro al cargar el módulo
registrar_fuentes()

# =============================================================================
# 2. FUNCIÓN PRINCIPAL
# =============================================================================
def generar_pdf_reporte(detalles):
    """
    Genera un PDF basado en el diccionario 'detalles'.
    """
    # Configuración de rutas usando MEDIA_ROOT de Django
    output_dir = os.path.join(settings.MEDIA_ROOT, "reportes")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    fecha_p = detalles.get('fecha_analisis')
    if not isinstance(fecha_p, datetime):
        fecha_p = datetime.now()
    
    nombre_paciente = str(detalles.get('paciente', 'sin_nombre')).replace(" ", "_")
    archivo_nombre = f"Reporte_{nombre_paciente}_{fecha_p.strftime('%Y%m%d_%H%M%S')}.pdf"
    archivo_path = os.path.join(output_dir, archivo_nombre)

    c = canvas.Canvas(archivo_path, pagesize=A4)
    width, height = A4

    # --- Header / Paciente ---
    y = height - 2*cm
    
    # Logo del Laboratorio
    logo_data = detalles.get("laboratorio_logo")
    if logo_data:
        try:
            # Soporte para ImageField de Django o Bytes
            content = logo_data.read() if hasattr(logo_data, 'read') else logo_data
            img = Image.open(BytesIO(content))
            c.drawInlineImage(img, 2*cm, y - 1*cm, width=3*cm, preserveAspectRatio=True)
        except:
            pass

    c.setFillColor(colors.HexColor("#2c3e50"))
    # Intentar usar Roboto, si falló el registro usa Helvetica (estándar de PDF)
    try:
        c.setFont("Roboto", 14)
    except:
        c.setFont("Helvetica-Bold", 14)
        
    c.drawString(6*cm, y, f"PACIENTE: {detalles.get('paciente', 'N/A')}")
    
    try:
        c.setFont("Roboto", 10)
    except:
        c.setFont("Helvetica", 10)

    c.drawString(6*cm, y - 0.6*cm, f"EDAD: {detalles.get('edad', '0')} años")
    c.drawString(10*cm, y - 0.6*cm, f"SEXO: {detalles.get('sexo', 'N/A')}")
    c.drawString(6*cm, y - 1.2*cm, f"RESPONSABLE: {detalles.get('usuario_generador', 'N/A')}")

    # --- Título del Análisis ---
    y -= 3*cm
    c.setFillColor(colors.HexColor("#3498db"))
    c.rect(2*cm, y, width - 4*cm, 1*cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.drawCentredString(width/2, y + 0.3*cm, str(detalles.get('tipo', 'RESULTADOS')).upper())

    # --- Tabla de Resultados ---
    y -= 1.5*cm
    # Encabezados de tabla
    c.setFillColor(colors.black)
    c.line(2*cm, y + 0.6*cm, width - 2*cm, y + 0.6*cm)
    c.drawString(2.2*cm, y + 0.2*cm, "ESTUDIO")
    c.drawString(9*cm, y + 0.2*cm, "RESULTADO")
    c.drawString(12*cm, y + 0.2*cm, "UNIDAD")
    c.drawString(15*cm, y + 0.2*cm, "RANGOS")
    c.line(2*cm, y, width - 2*cm, y)

    y -= 0.8*cm
    resultados = detalles.get('resultados', [])
    for res in resultados:
        if y < 3*cm: # Salto de página
            c.showPage()
            y = height - 3*cm
        
        c.drawString(2.2*cm, y, str(res.get('nombre_propiedad', '')))
        c.drawString(9*cm, y, str(res.get('valor', '')))
        c.drawString(12*cm, y, str(res.get('unidad', '')))
        
        rango = f"{res.get('valor_min', '')} - {res.get('valor_max', '')}"
        c.drawString(15*cm, y, rango if res.get('valor_min') is not None else "-")
        y -= 0.7*cm

    # --- Footer ---
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.gray)
    c.drawCentredString(width/2, 1.5*cm, "Este documento es un reporte oficial del laboratorio.")

    c.save()
    return archivo_path