"""Tests de validacion y guardado de imagenes subidas."""

import io
import os

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from services.uploads import allowed_file, save_post_image


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
