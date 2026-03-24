import os
from io import BytesIO
from datetime import datetime
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

from django.conf import settings

# =============================================================================
# 1. REGISTRO DE FUENTES
# =============================================================================
def registrar_fuentes():
    ruta_base = os.path.dirname(__file__)
    fuentes = {
        "Roboto":        "Roboto-Regular.ttf",
        "Roboto-Bold":   "Roboto-Bold.ttf",
        "Roboto-Italic": "Roboto-Italic.ttf",
    }
    for nombre, archivo in fuentes.items():
        ruta_font = os.path.join(ruta_base, "fonts", archivo)
        if os.path.exists(ruta_font):
            try:
                pdfmetrics.registerFont(TTFont(nombre, ruta_font))
            except Exception as e:
                print(f"Error al registrar {nombre}: {e}")
        else:
            print(f" Fuente {archivo} no encontrada. Se usará Helvetica.")

registrar_fuentes()

# =============================================================================
# HELPERS
# =============================================================================
def _font(c, nombre, size):
    try:
        c.setFont(nombre, size)
    except:
        fallback = {
            "Roboto-Bold":   "Helvetica-Bold",
            "Roboto-Italic": "Helvetica-Oblique",
        }.get(nombre, "Helvetica")
        c.setFont(fallback, size)


def _color_resultado(valor, valor_min, valor_max):
    if valor_min is None and valor_max is None:
        return colors.black
    try:
        v = float(str(valor).replace(",", "."))
        if valor_min is not None and v < float(valor_min):
            return colors.red
        if valor_max is not None and v > float(valor_max):
            return colors.red
        return colors.HexColor("#1a7a3c")
    except (ValueError, TypeError):
        return colors.black


def _fmt_fecha(valor):
    """Convierte date/datetime a string dd/mm/yyyy."""
    if valor is None:
        return "-"
    try:
        return valor.strftime("%d/%m/%Y")
    except:
        return str(valor)


def _fmt_hora(valor):
    """Convierte time a string HH:MM."""
    if valor is None:
        return "-"
    try:
        return valor.strftime("%H:%M")
    except:
        return str(valor)


