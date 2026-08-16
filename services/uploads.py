"""Validacion y guardado de las imagenes que suben los usuarios.

Esta logica estaba repetida en blog.create() y blog.update(). Al tenerla en un
solo lugar, cualquier regla nueva (tamanio maximo, miniaturas, mover a S3)
se agrega una sola vez y aplica a los dos flujos.
"""

import logging
import os
import uuid

from flask import current_app
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Tamanio maximo por imagen. Flask corta antes con MAX_CONTENT_LENGTH, pero
# dejamos el valor aca tambien para que el servicio sea autocontenido.
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

# Un emprendedor sube fotos de 8 MB desde el celular sin darse cuenta: se
# redimensionan y comprimen antes de guardar para no llenar el disco.
MAX_IMAGE_WIDTH = 1200
JPEG_QUALITY = 85


def carpeta_uploads(*subcarpetas):
    """La carpeta donde se guardan las imagenes subidas, ya absoluta.

    Es el unico lugar del proyecto que arma esa ruta. Antes cada vista la
    componia con current_app.root_path (habia seis copias, y dos de ellas con
    subcarpeta propia: avatars y covers): ademas de estar repetida, ataba la
    ubicacion de los archivos a la ubicacion del codigo. Ahora sale de
    UPLOAD_FOLDER, que se calcula una sola vez en config.py.

    Las subcarpetas se pasan como argumentos: carpeta_uploads("avatars").
    """
    return os.path.join(current_app.config["UPLOAD_FOLDER"], *subcarpetas)


def allowed_file(filename):
    """Verifica si el archivo tiene una extension permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_post_image(file, upload_dir):
    """Valida y guarda una imagen subida.

    Devuelve una tupla (nombre_de_archivo, error):
    - (None, None)      -> no se subio ninguna imagen, no es un error
    - (None, "mensaje") -> la imagen fue rechazada, hay que mostrar el mensaje
    - ("abc_foto.jpg", None) -> se guardo bien, ese es el nombre a persistir
    """
    if not file or not file.filename:
        return None, None

    if not allowed_file(file.filename):
        return None, "Formato de imagen no permitido (usa png, jpg, jpeg o gif)."

    # La extension se puede falsificar facil: un .exe renombrado a .jpg pasaria
    # el chequeo de arriba. Pillow intenta abrir el archivo de verdad, asi que
    # solo pasan archivos que realmente son imagenes.
    try:
        Image.open(file.stream).verify()
    except Exception:
        logger.warning("Se rechazo un archivo que no es una imagen valida: %s", file.filename)
        return None, "El archivo no parece ser una imagen valida."

    # verify() consume el stream, hay que volver al principio antes de leerlo
    # de nuevo para procesar la imagen.
    file.stream.seek(0)

    os.makedirs(upload_dir, exist_ok=True)
    # El uuid evita que dos usuarios que suben "foto.jpg" se pisen el archivo.
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    destino = os.path.join(upload_dir, filename)

    _guardar_comprimida(file.stream, destino)

    return filename, None


def borrar_de_disco(upload_dir, nombres):
    """Borra imagenes del disco, ignorando las que no esten.

    Se usa para dos cosas: limpiar lo que escribio un intento que despues
    fallo, y sacar la foto de algo que se borro de la base. En los dos casos,
    sin esto el archivo queda ocupando disco para siempre sin ninguna fila que
    lo referencie.
    """
    for nombre in nombres:
        if not nombre:
            continue
        try:
            os.remove(os.path.join(upload_dir, nombre))
        except OSError:
            # Que no se pueda borrar no justifica romperle el formulario al
            # usuario: queda el archivo suelto y el aviso en el log.
            logger.warning("No se pudo borrar la imagen huerfana %s", nombre)


def _guardar_comprimida(stream, destino):
    """Redimensiona y comprime la imagen antes de guardarla en disco.

    Sin esto una foto de celular de varios MB se guarda tal cual, y si viene
    con orientacion EXIF (tipico en fotos verticales) se ve rotada en el
    navegador, que ignora ese metadato.
    """
    imagen = Image.open(stream)
    formato = (imagen.format or "JPEG").upper()
    imagen = ImageOps.exif_transpose(imagen)

    if imagen.width > MAX_IMAGE_WIDTH:
        nueva_altura = round(imagen.height * MAX_IMAGE_WIDTH / imagen.width)
        imagen = imagen.resize((MAX_IMAGE_WIDTH, nueva_altura), Image.LANCZOS)

    # JPEG no soporta canal alfa: sin esta conversion el guardado falla para
    # imagenes que vienen en modo RGBA o paleta (P).
    extension = os.path.splitext(destino)[1].lower()
    if extension in (".jpg", ".jpeg") and imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")

    imagen.save(destino, format=formato, quality=JPEG_QUALITY, optimize=True)
