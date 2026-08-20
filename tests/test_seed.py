"""El script de datos de prueba (python -m scripts.seed)."""

import os

import pytest

from db import db as _db
from models.user import User
from scripts.seed.carga import cargar
from scripts.seed.imagenes import PREFIJO_IMAGEN


@pytest.fixture
def carpeta_de_esta_carga(app, tmp_path):
    """Una carpeta de uploads propia de este test, y no la de la corrida.

    El sufijo de corrida de los nombres (imagenes.CORRIDA) se calcula una sola
    vez al importar el modulo, asi que dos cargas dentro del mismo proceso
    generan los mismos nombres de archivo. Compartiendo carpeta, un test
    pisaria y despues limpiaria las imagenes del otro.
    """
    carpeta = tmp_path / "uploads"
    carpeta.mkdir()
    app.config["UPLOAD_FOLDER"] = str(carpeta)
    return carpeta


def _imagenes_de_seed(app):
    carpeta = app.config["UPLOAD_FOLDER"]
    return {n for n in os.listdir(carpeta) if n.startswith(PREFIJO_IMAGEN)}


def test_una_carga_completa_deja_sus_imagenes(app, carpeta_de_esta_carga):
    """El contrapeso del test de abajo: no hay que limpiar de mas."""
    cargar(app)

    assert _imagenes_de_seed(app)
    assert User.query.count() > 0


def test_si_la_carga_falla_no_deja_imagenes_huerfanas(
    app, carpeta_de_esta_carga, monkeypatch
):
    """Los PNG se escriben mientras se arman las filas, mucho antes del commit.

    Si algo falla en el medio, el rollback deshace la base pero los archivos
    quedan: nadie los referencia, y borrar() tampoco los encuentra despues
    porque busca por los nombres que estan cargados en la base.
    """
    def explotar():
        raise RuntimeError("la base se cayo a mitad de la carga")

    monkeypatch.setattr(_db.session, "commit", explotar)

    with pytest.raises(RuntimeError):
        cargar(app)

    assert _imagenes_de_seed(app) == set()
    assert User.query.count() == 0


def test_si_falla_generando_una_imagen_tampoco_queda_la_de_esa_vuelta(
    app, carpeta_de_esta_carga, monkeypatch
):
    """El caso del medio: la excepcion sale de adentro de _generar_imagen.

    No es lo mismo que fallar entre dos imagenes. Si el imagen.save() se corta
    a mitad -- disco lleno, permisos -- el archivo ya existe en disco pero
    _generar_imagen nunca vuelve, asi que hasta que el nombre se anoto DESPUES
    de generar, esa imagen no quedaba registrada en ningun lado y la limpieza
    pasaba de largo justo por la unica que si habia que borrar.
    """
    from scripts.seed import carga

    real = carga._generar_imagen
    cuantas = []

    def cortar_a_mitad(carpeta, nombre, texto, color):
        cuantas.append(nombre)
        if len(cuantas) < 3:
            return real(carpeta, nombre, texto, color)
        # Lo que deja un save() interrumpido: el archivo abierto y a medio
        # escribir, y la excepcion saliendo antes del return.
        (carpeta_de_esta_carga / nombre).write_bytes(b"\x89PNG a medio escri")
        raise OSError("No space left on device")

    monkeypatch.setattr(carga, "_generar_imagen", cortar_a_mitad)

    with pytest.raises(OSError):
        cargar(app)

    assert _imagenes_de_seed(app) == set()
    assert User.query.count() == 0
