import os
from io import BytesIO
from datetime import datetime
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

import re
import requests

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
# HELPERS DE DESCARGA — Cloudinary con URL optimizada
# =============================================================================

def _optimizar_url_cloudinary(url: str, ancho: int = 1200) -> str:
    """
    Inserta parámetros de transformación en la URL de Cloudinary para que el
    servidor entregue la imagen redimensionada y comprimida, SIN modificar el
    original guardado en la nube.

    Transformaciones aplicadas:
      w_1200   → máximo 1200 px de ancho (más que suficiente para A4 a 300 DPI)
      q_auto   → Cloudinary elige la calidad óptima (elimina metadatos EXIF, comprime)
      f_jpg    → fuerza JPEG de salida (evita WEBP que ReportLab no soporta)

    Ejemplo:
      .../image/upload/v1/resultados_imagenes/abc123
      →  .../image/upload/w_1200,q_auto,f_jpg/v1/resultados_imagenes/abc123

    Si la URL ya contiene transformaciones (ej. w_), no las sobreescribe.
    Si la URL no es de Cloudinary o no contiene '/upload/', la devuelve sin cambios.
    """
    if not url or '/upload/' not in url:
        return url
    # Solo insertar si no tiene ya parámetros de transformación
    if re.search(r'/upload/[a-z]', url):
        return url
    transformacion = f'w_{ancho},q_auto,f_jpg'
    return url.replace('/upload/', f'/upload/{transformacion}/', 1)


def descargar_imagen_cloudinary(url: str, timeout: int = 20) -> bytes | None:
    """
    Descarga una imagen desde Cloudinary aplicando transformaciones de
    redimensionado antes de la descarga (el servidor de Cloudinary entrega
    la versión reducida, no el original completo).

    Esto evita el WORKER TIMEOUT en Render:
      - Sin optimización : ~7.5 MB por imagen → Pillow tarda segundos → 502
      - Con optimización : ~150–300 KB por imagen → Pillow instantáneo

    Devuelve los bytes de la imagen, o None si falla/timeout.
    """
    if not url:
        return None
    url_opt = _optimizar_url_cloudinary(url)
    try:
        print(f"[IMG] Descargando: {url_opt}")
        resp = requests.get(url_opt, timeout=timeout)
        resp.raise_for_status()
        print(f"[IMG] OK — {len(resp.content):,} bytes — content-type: {resp.headers.get('content-type', '?')}")
        return resp.content
    except requests.exceptions.Timeout:
        print(f"[IMG] ⏱️ Timeout descargando imagen: {url_opt}")
        return None
    except Exception as e:
        print(f"[IMG] ❌ Error descargando imagen ({type(e).__name__}): {e}")
        return None


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


