"""Validacion y guardado de las imagenes que suben los usuarios.

Esta logica estaba repetida en blog.create() y blog.update(). Al tenerla en un
solo lugar, cualquier regla nueva (tamanio maximo, miniaturas, mover a S3)
se agrega una sola vez y aplica a los dos flujos.
"""

import logging
import os
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Tamanio maximo por imagen. Flask corta antes con MAX_CONTENT_LENGTH, pero
# dejamos el valor aca tambien para que el servicio sea autocontenido.
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


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

    # verify() consume el stream, hay que volver al principio antes de guardar.
    file.stream.seek(0)

    os.makedirs(upload_dir, exist_ok=True)
    # El uuid evita que dos usuarios que suben "foto.jpg" se pisen el archivo.
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    file.save(os.path.join(upload_dir, filename))

    return filename, None
