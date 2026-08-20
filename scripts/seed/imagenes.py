"""Las fotos del seed: PNG generados, no fotos de verdad.

Tambien de aca sale como se llaman, que es lo que despues le permite a
borrado.py sacar del disco exactamente los archivos de esta base.
"""

import os
import uuid

# Prefijo de los archivos que genera el seed, para reconocerlos de un vistazo
# en static/uploads. La otra marca son los mails (ver datos.EMAIL_SEED).
PREFIJO_IMAGEN = "seed_"

# Sufijo distinto en cada corrida. Sin esto, dos bases sembradas por
# separado generan los mismos nombres de archivo (seed_post_0.png y
# compania) sobre la misma carpeta static/uploads: la segunda pisa las
# imagenes de la primera, y borrar una deja a la otra sin fotos.
CORRIDA = uuid.uuid4().hex[:8]


def _carpeta_uploads(app):
    # La misma carpeta que usa la app (config.UPLOAD_FOLDER); ver
    # services/uploads.py carpeta_uploads().
    return app.config["UPLOAD_FOLDER"]


def _generar_imagen(carpeta, nombre, texto, color):
    """Un PNG con un degrade y unas iniciales. Placeholder, no una foto."""
    from PIL import Image, ImageDraw, ImageFont

    ancho, alto = 800, 600
    imagen = Image.new("RGB", (ancho, alto), color)
    dibujo = ImageDraw.Draw(imagen)

    # Degrade vertical simple: se oscurece hacia abajo.
    for y in range(alto):
        factor = 1 - (y / alto) * 0.45
        dibujo.line(
            [(0, y), (ancho, y)],
            fill=tuple(int(canal * factor) for canal in color),
        )

    try:
        fuente = ImageFont.truetype("arial.ttf", 120)
    except OSError:
        # En una maquina sin esa fuente el placeholder sale igual, mas chico.
        fuente = ImageFont.load_default()

    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    dibujo.text(
        ((ancho - caja[2] + caja[0]) / 2, (alto - caja[3] + caja[1]) / 2),
        texto, font=fuente, fill=(255, 255, 255),
    )

    ruta = os.path.join(carpeta, nombre)
    imagen.save(ruta, format="PNG", optimize=True)
    return nombre


def _nombre_de_imagen(que):
    """seed_<corrida>_<que>.png. El prefijo para reconocerlas de un
    vistazo en la carpeta; la corrida para que no se pisen entre bases."""
    return f"{PREFIJO_IMAGEN}{CORRIDA}_{que}.png"


def _iniciales(titulo):
    palabras = [p for p in titulo.split() if p[0].isalpha()]
    return "".join(p[0] for p in palabras[:2]).upper() or "IM"
