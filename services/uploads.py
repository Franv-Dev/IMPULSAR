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

# Tope duro de subida, la ultima red de seguridad y no el control de tamanio de
# todos los dias. Flask lo usa como MAX_CONTENT_LENGTH (ver config.py) y corta
# la request antes de que llegue a este modulo, con lo cual una foto que lo pasa
# no llega nunca a _guardar_comprimida.
#
# Por eso son 15 MB y no 5: con 5 MB, la foto de cualquier celular moderno
# rebotaba con "la imagen es demasiado grande" en vez de pasar por la
# compresion que ya existia justamente para eso. El emprendedor no tiene como
# achicar una foto antes de subirla, y el disco no se llenaba igual, porque lo
# que se guarda es la version redimensionada a MAX_IMAGE_WIDTH. Lo unico que
# sigue frenando este numero es lo que tardaria demasiado en procesarse.
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB

# Un emprendedor sube fotos de 8 MB desde el celular sin darse cuenta: se
# redimensionan y comprimen antes de guardar para no llenar el disco.
MAX_IMAGE_WIDTH = 1200
JPEG_QUALITY = 85

# Cuantos pixeles puede tener una imagen, que es un limite distinto del de
# bytes y no se deduce de el: el peso del archivo es la imagen COMPRIMIDA, y la
# que se descomprime en RAM ocupa ancho * alto * 3 bytes sin importar cuanto
# pesaba. Un PNG de un color solido de menos de 1 MB puede descomprimir a
# cientos de MB, asi que sin este tope subir el limite de bytes a 15 MB seria
# abrirle mas puerta a eso.
#
# Pillow trae su propio freno (Image.MAX_IMAGE_PIXELS, 89.5 Mpx por default)
# pero no alcanza tal cual: entre una y dos veces ese valor solo emite un
# DecompressionBombWarning y sigue de largo, asi que el techo real del default
# son 179 Mpx, o sea medio giga en RAM para decodificar una foto. Por eso el
# numero se fija aca y ademas se chequea a mano en save_post_image: el warning
# no frena nada por si solo.
#
# 50 Mpx cubre de sobra lo que sacan las camaras y los celulares de verdad (un
# sensor de 50 MP da 8660x5773) y deja el pico de RAM en unos 200 MB por
# imagen, que dura lo que tarda el resize a 1200 px de ancho.
#
# Ese numero esta medido, no estimado. La cuenta ingenua (ancho * alto * 3 = 150
# MB) cuenta solo el decode y se queda corta: el pipeline tiene mas de un raster
# vivo a la vez. Con exif_transpose copiando el raster entero -- como estaba
# hasta que se le paso in_place=True, ver _guardar_comprimida -- el pico real
# eran ~375 MB.
MAX_IMAGE_PIXELS = 50 * 1000 * 1000

# El default de Pillow tambien se baja al mismo numero, para que su freno duro
# (el que si corta, a 2x) quede en 100 Mpx en vez de 179. Es global del modulo
# Image y por eso se hace una sola vez, al importar: el chequeo explicito de
# save_post_image es el que da el mensaje bueno, y esto es lo que ataja el caso
# donde la imagen es tan grande que ni conviene llegar a medirla.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# El mensaje sale por los dos caminos que rechazan por dimensiones (el freno de
# Pillow y el chequeo propio), asi que vive en un solo lado: para el que sube la
# foto los dos casos son el mismo problema.
MENSAJE_DEMASIADOS_PIXELES = (
    "Esa imagen tiene demasiados píxeles. Probá con una foto de cámara o celular normal."
)


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


def carpeta_privada(*subcarpetas):
    """La carpeta de las subidas que no son publicas, ya absoluta.

    Es a PRIVATE_UPLOAD_FOLDER lo que carpeta_uploads() es a UPLOAD_FOLDER, y
    existe separada por una razon concreta y no por prolijidad: carpeta_uploads
    ("privado") habria dado static/uploads/privado, y Flask sirve su
    static_folder recursivamente, con lo cual el archivo se bajaria por
    /static/uploads/privado/<nombre> sin pasar por ninguna vista ni por ningun
    chequeo. La carpeta que devuelve esta cuelga de la raiz del repo, afuera de
    static/.

    Que el permiso se chequee igual en las vistas no la hace redundante: son dos
    capas. La del codigo cubre a quien pide la URL de la ruta Flask; esta cubre
    el dia que un nginx sirva static/ directo sin preguntarle nada a la app.
    """
    return os.path.join(current_app.config["PRIVATE_UPLOAD_FOLDER"], *subcarpetas)


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
    #
    # Las dimensiones se leen aca, del mismo open: estan en el encabezado, asi
    # que saberlas no cuesta decodificar nada. Recien despues se decide si vale
    # la pena hacerlo.
    try:
        imagen = Image.open(file.stream)
        ancho, alto = imagen.size
        imagen.verify()
    except Image.DecompressionBombError:
        # Tan grande que Pillow corto sin llegar a abrirla (ver MAX_IMAGE_PIXELS).
        logger.warning(
            "Se rechazo una imagen con dimensiones desmedidas: %s", file.filename
        )
        return None, MENSAJE_DEMASIADOS_PIXELES
    except Exception:
        logger.warning("Se rechazo un archivo que no es una imagen valida: %s", file.filename)
        return None, "El archivo no parece ser una imagen valida."

    # El chequeo propio, que es el que de verdad frena la franja donde Pillow
    # solo avisa: entre MAX_IMAGE_PIXELS y el doble, DecompressionBombWarning no
    # corta nada y la imagen se decodificaria igual.
    if ancho * alto > MAX_IMAGE_PIXELS:
        logger.warning(
            "Se rechazo una imagen de %sx%s px (tope %s): %s",
            ancho, alto, MAX_IMAGE_PIXELS, file.filename,
        )
        return None, MENSAJE_DEMASIADOS_PIXELES

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
    # in_place=True y por eso SIN asignar: asi rota sobre el mismo raster en vez
    # de generar una copia entera antes de que el resize lo achique, que es de
    # donde salia la mitad del pico de RAM (ver MAX_IMAGE_PIXELS). Ojo que en
    # ese modo la funcion devuelve None: `imagen = ImageOps.exif_transpose(...)`
    # con in_place dejaria imagen en None y todo lo de abajo explota.
    ImageOps.exif_transpose(imagen, in_place=True)

    # El resize va DESPUES de la rotacion y no al reves. Si la foto viene
    # vertical con un EXIF que la marca para rotar a horizontal, hasta que la
    # rotacion se aplica el ancho y el alto estan cruzados, y redimensionar ahi
    # ataria MAX_IMAGE_WIDTH a la dimension equivocada: la foto terminaria con
    # 1200 px de alto y el ancho que saliera.
    if imagen.width > MAX_IMAGE_WIDTH:
        nueva_altura = round(imagen.height * MAX_IMAGE_WIDTH / imagen.width)
        imagen = imagen.resize((MAX_IMAGE_WIDTH, nueva_altura), Image.LANCZOS)

    # JPEG no soporta canal alfa: sin esta conversion el guardado falla para
    # imagenes que vienen en modo RGBA o paleta (P).
    extension = os.path.splitext(destino)[1].lower()
    if extension in (".jpg", ".jpeg") and imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")

    imagen.save(destino, format=formato, quality=JPEG_QUALITY, optimize=True)
