"""Tests de validacion y guardado de imagenes subidas."""

import io
import os

import pytest
from PIL import Image, ImageOps
from werkzeug.datastructures import FileStorage

from services import uploads
from services.uploads import MAX_IMAGE_WIDTH, allowed_file, save_post_image


@pytest.fixture
def upload_dir(tmp_path):
    """Carpeta temporal distinta para cada test."""
    return str(tmp_path / "uploads")


def _imagen_real(formato="PNG", nombre="foto.png"):
    """Genera una imagen valida en memoria, como si la subiera un usuario."""
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "purple").save(buffer, format=formato)
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=nombre)


def test_allowed_file_acepta_extensiones_de_imagen():
    assert allowed_file("foto.jpg")
    assert allowed_file("imagen.PNG")
    assert allowed_file("algo.JPEG")
    assert allowed_file("animacion.gif")


def test_allowed_file_rechaza_otros_formatos():
    assert not allowed_file("documento.pdf")
    assert not allowed_file("script.exe")
    assert not allowed_file("sin_extension")


def test_guarda_una_imagen_valida(upload_dir):
    filename, error = save_post_image(_imagen_real(), upload_dir)

    assert error is None
    assert filename is not None
    assert os.path.exists(os.path.join(upload_dir, filename))


def test_el_nombre_se_hace_unico(upload_dir):
    """Dos usuarios que suben "foto.png" no se deben pisar el archivo."""
    primero, _ = save_post_image(_imagen_real(), upload_dir)
    segundo, _ = save_post_image(_imagen_real(), upload_dir)

    assert primero != segundo
    assert len(os.listdir(upload_dir)) == 2


def test_rechaza_un_archivo_que_no_es_imagen_aunque_tenga_extension_valida(upload_dir):
    """La extension se falsifica facil: hay que mirar el contenido real."""
    falso = FileStorage(
        stream=io.BytesIO(b"MZ\x90\x00 esto es un ejecutable, no una imagen"),
        filename="virus.jpg",
    )

    filename, error = save_post_image(falso, upload_dir)

    assert filename is None
    assert "no parece ser una imagen" in error
    assert not os.path.exists(upload_dir) or os.listdir(upload_dir) == []


def test_rechaza_extension_no_permitida(upload_dir):
    archivo = FileStorage(stream=io.BytesIO(b"contenido"), filename="documento.pdf")

    filename, error = save_post_image(archivo, upload_dir)

    assert filename is None
    assert "Formato de imagen no permitido" in error


def test_sin_archivo_no_es_error(upload_dir):
    """No subir imagen es valido: el post simplemente queda sin foto."""
    assert save_post_image(None, upload_dir) == (None, None)
    assert save_post_image(FileStorage(filename=""), upload_dir) == (None, None)


# --- tamanio: lo que entra, lo que se comprime y lo que rebota

def _imagen_pesada(megabytes, nombre="foto.jpg"):
    """Una foto grande de verdad, del orden de peso que pide el test.

    Ruido y no un color solido: un JPEG de un color plano se comprime a nada y
    nunca llegaria a pesar los MB que el test quiere probar. El tamanio en px se
    elige para que el archivo quede por encima del peso pedido, y despues se
    verifica: si Pillow comprime mejor de lo esperado, el test tiene que fallar
    en vez de pasar probando otra cosa.
    """
    import os as _os

    # Medido: el ruido en JPEG q95 da ~1.18 bytes por pixel. Se divide por 1.1
    # para dejar margen y que el archivo salga por arriba del peso pedido.
    lado = int((megabytes * 1024 * 1024 / 1.1) ** 0.5)
    ruido = Image.frombytes("RGB", (lado, lado), _os.urandom(lado * lado * 3))
    buffer = io.BytesIO()
    ruido.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    assert buffer.getbuffer().nbytes >= megabytes * 1024 * 1024, (
        "la imagen de prueba salio mas chica de lo que el test necesita"
    )
    return FileStorage(stream=buffer, filename=nombre, content_type="image/jpeg")


def test_una_foto_de_8_mb_se_guarda_comprimida(upload_dir):
    """Con el limite viejo de 5 MB esta foto rebotaba antes de llegar al codigo.

    Es el caso que motivo la tanda: la compresion existia y no la alcanzaba
    nadie. Ahora entra y se guarda ya redimensionada.
    """
    filename, error = save_post_image(_imagen_pesada(8), upload_dir)

    assert error is None
    assert filename

    guardada = os.path.join(upload_dir, filename)
    with Image.open(guardada) as imagen:
        assert imagen.width == MAX_IMAGE_WIDTH
    # Lo que importa no es solo que entre, sino que ocupe poco en disco: lo que
    # se guarda es la version chica, no los 8 MB que subieron.
    assert os.path.getsize(guardada) < 1024 * 1024


