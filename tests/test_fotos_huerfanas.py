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
import sqlalchemy as sa

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


# ------------------------------------------------------------ por cascada

def test_borrar_el_servicio_se_lleva_las_fotos_de_lo_que_cuelga(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """El primer escalon de la cascada. Ninguna vista de este dominio se entera
    de que habia fotos: quien borra es el ORM bajando por Service.solicitudes y
    Service.verificaciones."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    foto_solicitud = foto_en_disco("de-la-solicitud.png")
    foto_verificacion = foto_en_disco("de-la-verificacion.png")
    db.session.add_all([
        ServiceRequest(service_id=servicio.id, cliente_id=cliente.id,
                       descripcion="Se me tapó la pileta", foto=foto_solicitud),
        VerificationRequest(service_id=servicio.id, foto=foto_verificacion),
    ])
    db.session.commit()

    db.session.delete(db.session.get(Service, servicio.id))
    db.session.commit()

    assert not existe(foto_solicitud)
    assert not existe(foto_verificacion)
    assert ServiceRequest.query.count() == 0
    assert VerificationRequest.query.count() == 0


def test_borrar_el_post_se_lleva_las_fotos_de_sus_servicios(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """Dos escalones: Post -> Service -> ServiceRequest/VerificationRequest.
    Este es el caso que motivo hacerlo en el modelo."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    foto_solicitud = foto_en_disco("post-solicitud.png")
    foto_verificacion = foto_en_disco("post-verificacion.png")
    db.session.add_all([
        ServiceRequest(service_id=servicio.id, cliente_id=cliente.id,
                       descripcion="Se me tapó la pileta", foto=foto_solicitud),
        VerificationRequest(service_id=servicio.id, foto=foto_verificacion),
    ])
    db.session.commit()

    db.session.delete(db.session.get(Post, post.id))
    db.session.commit()

    assert not existe(foto_solicitud)
    assert not existe(foto_verificacion)
    assert Service.query.count() == 0


def test_borrar_al_usuario_dueño_se_lleva_las_fotos_de_todo_lo_que_cuelga(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """Tres escalones: User -> Post -> Service -> las dos tablas con foto. El
    camino mas largo, y el que menos se parece a "borrar una foto"."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    foto_solicitud = foto_en_disco("user-solicitud.png")
    foto_verificacion = foto_en_disco("user-verificacion.png")
    db.session.add_all([
        ServiceRequest(service_id=servicio.id, cliente_id=cliente.id,
                       descripcion="Se me tapó la pileta", foto=foto_solicitud),
        VerificationRequest(service_id=servicio.id, foto=foto_verificacion),
    ])
    db.session.commit()

    db.session.delete(db.session.get(User, autor.id))
    db.session.commit()

    assert not existe(foto_solicitud)
    assert not existe(foto_verificacion)
    assert Post.query.count() == 0
    assert Service.query.count() == 0


def test_borrar_al_cliente_borra_la_fila_pero_deja_la_foto(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """HUECO CONOCIDO, no cubierto por el listener. Lo fija como esta hoy.

    service_requests.cliente_id se borra por el ON DELETE CASCADE de la FK, no
    por el ORM: modelo_solicitud.py declara la relacion `cliente` a proposito
    SIN backref con cascada, al reves que `servicio`. La fila la saca el motor,
    el ORM nunca carga la instancia, y sin instancia no hay after_delete: el
    archivo queda huerfano.

    Es el mismo limite que el de SQL crudo (ver el test del final), pero llega
    por un camino normal de la app y no por uno excepcional, asi que va anotado
    aparte. Arreglarlo es una linea -- ponerle backref con cascada del lado de
    User -- pero eso revierte una decision de diseño explicita y hace que borrar
    un usuario cargue todas sus solicitudes en memoria, asi que es una decision
    de Tomás y no de este lote.

    Cuando se decida, este test se da vuelta: pasa a esperar que la foto NO
    exista.
    """
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("del-cliente.png")
    db.session.add(ServiceRequest(
        service_id=servicio.id, cliente_id=cliente.id,
        descripcion="Se me tapó la pileta", foto=nombre,
    ))
    db.session.commit()
    post_id = post.id

    db.session.delete(db.session.get(User, cliente.id))
    db.session.commit()

    # La fila si se va: la cascada de la base funciona.
    assert ServiceRequest.query.count() == 0
    # Pero el archivo se queda, porque el ORM no vio pasar la fila.
    assert existe(nombre)
    # Lo del emprendedor sigue en pie.
    assert db.session.get(Post, post_id) is not None


def test_la_cascada_no_se_lleva_fotos_de_filas_que_no_borra(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """El contrapeso: borrar de mas pasaria igual de desapercibido que no borrar
    nada. Se borra un servicio y el del otro emprendimiento queda intacto."""
    autor = crear_usuario(username="autor")
    post_uno = crear_post(autor.id, title="Uno")
    post_otro = crear_post(autor.id, title="Otro")
    servicio_uno = crear_servicio(post_uno.id)
    servicio_otro = crear_servicio(post_otro.id)
    foto_uno = foto_en_disco("del-uno.png")
    foto_otro = foto_en_disco("del-otro.png")
    db.session.add_all([
        VerificationRequest(service_id=servicio_uno.id, foto=foto_uno),
        VerificationRequest(service_id=servicio_otro.id, foto=foto_otro),
    ])
    db.session.commit()

    db.session.delete(db.session.get(Post, post_uno.id))
    db.session.commit()

    assert not existe(foto_uno)
    assert existe(foto_otro)
    assert VerificationRequest.query.count() == 1


# ------------------------------------------------- el limite, fijado a proposito

def test_un_delete_crudo_borra_la_fila_pero_deja_la_foto(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """LIMITE CONOCIDO Y ACEPTADO, no un bug pendiente.

    Un evento de mapper corre cuando el ORM procesa la instancia en el flush.
    Con un DELETE crudo no hay instancia que procesar: la fila se va y el
    listener nunca se entera, asi que el archivo queda huerfano igual que antes
    de este lote.

    Es la misma distincion que quedo a la vista con reviews.post_id, al reves:
    alla el ORM tapaba que faltaba la constraint, aca la constraint (o el SQL
    directo) tapa que el ORM no corrio. Cubrirlo pediria un trigger en el motor,
    que es otro alcance.

    El test existe para que el limite este medido y no supuesto: si algun dia se
    agrega el trigger, este test se da vuelta y avisa.
    """
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("sobrevive-al-sql.png")
    verificacion = VerificationRequest(service_id=servicio.id, foto=nombre)
    db.session.add(verificacion)
    db.session.commit()
    verificacion_id = verificacion.id

    db.session.execute(
        sa.text("DELETE FROM verification_requests WHERE id = :i"),
        {"i": verificacion_id},
    )
    db.session.commit()

    # La fila se fue...
    assert db.session.execute(
        sa.text("SELECT COUNT(*) FROM verification_requests")
    ).scalar() == 0
    # ...y el archivo se quedo. Esto es lo que el listener NO cubre.
    assert existe(nombre)


def test_un_delete_masivo_del_orm_tampoco_dispara_el_listener(
    db, crear_usuario, crear_post, crear_servicio, foto_en_disco
):
    """La otra forma del mismo limite, y la mas facil de escribir sin querer:
    Query.delete() emite un solo DELETE sin cargar las instancias, asi que se
    comporta como el SQL crudo. Queda fijado para que se sepa que ese atajo no
    es equivalente a recorrer y borrar una por una."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    servicio = crear_servicio(post.id)
    nombre = foto_en_disco("sobrevive-al-bulk.png")
    db.session.add(VerificationRequest(service_id=servicio.id, foto=nombre))
    db.session.commit()

    VerificationRequest.query.filter_by(service_id=servicio.id).delete(
        synchronize_session=False
    )
    db.session.commit()

    assert VerificationRequest.query.count() == 0
    assert existe(nombre)