# =============================================================================
# 2. FUNCIÓN PRINCIPAL
# =============================================================================
def generar_pdf_reporte(detalles):
    output_dir = os.path.join(settings.MEDIA_ROOT, "reportes")
    os.makedirs(output_dir, exist_ok=True)

    # hora_impresion se genera automáticamente aquí
    ahora = datetime.now()
    hora_impresion_str = ahora.strftime("%H:%M")

    fecha_analisis = detalles.get('fecha_analisis')
    fecha_muestra  = detalles.get('fecha_muestra')
    hora_toma      = detalles.get('hora_toma')

    nombre_paciente = str(detalles.get('paciente', 'sin_nombre')).replace(" ", "_")
    archivo_nombre  = f"Reporte_{nombre_paciente}_{ahora.strftime('%Y%m%d_%H%M%S')}.pdf"
    archivo_path    = os.path.join(output_dir, archivo_nombre)

    c = canvas.Canvas(archivo_path, pagesize=A4)
    width, height = A4

    MARGEN_IZQ = 1.5 * cm
    MARGEN_DER = width - 1.5 * cm
    ANCHO_UTIL = MARGEN_DER - MARGEN_IZQ

    # Espacio reservado para el footer
    FIRMA_H      = 2.2 * cm
    LINEAS_PIE   = 5
    ALTO_LINEA   = 0.38 * cm
    FOOTER_TOTAL = 0.5*cm + FIRMA_H + (LINEAS_PIE * ALTO_LINEA) + 0.6*cm
    Y_FOOTER_TOP = FOOTER_TOTAL

    y = height - 2.1 * cm

    # =========================================================================
    # TÍTULO: Nombre del laboratorio (centrado, arriba de todo)
    # =========================================================================
    nombre_lab = detalles.get("laboratorio_nombre", "")
    if nombre_lab:
        _font(c, "Roboto-Bold", 14)
        c.setFillColor(colors.HexColor("#1a252f"))
        c.drawCentredString(width / 2, y, nombre_lab.upper())
        y -= 0.5 * cm

        # Línea decorativa bajo el nombre del laboratorio
        c.setStrokeColor(colors.HexColor("#2980b9"))
        c.setLineWidth(1.5)
        c.line(MARGEN_IZQ, y, MARGEN_DER, y)
        y -= 0.4 * cm

    # =========================================================================
    # HEADER: Logo (izquierda) + datos paciente (centro-izq) + fechas (derecha)
    # =========================================================================
    HEADER_TOP = y

    # --- Logo ---
    logo_data = detalles.get("laboratorio_logo")
    if logo_data:
        try:
            img = Image.open(BytesIO(logo_data))
            c.drawInlineImage(img, MARGEN_IZQ, y - 2.2*cm,
                              width=3.2*cm, preserveAspectRatio=True)
        except:
            pass

    # --- Datos del paciente (columna central) ---
    x_paciente = MARGEN_IZQ + 3.8 * cm
    _font(c, "Roboto-Bold", 10)
    c.setFillColor(colors.HexColor("#2c3e50"))
    c.drawString(x_paciente, y - 0.3*cm,
                 f"PACIENTE: {detalles.get('paciente', 'N/A')}")

    _font(c, "Roboto", 8.5)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawString(x_paciente, y - 0.85*cm,
                 f"EDAD: {detalles.get('edad', '')}     SEXO: {detalles.get('sexo', '')}")

    # --- Bloque de fechas y horas (columna derecha) ---
    x_fechas = width - 6.5 * cm   # alineado a la derecha

    def _fila_dato(label, valor, yy):
        _font(c, "Roboto-Bold", 7.5)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(x_fechas, yy, label)
        _font(c, "Roboto", 7.5)
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x_fechas + 3.0*cm, yy, valor)

    _fila_dato("Fecha análisis:",  _fmt_fecha(fecha_analisis),  y - 0.3*cm)
    _fila_dato("Fecha muestra:",   _fmt_fecha(fecha_muestra),   y - 0.75*cm)
    _fila_dato("Hora toma:",       _fmt_hora(hora_toma),        y - 1.20*cm)
    _fila_dato("Hora impresión:",  hora_impresion_str,          y - 1.65*cm)

    y -= 2.6 * cm

    # =========================================================================
    # BANNER: Título del análisis
    # =========================================================================
    BANNER_H = 0.85 * cm
    c.setFillColor(colors.HexColor("#2980b9"))
    c.rect(MARGEN_IZQ, y - BANNER_H, ANCHO_UTIL, BANNER_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    _font(c, "Roboto-Bold", 11)
    c.drawCentredString(width / 2, y - BANNER_H + 0.22*cm,
                        str(detalles.get('tipo', 'RESULTADOS')).upper())

    y -= BANNER_H + 0.5 * cm

    # =========================================================================
    # DOS TABLAS LADO A LADO
    # =========================================================================
    GAP       = 0.4 * cm
    ANCHO_IZQ = ANCHO_UTIL * 0.60
    ANCHO_DER = ANCHO_UTIL * 0.40 - GAP

    X_IZQ = MARGEN_IZQ
    X_DER = MARGEN_IZQ + ANCHO_IZQ + GAP

    COL_PRUEBA_W = ANCHO_IZQ * 0.58
    COL_RESULT_W = ANCHO_IZQ * 0.42
    COL_REF_W    = ANCHO_DER * 0.62
    COL_UNIDAD_W = ANCHO_DER * 0.38

    FILA_H       = 0.65 * cm
    HEADER_H     = 0.75 * cm
    COLOR_HEADER = colors.HexColor("#34495e")
    COLOR_PAR    = colors.HexColor("#f0f4f8")

    def dibujar_encabezados(yy):
        c.setFillColor(COLOR_HEADER)
        c.rect(X_IZQ, yy - HEADER_H, ANCHO_IZQ, HEADER_H, fill=1, stroke=0)
        c.setFillColor(colors.white)
        _font(c, "Roboto-Bold", 8)
        c.drawString(X_IZQ + 0.2*cm,                yy - HEADER_H + 0.22*cm, "PRUEBA")
        c.drawString(X_IZQ + COL_PRUEBA_W + 0.2*cm, yy - HEADER_H + 0.22*cm, "RESULTADO")
        c.setFillColor(COLOR_HEADER)
        c.rect(X_DER, yy - HEADER_H, ANCHO_DER, HEADER_H, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.drawString(X_DER + 0.2*cm,             yy - HEADER_H + 0.22*cm, "VALORES DE REFERENCIA")
        c.drawString(X_DER + COL_REF_W + 0.2*cm, yy - HEADER_H + 0.22*cm, "UNIDAD")

    dibujar_encabezados(y)
    y -= HEADER_H
    y_inicio_tabla = y

    def cerrar_tabla(y_actual):
        c.setStrokeColor(colors.HexColor("#aab4be"))
        c.setLineWidth(0.5)
        c.rect(X_IZQ, y_actual, ANCHO_IZQ, y_inicio_tabla - y_actual, fill=0, stroke=1)
        c.rect(X_DER, y_actual, ANCHO_DER, y_inicio_tabla - y_actual, fill=0, stroke=1)
        c.setLineWidth(0.3)
        c.line(X_IZQ + COL_PRUEBA_W, y_actual, X_IZQ + COL_PRUEBA_W, y_inicio_tabla)
        c.line(X_DER + COL_REF_W,    y_actual, X_DER + COL_REF_W,    y_inicio_tabla)

    resultados = detalles.get('resultados', [])

    for i, res in enumerate(resultados):
        if y - FILA_H < Y_FOOTER_TOP:
            cerrar_tabla(y)
            c.showPage()
            y = height - 2 * cm
            dibujar_encabezados(y)
            y -= HEADER_H
            y_inicio_tabla = y

        if i % 2 == 0:
            c.setFillColor(COLOR_PAR)
            c.rect(X_IZQ, y - FILA_H, ANCHO_IZQ, FILA_H, fill=1, stroke=0)
            c.rect(X_DER, y - FILA_H, ANCHO_DER, FILA_H, fill=1, stroke=0)

        valor_min = res.get('valor_min')
        valor_max = res.get('valor_max')
        color_val = _color_resultado(res.get('valor', ''), valor_min, valor_max)

        # Tabla izquierda
        _font(c, "Roboto", 8)
        c.setFillColor(colors.black)
        c.drawString(X_IZQ + 0.2*cm, y - FILA_H + 0.18*cm,
                     str(res.get('nombre_propiedad', '')))
        c.setFillColor(color_val)
        _font(c, "Roboto-Bold" if color_val != colors.black else "Roboto", 8)
        c.drawString(X_IZQ + COL_PRUEBA_W + 0.2*cm, y - FILA_H + 0.18*cm,
                     str(res.get('valor', '')))

        # Tabla derecha
        _font(c, "Roboto", 8)
        c.setFillColor(colors.HexColor("#333333"))
        if valor_min is not None and valor_max is not None:
            rango_txt = f"{valor_min} - {valor_max}"
        elif valor_min is not None:
            rango_txt = f"≥ {valor_min}"
        elif valor_max is not None:
            rango_txt = f"≤ {valor_max}"
        else:
            rango_txt = "-"

        c.drawString(X_DER + 0.2*cm,             y - FILA_H + 0.18*cm, rango_txt)
        c.drawString(X_DER + COL_REF_W + 0.2*cm, y - FILA_H + 0.18*cm,
                     str(res.get('unidad', '')))

        c.setStrokeColor(colors.HexColor("#d0d7de"))
        c.setLineWidth(0.3)
        c.line(X_IZQ, y - FILA_H, MARGEN_DER, y - FILA_H)

        y -= FILA_H

    cerrar_tabla(y)

    # =========================================================================
    # FOOTER: Firma digital + todos los datos del químico
    # =========================================================================
    FIRMA_W      = 4.0 * cm
    Y_DATOS_BASE = 0.3 * cm
    Y_FIRMA_BASE = Y_DATOS_BASE + (LINEAS_PIE * ALTO_LINEA) + 0.3*cm
    X_FIRMA      = width / 2 - FIRMA_W / 2
    Y_LINEA_SEP  = Y_FIRMA_BASE + FIRMA_H + 0.3*cm

    c.setStrokeColor(colors.HexColor("#aab4be"))
    c.setLineWidth(0.5)
    c.line(MARGEN_IZQ, Y_LINEA_SEP, MARGEN_DER, Y_LINEA_SEP)

    firma_bytes = detalles.get("quimico_firma_bytes")
    if firma_bytes:
        try:
            firma_img = Image.open(BytesIO(firma_bytes))
            c.drawInlineImage(firma_img, X_FIRMA, Y_FIRMA_BASE,
                              width=FIRMA_W, height=FIRMA_H,
                              preserveAspectRatio=True)
        except:
            pass
    else:
        c.setStrokeColor(colors.HexColor("#bbbbbb"))
        c.setDash(3, 3)
        c.rect(X_FIRMA, Y_FIRMA_BASE, FIRMA_W, FIRMA_H, fill=0, stroke=1)
        c.setDash()
        _font(c, "Roboto-Italic", 7)
        c.setFillColor(colors.HexColor("#aaaaaa"))
        c.drawCentredString(width / 2, Y_FIRMA_BASE + FIRMA_H / 2, "Firma digital")

    # Datos del químico
    quimico = detalles.get("usuario_generador", "")
    titulo  = detalles.get("quimico_titulo", "")
    puesto  = detalles.get("quimico_puesto", "")
    cedula  = detalles.get("quimico_cedula", "")
    esp     = detalles.get("quimico_cedula_especialidad", "")
    ssg     = detalles.get("quimico_ssg", "")
    uni     = detalles.get("quimico_universidad", "")

    nombre_completo = f"{titulo} {quimico}".strip()

    _font(c, "Roboto-Bold", 7.5)
    c.setFillColor(colors.HexColor("#2c3e50"))
    yy = Y_DATOS_BASE + (LINEAS_PIE - 1) * ALTO_LINEA
    c.drawCentredString(width / 2, yy, nombre_completo)

    _font(c, "Roboto", 6.5)
    c.setFillColor(colors.HexColor("#444444"))

    yy -= ALTO_LINEA
    if puesto:
        c.drawCentredString(width / 2, yy, puesto)

    yy -= ALTO_LINEA
    partes_cedula = []
    if cedula: partes_cedula.append(f"Cédula Prof.: {cedula}")
    if esp:    partes_cedula.append(f"Cédula Esp.: {esp}")
    if partes_cedula:
        c.drawCentredString(width / 2, yy, "   |   ".join(partes_cedula))

    yy -= ALTO_LINEA
    if ssg:
        c.drawCentredString(width / 2, yy, f"Reg. SSG: {ssg}")

    yy -= ALTO_LINEA
    if uni:
        c.drawCentredString(width / 2, yy, uni)

    c.save()
    return archivo_path