def test_el_tope_de_bytes_sigue_rechazando_un_archivo_enorme(client, crear_usuario, login):
    """16 MB pasan el tope y Flask corta la request antes de que corra la vista.

    Se prueba por HTTP y no llamando a save_post_image, porque el que corta es
    MAX_CONTENT_LENGTH y no este modulo: la request nunca llega aca.

    El mensaje se lee de la sesion y no del HTML de la pagina siguiente: el
    handler redirige al referrer, que en un test no existe, y la home a la que
    cae no pinta los flashes. Mirar el HTML haria pasar el test por no encontrar
    el texto en una pagina que igual no lo iba a mostrar.
    """
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    respuesta = client.post(
        "/blog/create",
        data={
            "title": "Panadería", "body": "Pan", "category": "gastronomia",
            "address_street": "",
            "image": (io.BytesIO(b"x" * (16 * 1024 * 1024)), "enorme.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert respuesta.status_code == 303
    with client.session_transaction() as sesion:
        mensajes = [texto for _categoria, texto in sesion.get("_flashes", [])]
    assert any("demasiado grande" in texto for texto in mensajes)
    assert any("15 MB" in texto for texto in mensajes)


def test_rechaza_una_imagen_con_demasiados_pixeles(upload_dir, monkeypatch):
    """El caso que el default de Pillow deja pasar: entre MAX_IMAGE_PIXELS y el
    doble solo emite un warning y decodifica igual.

    El tope se baja con monkeypatch en vez de generar una imagen de 50 Mpx de
    verdad: fabricarla costaria los 150 MB de RAM que el limite existe para
    evitar. Lo que se prueba es el chequeo, y ese no sabe de que numero se trata.
    """
    monkeypatch.setattr(uploads, "MAX_IMAGE_PIXELS", 100)

    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), "purple").save(buffer, format="PNG")  # 2500 px
    buffer.seek(0)
    grande = FileStorage(stream=buffer, filename="bomba.png")

    filename, error = save_post_image(grande, upload_dir)

    assert filename is None
    assert "demasiados píxeles" in error
    assert not os.path.exists(upload_dir) or os.listdir(upload_dir) == []


def test_una_imagen_justo_por_debajo_del_tope_de_pixeles_pasa(upload_dir, monkeypatch):
    """El control negativo del test anterior: sin el, "rechaza" podria estar
    rechazando todo."""
    monkeypatch.setattr(uploads, "MAX_IMAGE_PIXELS", 2500)

    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), "purple").save(buffer, format="PNG")  # 2500 px justos
    buffer.seek(0)

    filename, error = save_post_image(
        FileStorage(stream=buffer, filename="justa.png"), upload_dir
    )

    assert error is None
    assert filename


def test_el_freno_duro_de_pillow_quedo_atado_a_nuestra_constante():
    """Sin esto, el freno de Pillow seguiria en su default de 89.5 Mpx y la
    franja donde solo avisa llegaria hasta 179 Mpx."""
    assert Image.MAX_IMAGE_PIXELS == uploads.MAX_IMAGE_PIXELS


# --- orientacion EXIF

def _foto_con_exif_rotada(ancho, alto, nombre="vertical.jpg"):
    """Una foto guardada vertical que el EXIF marca para mostrar horizontal.

    Es el caso tipico del celular: el sensor graba siempre igual y la
    orientacion real viaja en el metadato 274, que el navegador ignora. Cada
    cuadrante lleva un color distinto para poder verificar despues que la
    rotacion se aplico a los pixeles y no solo al tamanio.
    """
    imagen = Image.new("RGB", (ancho, alto))
    colores = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))
    for indice, color in enumerate(colores):
        izquierda = (indice % 2) * (ancho // 2)
        arriba = (indice // 2) * (alto // 2)
        imagen.paste(color, (izquierda, arriba, izquierda + ancho // 2, arriba + alto // 2))

    exif = imagen.getexif()
    exif[274] = 6  # "rotar para que se vea horizontal"

    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=95, exif=exif)
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=nombre, content_type="image/jpeg"), imagen


def test_una_foto_vertical_con_exif_horizontal_se_rota_y_recien_ahi_se_achica(upload_dir):
    """El orden importa: exif_transpose primero, resize despues.

    La foto se guarda 800x2000 (vertical) y el EXIF la marca para verse
    2000x800 (horizontal). Si el resize corriera antes de la rotacion, miraria
    un ancho de 800, no entraria en el `if` de MAX_IMAGE_WIDTH y la imagen se
    guardaria sin achicar; con el orden correcto, el ancho a mirar es 2000 y
    termina en 1200.

    Tambien cubre que exif_transpose se llame con in_place=True y SIN asignar
    el resultado: en ese modo devuelve None, asi que la version con asignacion
    reventaria en la primera linea que toque `imagen`.
    """
    archivo, original = _foto_con_exif_rotada(800, 2000)

    filename, error = save_post_image(archivo, upload_dir)

    assert error is None

    with Image.open(os.path.join(upload_dir, filename)) as guardada:
        # 2000x800 rotada, achicada contra el ancho de verdad.
        assert guardada.size == (MAX_IMAGE_WIDTH, 480)

        # Y la rotacion se aplico a los pixeles, no solo a las dimensiones: el
        # cuadrante de arriba a la izquierda de la imagen ya rotada tiene que
        # ser el mismo que calcula Pillow por su cuenta sobre el original.
        esperada = ImageOps.exif_transpose(original)
        assert _color_dominante(guardada) == _color_dominante(esperada)


def _color_dominante(imagen):
    """El color del cuadrante de arriba a la izquierda, redondeado.

    Se muestrea bien adentro del cuadrante para no caer en el borde entre dos
    colores, que el JPEG difumina.
    """
    ancho, alto = imagen.size
    pixel = imagen.convert("RGB").getpixel((ancho // 4, alto // 4))
    return tuple(round(canal / 64) for canal in pixel)


def test_exif_transpose_in_place_devuelve_none(upload_dir):
    """El detalle que hace que el fix sea de una palabra y no de una linea.

    Si alguien "prolija" el codigo poniendo `imagen = ImageOps.exif_transpose(
    imagen, in_place=True)`, imagen queda en None y _guardar_comprimida explota.
    Este test fija el porque, para que el comentario no sea la unica defensa.
    """
    imagen = Image.new("RGB", (10, 20))

    assert ImageOps.exif_transpose(imagen, in_place=True) is None
