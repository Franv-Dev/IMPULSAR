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
