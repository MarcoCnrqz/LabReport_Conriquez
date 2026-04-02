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
# PALETA DE COLORES
# =============================================================================
COLOR_PRIMARIO   = colors.HexColor("#a2ab03")   # Verde oliva oscuro — headers, banners
COLOR_SECUNDARIO = colors.HexColor("#d3dd26")   # Amarillo-verde — acento, filas pares
COLOR_TEXTO_OSC  = colors.HexColor("#2c3e50")
COLOR_TEXTO_MED  = colors.HexColor("#444444")
COLOR_TEXTO_SUAV = colors.HexColor("#555555")
COLOR_BORDE      = colors.HexColor("#c5cc10")   # Borde dorado entre primario/secundario
COLOR_FILA_PAR   = colors.HexColor("#f5f7d6")   # Versión muy suave del secundario

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
    except Exception:
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
    except Exception:
        return str(valor)


def _fmt_hora(valor):
    """Convierte time a string HH:MM."""
    if valor is None:
        return "-"
    try:
        return valor.strftime("%H:%M")
    except Exception:
        return str(valor)


def _sanitizar_unidad(valor):
    """Devuelve N/A si la unidad es None, vacía o la cadena 'None'."""
    if not valor or str(valor).strip().lower() in ("none", ""):
        return "N/A"
    return str(valor).strip()