def _truncar(texto, ancho_max_pt, font_name, font_size):
    """
    Trunca `texto` con '…' si supera `ancho_max_pt` puntos tipográficos.
    Útil para evitar que nombres de propiedad muy largos se salgan de la columna.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if not texto:
        return texto
    try:
        sw = stringWidth(texto, font_name, font_size)
    except Exception:
        sw = stringWidth(texto, 'Helvetica', font_size)
    if sw <= ancho_max_pt:
        return texto
    while len(texto) > 1:
        texto = texto[:-1]
        try:
            ancho = stringWidth(texto + '…', font_name, font_size)
        except Exception:
            ancho = stringWidth(texto + '…', 'Helvetica', font_size)
        if ancho <= ancho_max_pt:
            break
    return texto + '…'


# =============================================================================
# HELPER: Convierte bytes de imagen a ImageReader apto para ReportLab
# =============================================================================
def _preparar_imagen(blob, max_px: int = 1400):
    """
    Abre los bytes de una imagen, la redimensiona si es demasiado grande,
    convierte a RGB (fondo blanco si tiene transparencia) y devuelve un
    ImageReader listo para drawImage.

    Problemas que resuelve:
      1. drawInlineImage falla silenciosamente con PNG RGBA (transparencia).
         Usando drawImage + ImageReader el renderizado es confiable en todos los
         formatos: PNG con/sin alpha, JPEG, WebP, etc.
      2. Imágenes de celular en full resolution (4000×3000 px, 7+ MB) consumen
         demasiada RAM y CPU en Pillow + ReportLab, causando WORKER TIMEOUT en
         servidores con recursos limitados (ej. plan Free de Render).
         Se redimensionan a max_px en el lado mayor, manteniendo la proporción.
         Para A4 a 300 DPI el límite útil es ~2480 px; 1400 px da calidad
         excelente en impresión y reduce el tiempo de procesamiento ~10×.

    Retorna (ImageReader, (ancho_px, alto_px)) o lanza excepción si falla.
    """
    img = Image.open(BytesIO(blob))

    # ── Redimensionar si el lado mayor supera max_px ─────────────────────────
    orig_w, orig_h = img.size
    lado_mayor = max(orig_w, orig_h)
    if lado_mayor > max_px:
        escala  = max_px / lado_mayor
        nuevo_w = max(1, int(orig_w * escala))
        nuevo_h = max(1, int(orig_h * escala))
        img = img.resize((nuevo_w, nuevo_h), Image.LANCZOS)
        print(f"[IMG] Redimensionada: {orig_w}×{orig_h} → {nuevo_w}×{nuevo_h} px")

    # ── Normalizar modo de color ──────────────────────────────────────────────
    # Modo P (paleta) → RGBA primero para conservar canal alpha si existe
    if img.mode == 'P':
        img = img.convert('RGBA')

    # RGBA / LA (con transparencia) → RGB con fondo blanco
    if img.mode in ('RGBA', 'LA'):
        fondo = Image.new('RGB', img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[-1])   # usa el canal alpha como máscara
        img = fondo

    # Cualquier otro modo que no sea RGB (ej: L, CMYK, YCbCr…)
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85, optimize=True)  # JPEG << PNG en tamaño
    buf.seek(0)
    return ImageReader(buf), img.size


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
    # TÍTULO: Nombre del laboratorio — texto simple, sin panel ni barra de color
    # =========================================================================
    nombre_lab = detalles.get("laboratorio_nombre", "")
    if nombre_lab:
        _font(c, "Roboto-Bold", 14)
        c.setFillColor(COLOR_TEXTO_OSC)
        c.drawCentredString(width / 2, y - 0.65 * cm, nombre_lab.upper())
        y -= 1.05 * cm

        # Línea decorativa doble bajo el nombre
        c.setStrokeColor(COLOR_BORDE)
        c.setLineWidth(1.5)
        c.line(MARGEN_IZQ, y, MARGEN_DER, y)
        c.setStrokeColor(colors.HexColor("#e8eb90"))
        c.setLineWidth(0.5)
        c.line(MARGEN_IZQ, y - 0.13 * cm, MARGEN_DER, y - 0.13 * cm)
        y -= 0.38 * cm

    # =========================================================================
    # HEADER: Logo (izquierda) + datos paciente (centro) + fechas (derecha)
    # =========================================================================
    logo_data = detalles.get("laboratorio_logo")
    if logo_data:
        try:
            img_reader, (orig_w, orig_h) = _preparar_imagen(logo_data)
            # Calcular alto proporcional al ancho fijo de 3.2 cm
            logo_w = 3.2 * cm
            logo_h = logo_w * orig_h / orig_w if orig_w else logo_w
            c.drawImage(img_reader, MARGEN_IZQ, y - logo_h,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"[PDF] ERROR dibujando logo del laboratorio: {type(e).__name__}: {e}")

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
    # IMÁGENES DE RESULTADO
    # Solo se renderizan cuando tipo_formato == 'IMAGENES_RESULTADOS'.
    # Se muestran ANTES de la tabla: primero imagen1 e imagen2 lado a lado
    # (o centrada si solo hay una), luego la tabla de resultados.
    # Las imágenes llegan como bytes descargados desde Cloudinary en views.py,
    # igual que el logo del laboratorio y la firma digital del químico.
    # =========================================================================
    imagen_blob1 = detalles.get("imagen_blob1")
    imagen_blob2 = detalles.get("imagen_blob2")

    if imagen_blob1 or imagen_blob2:
        IMG_MAX_H = 7.0 * cm                          # alto máximo de cada imagen
        IMG_MAX_W = (ANCHO_UTIL / 2) - 0.3 * cm      # mitad del ancho útil

        blobs_validos = [b for b in [imagen_blob1, imagen_blob2] if b]
        n = len(blobs_validos)

        # Si solo hay una imagen se muestra centrada ocupando el ancho completo
        img_w = ANCHO_UTIL if n == 1 else IMG_MAX_W

        # Si no caben en la página actual, nueva página
        if y - IMG_MAX_H - 0.4 * cm < Y_FOOTER_TOP:
            y = _nueva_pagina()

        # Título de sección "IMÁGENES"
        SEC_IMG_H = 0.55 * cm
        c.setFillColor(COLOR_PRIMARIO)
        c.rect(MARGEN_IZQ, y - SEC_IMG_H, ANCHO_UTIL, SEC_IMG_H, fill=1, stroke=0)
        c.setFillColor(COLOR_SECUNDARIO)
        c.rect(MARGEN_IZQ, y - SEC_IMG_H, ANCHO_UTIL, 0.08 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        _font(c, "Roboto-Bold", 8)
        c.drawString(MARGEN_IZQ + 0.25 * cm, y - SEC_IMG_H + 0.16 * cm, "IMÁGENES")
        y -= SEC_IMG_H + 0.25 * cm

        x_pos = MARGEN_IZQ
        alto_real_max = 0  # para avanzar y exactamente lo que ocupó la imagen más alta

        for blob in blobs_validos:
            try:
                img_reader, (orig_w, orig_h) = _preparar_imagen(blob)
                if orig_w and orig_h:
                    scale  = min(img_w / orig_w, IMG_MAX_H / orig_h)
                    draw_w = orig_w * scale
                    draw_h = orig_h * scale
                else:
                    draw_w, draw_h = img_w, IMG_MAX_H

                c.drawImage(
                    img_reader,
                    x_pos,
                    y - draw_h,
                    width=draw_w,
                    height=draw_h,
                    preserveAspectRatio=True,
                    mask='auto',
                )
                alto_real_max = max(alto_real_max, draw_h)
            except Exception as e:
                print(f"[PDF] ERROR al renderizar imagen resultado: {type(e).__name__}: {e}")

            # Avanzar al lado derecho si hay dos imágenes
            x_pos += IMG_MAX_W + 0.6 * cm

        y -= alto_real_max + 0.5 * cm   # espacio entre imágenes y tabla

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

    # FILA_H ampliada a 0.82cm para dar cabida al código LOINC en segunda línea
    FILA_H   = 0.82 * cm
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

    # ── Compatibilidad: soporta tanto 'resultados_agrupados' (nuevo, con series)
    #    como 'resultados' (lista plana, legado). Si viene la clave nueva, la usa;
    #    si no, envuelve la lista plana en un grupo sin nombre para reutilizar
    #    el mismo código de renderizado.
    grupos = detalles.get('resultados_agrupados')
    if not grupos:
        resultados_planos = detalles.get('resultados', [])
        grupos = [{'seccion': '', 'orden': 0, 'filas': resultados_planos}]

    SERIE_H = 0.6 * cm   # altura de la barra de serie

    # y_inicio_tabla como lista de un elemento para poder mutarlo desde cerrar_tabla
    _yit = [y]

    def _iniciar_tabla(yy):
        """Dibuja encabezados y actualiza y_inicio_tabla. Devuelve nueva y."""
        dibujar_encabezados_tabla(yy)
        _yit[0] = yy - HEADER_H
        return yy - HEADER_H

    def cerrar_tabla(y_actual):
        """Dibuja el borde exterior y los separadores de columna."""
        c.setStrokeColor(COLOR_BORDE)
        c.setLineWidth(0.8)
        c.rect(X0, y_actual, ANCHO_UTIL, _yit[0] - y_actual, fill=0, stroke=1)
        c.setLineWidth(0.3)
        c.setStrokeColor(colors.HexColor("#c8cc60"))
        for x_sep in (X1, X2, X3, X4):
            c.line(x_sep, y_actual, x_sep, _yit[0])

    def dibujar_serie_header(yy, nombre_serie):
        """Dibuja el nombre de la serie como texto simple con línea separadora."""
        # Línea decorativa encima del texto
        c.setStrokeColor(COLOR_BORDE)
        c.setLineWidth(0.6)
        c.line(X0, yy - 0.1 * cm, MARGEN_DER, yy - 0.1 * cm)
        # Texto del nombre de serie
        _font(c, "Roboto-Bold", 8)
        c.setFillColor(COLOR_TEXTO_OSC)
        c.drawString(X0, yy - SERIE_H + 0.12 * cm, nombre_serie.upper())

    fila_global = 0   # contador continuo para fondo alterno entre grupos
    primer_grupo = True

    # ── Función para saltar de página con cabecera compacta ──────────────────
    #
    # En páginas de continuación se dibuja un header reducido con:
    #   • Nombre del laboratorio + línea decorativa doble
    #   • Nombre del paciente (izquierda) + tipo de análisis (derecha)
    # Devuelve la nueva `y` desde la que continuar el contenido.
    def _nueva_pagina():
        c.showPage()
        yy = height - 1.2 * cm

        nombre_lab = detalles.get("laboratorio_nombre", "")
        if nombre_lab:
            _font(c, "Roboto-Bold", 9)
            c.setFillColor(COLOR_TEXTO_OSC)
            c.drawCentredString(width / 2, yy, nombre_lab.upper())
            yy -= 0.45 * cm
            c.setStrokeColor(COLOR_BORDE)
            c.setLineWidth(1.0)
            c.line(MARGEN_IZQ, yy, MARGEN_DER, yy)
            c.setStrokeColor(colors.HexColor("#e8eb90"))
            c.setLineWidth(0.4)
            c.line(MARGEN_IZQ, yy - 0.1 * cm, MARGEN_DER, yy - 0.1 * cm)
            yy -= 0.35 * cm

        _font(c, "Roboto-Bold", 8)
        c.setFillColor(COLOR_TEXTO_OSC)
        c.drawString(MARGEN_IZQ, yy,
                     f"Paciente: {detalles.get('paciente', '')}")
        _font(c, "Roboto-Italic", 8)
        c.setFillColor(COLOR_TEXTO_SUAV)
        c.drawRightString(MARGEN_DER, yy,
                          str(detalles.get('tipo', '')).upper())
        yy -= 0.55 * cm

        return yy

    for grupo in grupos:
        nombre_serie = (grupo.get('seccion') or '').strip()
        filas        = grupo.get('filas', [])
        if not filas:
            continue

        # — Encabezado de serie (si tiene nombre) o encabezado inicial —
        if nombre_serie:
            # ¿Cabe barra de serie + cabecera de tabla + al menos 1 fila?
            espacio_min = SERIE_H + HEADER_H + FILA_H
            if not primer_grupo and y - espacio_min < Y_FOOTER_TOP:
                cerrar_tabla(y)
                y = _nueva_pagina()

            dibujar_serie_header(y, nombre_serie)
            y -= SERIE_H
            y = _iniciar_tabla(y)
        else:
            # Grupo sin serie: dibujar encabezado de tabla normal si es el primero
            if primer_grupo:
                y = _iniciar_tabla(y)
            # Si no es el primero y no tiene serie, solo separar un poco
            # (los grupos sin serie no suelen mezclarse con los que sí tienen)

        for res in filas:
            if y - FILA_H < Y_FOOTER_TOP:
                cerrar_tabla(y)
                y = _nueva_pagina()
                y = _iniciar_tabla(y)

            # Fondo alterno (continuo entre grupos para consistencia visual)
            if fila_global % 2 == 0:
                c.setFillColor(COLOR_FILA_PAR)
                c.rect(X0, y - FILA_H, ANCHO_UTIL, FILA_H, fill=1, stroke=0)

            valor_min = res.get('valor_min')
            valor_max = res.get('valor_max')
            color_val = _color_resultado(res.get('valor', ''), valor_min, valor_max)

            PAD  = 0.18 * cm
            # Línea superior: nombre de la propiedad (con espacio para LOINC abajo)
            Y_TX_NAME  = y - 0.28 * cm          # primer renglón
            Y_TX_LOWER = y - FILA_H + 0.13 * cm  # segundo renglón (LOINC / valor)

            # — PRUEBA —
            _font(c, "Roboto", 7.5)
            c.setFillColor(colors.black)
            nombre_txt = _truncar(
                str(res.get('nombre_propiedad', '')),
                COL_PRUEBA - PAD * 2,
                'Roboto', 7.5,
            )
            c.drawString(X0 + PAD, Y_TX_NAME, nombre_txt)

            # — LOINC (código gris, pequeño, debajo del nombre de prueba) —
            loinc_num = res.get('loinc_num', '') or ''
            if loinc_num:
                _font(c, "Roboto-Italic", 6)
                c.setFillColor(colors.HexColor("#999999"))
                c.drawString(X0 + PAD, Y_TX_LOWER, loinc_num)

            # — RESULTADO —
            c.setFillColor(color_val)
            _font(c, "Roboto-Bold" if color_val != colors.black else "Roboto", 7.5)
            c.drawString(X1 + PAD, Y_TX_NAME, str(res.get('valor', '')))

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
            c.drawString(X2 + PAD, Y_TX_NAME, rango_txt)

            # — OPCIONES CUALITATIVAS —
            # Se calcula antes de la unidad para saber si la propiedad es cualitativa.
            opciones_str = res.get('opciones_cualitativas', '') or ''
            if opciones_str:
                partes           = [p.strip() for p in opciones_str.split(',') if p.strip()]
                opciones_display = " / ".join(partes)
            else:
                opciones_display = "-"

            # — UNIDAD —
            # Para propiedades cualitativas la unidad no aplica; se muestra "-"
            # en lugar de "N/A" para no confundir al lector del reporte.
            if opciones_str:
                unidad_str = "-"
            else:
                unidad_str = _sanitizar_unidad(res.get('unidad'))
            c.setFillColor(COLOR_TEXTO_MED)
            c.drawString(X3 + PAD, Y_TX_NAME, unidad_str)

            _font(c, "Roboto-Italic", 7)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(X4 + PAD, Y_TX_NAME, opciones_display)

            # Línea divisoria entre filas
            c.setStrokeColor(colors.HexColor("#dce07a"))
            c.setLineWidth(0.3)
            c.line(X0, y - FILA_H, MARGEN_DER, y - FILA_H)

            y -= FILA_H
            fila_global += 1

        # Cerrar la tabla al terminar cada grupo
        cerrar_tabla(y)
        y -= 0.2 * cm   # pequeña separación entre grupos
        primer_grupo = False
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
            firma_reader, (orig_w, orig_h) = _preparar_imagen(firma_bytes)
            c.drawImage(firma_reader, X_FIRMA, Y_FIRMA_BASE,
                        width=FIRMA_W, height=FIRMA_H,
                        preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"[PDF] ERROR dibujando firma digital: {type(e).__name__}: {e}")
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