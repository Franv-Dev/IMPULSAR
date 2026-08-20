"""Que la foto de una solicitud o una verificacion se vaya con su fila.

Hasta este lote no se iba: las cuatro llamadas a borrar_de_disco de
app/servicios/vistas.py son de rollback (limpian lo que escribio un intento que
despues fallo) y ninguna cubria el borrado de una fila ya guardada. El archivo
quedaba ocupando disco para siempre, sin nada que lo referenciara.

Los tests trabajan sobre archivos de verdad en la carpeta privada del entorno
de test (ver la fixture de subidas en conftest.py), no sobre mocks: lo que se
quiere probar es justamente que el archivo desaparezca del disco.
"""

import os

import pytest

from app.servicios.modelo import Rubros, Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.servicios.modelo_verificacion import EstadosVerificacion, VerificationRequest
from app.blog.modelo_post import Post
from models.user import User
from services.uploads import carpeta_privada


@pytest.fixture
def crear_servicio(db):
    """Fabrica minima de servicios. Local a este archivo: la de test_services.py
    no esta en conftest, y aca solo hace falta un servicio del que colgar la
    solicitud o la verificacion."""

    def _crear(post_id, titulo="Destapaciones"):
        servicio = Service(post_id=post_id, titulo=titulo, rubro=Rubros.PLOMERIA)
        db.session.add(servicio)
        db.session.commit()
        return servicio

    return _crear


@pytest.fixture
def foto_en_disco(app):
    """Crea un archivo de verdad en la carpeta privada y devuelve su nombre.

    Contenido cualquiera: ninguna de estas rutas abre la imagen, solo la mueven
    y la borran. Lo que importa es que el archivo exista.
    """
    creados = []

    def _crear(nombre="matricula.png"):
        carpeta = carpeta_privada()
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "wb") as f:
            f.write(b"no importa que haya adentro")
        creados.append(ruta)
        return nombre

    yield _crear

    # Por si un test falla antes de borrar: no se ensucia la carpeta compartida.
    for ruta in creados:
        if os.path.exists(ruta):
            os.remove(ruta)


def existe(nombre):
    return os.path.exists(os.path.join(carpeta_privada(), nombre))


# ------------------------------------------------------- borrado directo

def test_borrar_una_solicitud_se_lleva_su_foto(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("solicitud.png")
    solicitud = ServiceRequest(
        service_id=servicio.id, cliente_id=cliente.id,
        descripcion="Se me tapó la pileta", foto=nombre,
    )
    db.session.add(solicitud)
    db.session.commit()
    assert existe(nombre)

    db.session.delete(solicitud)
    db.session.commit()

    assert not existe(nombre)
    assert ServiceRequest.query.count() == 0


def test_borrar_una_verificacion_se_lleva_su_foto(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("matricula.png")
    verificacion = VerificationRequest(service_id=servicio.id, foto=nombre)
    db.session.add(verificacion)
    db.session.commit()
    assert existe(nombre)

    db.session.delete(verificacion)
    db.session.commit()

    assert not existe(nombre)
    assert VerificationRequest.query.count() == 0


def test_una_fila_sin_foto_no_rompe_el_borrado(
    db, crear_usuario, crear_post, crear_servicio
):
    """foto es nullable en las dos tablas: el listener tiene que no hacer nada,
    no explotar con un None."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    solicitud = ServiceRequest(
        service_id=servicio.id, cliente_id=cliente.id,
        descripcion="Sin foto", foto=None,
    )
    db.session.add(solicitud)
    db.session.commit()

    db.session.delete(solicitud)
    db.session.commit()

    assert ServiceRequest.query.count() == 0


def test_un_archivo_que_ya_no_esta_no_rompe_el_borrado(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """La fila puede apuntar a un archivo que alguien borro a mano. borrar_de_disco
    ya ignora eso en silencio; aca se fija que el camino nuevo tampoco lo
    convierta en un error."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("se-borro-sola.png")
    verificacion = VerificationRequest(service_id=servicio.id, foto=nombre)
    db.session.add(verificacion)
    db.session.commit()
    os.remove(os.path.join(carpeta_privada(), nombre))

    db.session.delete(verificacion)
    db.session.commit()

    assert VerificationRequest.query.count() == 0


def test_un_rollback_no_se_lleva_la_foto(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """El archivo se borra en el commit y no en el flush, justamente por esto:
    un borrado que despues se deshace tiene que dejar el archivo donde estaba.
    Si se borrara en el after_delete, la fila volveria apuntando a la nada."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("sobrevive.png")
    verificacion = VerificationRequest(service_id=servicio.id, foto=nombre)
    db.session.add(verificacion)
    db.session.commit()

    db.session.delete(verificacion)
    db.session.flush()          # el after_delete ya corrio
    assert existe(nombre)       # pero todavia no se toco el disco
    db.session.rollback()

    assert existe(nombre)
    assert VerificationRequest.query.count() == 1