# =============================================================================
# 2. FUNCIÓN PRINCIPAL
# =============================================================================
def generar_pdf_reporte(detalles):
    output_dir = os.path.join(settings.MEDIA_ROOT, "reportes")
    os.makedirs(output_dir, exist_ok=True)

    ahora              = datetime.now()
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

    y = height - 1.8 * cm

    # =========================================================================
    # TÍTULO: Nombre del laboratorio
    # =========================================================================
    nombre_lab = detalles.get("laboratorio_nombre", "")
    if nombre_lab:
        BANNER_LAB_H = 1.0 * cm
        c.setFillColor(COLOR_PRIMARIO)
        c.roundRect(MARGEN_IZQ, y - BANNER_LAB_H, ANCHO_UTIL, BANNER_LAB_H,
                    radius=4, fill=1, stroke=0)

        c.setFillColor(colors.white)
        _font(c, "Roboto-Bold", 13)
        c.drawCentredString(width / 2, y - BANNER_LAB_H + 0.28*cm,
                            nombre_lab.upper())
        y -= BANNER_LAB_H + 0.5 * cm

        # Línea decorativa doble bajo el banner
        c.setStrokeColor(COLOR_SECUNDARIO)
        c.setLineWidth(2.5)
        c.line(MARGEN_IZQ, y, MARGEN_DER, y)
        c.setStrokeColor(COLOR_PRIMARIO)
        c.setLineWidth(0.8)
        c.line(MARGEN_IZQ, y - 0.15*cm, MARGEN_DER, y - 0.15*cm)
        y -= 0.45 * cm

    # =========================================================================
    # HEADER: Logo (izquierda) + datos paciente (centro) + fechas (derecha)
    # =========================================================================
    logo_data = detalles.get("laboratorio_logo")
    if logo_data:
        try:
            img = Image.open(BytesIO(logo_data))
            c.drawInlineImage(img, MARGEN_IZQ, y - 5*cm,
                              width=3.2*cm, preserveAspectRatio=True)
        except Exception:
            pass

    x_paciente = MARGEN_IZQ + 3.8 * cm
    _font(c, "Roboto-Bold", 10)
    c.setFillColor(COLOR_TEXTO_OSC)
    c.drawString(x_paciente, y - 0.3*cm,
                 f"PACIENTE: {detalles.get('paciente', 'N/A')}")

    _font(c, "Roboto", 8.5)
    c.setFillColor(COLOR_TEXTO_MED)
    c.drawString(x_paciente, y - 0.85*cm,
                 f"EDAD: {detalles.get('edad', '')}     SEXO: {detalles.get('sexo', '')}")

    x_fechas = width - 6.5 * cm

    def _fila_dato(label, valor, yy):
        _font(c, "Roboto-Bold", 7.5)
        c.setFillColor(COLOR_TEXTO_SUAV)
        c.drawString(x_fechas, yy, label)
        _font(c, "Roboto", 7.5)
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x_fechas + 3.0*cm, yy, valor)

    _fila_dato("Fecha análisis:", _fmt_fecha(fecha_analisis), y - 0.30*cm)
    _fila_dato("Fecha muestra:",  _fmt_fecha(fecha_muestra),  y - 0.75*cm)
    _fila_dato("Hora toma:",      _fmt_hora(hora_toma),       y - 1.20*cm)
    _fila_dato("Hora impresión:", hora_impresion_str,         y - 1.65*cm)

    y -= 2.6 * cm

    # =========================================================================
    # BANNER: Título del tipo de análisis
    # =========================================================================
    BANNER_H = 0.85 * cm
    c.setFillColor(COLOR_PRIMARIO)
    c.rect(MARGEN_IZQ, y - BANNER_H, ANCHO_UTIL, BANNER_H, fill=1, stroke=0)

    # Franja decorativa en el borde inferior del banner
    c.setFillColor(COLOR_SECUNDARIO)
    c.rect(MARGEN_IZQ, y - BANNER_H, ANCHO_UTIL, 0.12*cm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    _font(c, "Roboto-Bold", 11)
    c.drawCentredString(width / 2, y - BANNER_H + 0.25*cm,
                        str(detalles.get('tipo', 'RESULTADOS')).upper())

    y -= BANNER_H + 0.35 * cm

# =========================================================================
    # TABLA DE RESULTADOS — 5 columnas:
    #   PRUEBA | RESULTADO | REFERENCIA | UNIDAD | OPCIONES
    # =========================================================================

    COL_PRUEBA   = ANCHO_UTIL * 0.27
    COL_RESULT   = ANCHO_UTIL * 0.15
    COL_REF      = ANCHO_UTIL * 0.18
    COL_UNIDAD   = ANCHO_UTIL * 0.12
    COL_OPCIONES = ANCHO_UTIL * 0.28

    X0 = MARGEN_IZQ
    X1 = X0 + COL_PRUEBA
    X2 = X1 + COL_RESULT
    X3 = X2 + COL_REF
    X4 = X3 + COL_UNIDAD

    FILA_H   = 0.65 * cm
    HEADER_H = 0.75 * cm

    def dibujar_encabezados_tabla(yy):
        c.setFillColor(COLOR_PRIMARIO)
        c.rect(X0, yy - HEADER_H, ANCHO_UTIL, HEADER_H, fill=1, stroke=0)

        c.setFillColor(COLOR_SECUNDARIO)
        c.rect(X0, yy - HEADER_H, ANCHO_UTIL, 0.1*cm, fill=1, stroke=0)

        c.setFillColor(colors.white)
        _font(c, "Roboto-Bold", 7.5)
        PAD = 0.18 * cm
        c.drawString(X0 + PAD, yy - HEADER_H + 0.24*cm, "PRUEBA")
        c.drawString(X1 + PAD, yy - HEADER_H + 0.24*cm, "RESULTADO")
        c.drawString(X2 + PAD, yy - HEADER_H + 0.24*cm, "REFERENCIA")
        c.drawString(X3 + PAD, yy - HEADER_H + 0.24*cm, "UNIDAD")
        c.drawString(X4 + PAD, yy - HEADER_H + 0.24*cm, "OPCIONES")

    dibujar_encabezados_tabla(y)
    y -= HEADER_H
    y_inicio_tabla = y

    def cerrar_tabla(y_actual):
        """Dibuja el borde exterior y los separadores de columna."""
        c.setStrokeColor(COLOR_BORDE)
        c.setLineWidth(0.8)
        c.rect(X0, y_actual, ANCHO_UTIL, y_inicio_tabla - y_actual, fill=0, stroke=1)
        c.setLineWidth(0.3)
        c.setStrokeColor(colors.HexColor("#c8cc60"))
        for x_sep in (X1, X2, X3, X4):
            c.line(x_sep, y_actual, x_sep, y_inicio_tabla)

    resultados = detalles.get('resultados', [])

    for i, res in enumerate(resultados):
        if y - FILA_H < Y_FOOTER_TOP:
            cerrar_tabla(y)
            c.showPage()
            y = height - 2 * cm
            dibujar_encabezados_tabla(y)
            y -= HEADER_H
            y_inicio_tabla = y

        # Fondo alterno
        if i % 2 == 0:
            c.setFillColor(COLOR_FILA_PAR)
            c.rect(X0, y - FILA_H, ANCHO_UTIL, FILA_H, fill=1, stroke=0)

        valor_min = res.get('valor_min')
        valor_max = res.get('valor_max')
        color_val = _color_resultado(res.get('valor', ''), valor_min, valor_max)

        PAD  = 0.18 * cm
        Y_TX = y - FILA_H + 0.18*cm

        # — PRUEBA —
        _font(c, "Roboto", 7.5)
        c.setFillColor(colors.black)
        c.drawString(X0 + PAD, Y_TX, str(res.get('nombre_propiedad', '')))

        # — RESULTADO —
        c.setFillColor(color_val)
        _font(c, "Roboto-Bold" if color_val != colors.black else "Roboto", 7.5)
        c.drawString(X1 + PAD, Y_TX, str(res.get('valor', '')))

        # — REFERENCIA —
        _font(c, "Roboto", 7.5)
        c.setFillColor(COLOR_TEXTO_MED)
        if valor_min is not None and valor_max is not None:
            rango_txt = f"{valor_min} - {valor_max}"
        elif valor_min is not None:
            rango_txt = f">= {valor_min}"
        elif valor_max is not None:
            rango_txt = f"<= {valor_max}"
        else:
            rango_txt = "-"
        c.drawString(X2 + PAD, Y_TX, rango_txt)

        # — UNIDAD — (None → N/A)
        unidad_str = _sanitizar_unidad(res.get('unidad'))
        c.setFillColor(COLOR_TEXTO_MED)
        c.drawString(X3 + PAD, Y_TX, unidad_str)

        # — OPCIONES CUALITATIVAS —
        opciones_str = res.get('opciones_cualitativas', '') or ''
        if opciones_str:
            partes           = [p.strip() for p in opciones_str.split(',') if p.strip()]
            opciones_display = " / ".join(partes)
        else:
            opciones_display = "-"

        _font(c, "Roboto-Italic", 7)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(X4 + PAD, Y_TX, opciones_display)

        # Línea divisoria entre filas
        c.setStrokeColor(colors.HexColor("#dce07a"))
        c.setLineWidth(0.3)
        c.line(X0, y - FILA_H, MARGEN_DER, y - FILA_H)

        y -= FILA_H

    cerrar_tabla(y)
    y -= 0.3 * cm  # Separación entre tabla y bloque de metadatos

    # =========================================================================
    # TIPO DE MUESTRA Y MÉTODO
    # Aparecen como texto informativo debajo de la tabla de resultados.
    # Solo se renderizan si tienen valor; cada campo ocupa su propia línea.
    # =========================================================================
    tipo_muestra = detalles.get('tipo_muestra', '') or ''
    metodo       = detalles.get('metodo', '')       or ''

    if tipo_muestra or metodo:
        BLOQUE_H = (0.45 * cm) * (bool(tipo_muestra) + bool(metodo)) + 0.2 * cm
        c.setFillColor(colors.HexColor("#f9fbe7"))
        c.setStrokeColor(COLOR_SECUNDARIO)
        c.setLineWidth(0.5)
        c.roundRect(MARGEN_IZQ, y - BLOQUE_H, ANCHO_UTIL, BLOQUE_H,
                    radius=3, fill=1, stroke=1)

        y_txt = y - 0.28 * cm

        if tipo_muestra:
            _font(c, "Roboto-Bold", 7.5)
            c.setFillColor(COLOR_TEXTO_SUAV)
            c.drawString(MARGEN_IZQ + 0.3*cm, y_txt, "Tipo de muestra:")
            _font(c, "Roboto", 7.5)
            c.setFillColor(COLOR_TEXTO_OSC)
            c.drawString(MARGEN_IZQ + 3.5*cm, y_txt, tipo_muestra)
            y_txt -= 0.45 * cm

        if metodo:
            _font(c, "Roboto-Bold", 7.5)
            c.setFillColor(COLOR_TEXTO_SUAV)
            c.drawString(MARGEN_IZQ + 0.3*cm, y_txt, "Método:")
            _font(c, "Roboto", 7.5)
            c.setFillColor(COLOR_TEXTO_OSC)
            c.drawString(MARGEN_IZQ + 3.5*cm, y_txt, metodo)

        y -= BLOQUE_H + 0.3 * cm
    # =========================================================================
    # FOOTER: Firma digital + datos del químico
    # =========================================================================
    FIRMA_W      = 4.0 * cm
    Y_DATOS_BASE = 0.3 * cm
    Y_FIRMA_BASE = Y_DATOS_BASE + (LINEAS_PIE * ALTO_LINEA) + 0.3*cm
    X_FIRMA      = width / 2 - FIRMA_W / 2
    Y_LINEA_SEP  = Y_FIRMA_BASE + FIRMA_H + 0.3*cm

    # Línea separadora del footer
    c.setStrokeColor(COLOR_PRIMARIO)
    c.setLineWidth(1.2)
    c.line(MARGEN_IZQ, Y_LINEA_SEP, MARGEN_DER, Y_LINEA_SEP)
    c.setStrokeColor(COLOR_SECUNDARIO)
    c.setLineWidth(0.5)
    c.line(MARGEN_IZQ, Y_LINEA_SEP - 0.1*cm, MARGEN_DER, Y_LINEA_SEP - 0.1*cm)

    firma_bytes = detalles.get("quimico_firma_bytes")
    if firma_bytes:
        try:
            firma_img = Image.open(BytesIO(firma_bytes))
            c.drawInlineImage(firma_img, X_FIRMA, Y_FIRMA_BASE,
                              width=FIRMA_W, height=FIRMA_H,
                              preserveAspectRatio=True)
        except Exception:
            pass
    else:
        c.setStrokeColor(colors.HexColor("#bbbbbb"))
        c.setDash(3, 3)
        c.rect(X_FIRMA, Y_FIRMA_BASE, FIRMA_W, FIRMA_H, fill=0, stroke=1)
        c.setDash()
        _font(c, "Roboto-Italic", 7)
        c.setFillColor(colors.HexColor("#aaaaaa"))
        c.drawCentredString(width / 2, Y_FIRMA_BASE + FIRMA_H / 2, "Firma digital")

    quimico = detalles.get("usuario_generador", "")
    titulo  = detalles.get("quimico_titulo", "")
    puesto  = detalles.get("quimico_puesto", "")
    cedula  = detalles.get("quimico_cedula", "")
    esp     = detalles.get("quimico_cedula_especialidad", "")
    ssg     = detalles.get("quimico_ssg", "")
    uni     = detalles.get("quimico_universidad", "")

    nombre_completo = f"{titulo} {quimico}".strip()

    _font(c, "Roboto-Bold", 7.5)
    c.setFillColor(COLOR_TEXTO_OSC)
    yy = Y_DATOS_BASE + (LINEAS_PIE - 1) * ALTO_LINEA
    c.drawCentredString(width / 2, yy, nombre_completo)

    _font(c, "Roboto", 6.5)
    c.setFillColor(COLOR_TEXTO_MED)

    yy -= ALTO_LINEA
    if puesto:
        c.drawCentredString(width / 2, yy, puesto)

    yy -= ALTO_LINEA
    partes_cedula = []
    if cedula: partes_cedula.append(f"Cedula Prof.: {cedula}")
    if esp:    partes_cedula.append(f"Cedula Esp.: {esp}")
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
