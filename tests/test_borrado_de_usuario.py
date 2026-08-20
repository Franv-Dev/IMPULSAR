"""Borrar un User que dejo actividad en emprendimientos ajenos.

El caso complementario al de test_blog.py, que cubre borrar al AUTOR y que se
vayan sus emprendimientos. Aca se borra al tercero: el que marco un favorito,
escribio una resenia, denuncio algo o mando mensajes sobre cosas de otro. Hasta
b2b97d078fb2 eso fallaba con IntegrityError, porque las cinco FK que apuntan a
users desde esas tablas estaban en NO ACTION.

Se borra por los dos caminos, y la diferencia importa:

  - la mayoria borra con db.session.delete() + commit, que es lo que hace la
    app. Ese camino pasa antes por las cascadas del ORM, asi que un test que
    pasa aca no prueba por si solo que la FK exista en la base;
  - los que tienen que probar la constraint de verdad borran con SQL crudo
    (db.session.execute(text("DELETE FROM ..."))). Sin ORM en el medio, la
    cascada la hace el motor o no la hace nadie.

Los del final son del otro lado del grafo, reviews.post_id (c1f4a90b6e35): la
unica FK a posts que habia quedado sin CASCADE y que este lote dejo a la vista.
Ahi se ve para que sirve la distincion -- con session.delete() el bug no
aparecia, porque Post.reviews declara cascade="all, delete-orphan" y borraba
las resenias antes de que el motor mirara la FK.
"""

import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from models.message import Message
from models.user import User


def _mensaje(post_id, client_id, sender_id, body="hola"):
    return Message(
        post_id=post_id, client_id=client_id, sender_id=sender_id, body=body
    )


# ------------------------------------------------------ una FK por vez

def test_borrar_un_usuario_se_lleva_sus_favoritos(db, crear_usuario, crear_post):
    """favorites.user_id. El favorito es una marca privada sobre contenido
    ajeno: no le sirve a nadie mas que a quien lo puso."""
    autor = crear_usuario(username="autor")
    curioso = crear_usuario(username="curioso")
    post = crear_post(autor.id)
    db.session.add(Favorite(user_id=curioso.id, post_id=post.id))
    db.session.commit()
    post_id = post.id

    db.session.delete(db.session.get(User, curioso.id))
    db.session.commit()

    assert Favorite.query.count() == 0
    # El emprendimiento del otro no se toca.
    assert db.session.get(Post, post_id) is not None


def test_borrar_un_usuario_se_lleva_sus_resenias(db, crear_usuario, crear_post):
    """reviews.user_id. La resenia se va con quien la escribio aunque sea sobre
    un emprendimiento ajeno, que es la decision tomada para b2b97d078fb2."""
    autor = crear_usuario(username="autor")
    critico = crear_usuario(username="critico")
    post = crear_post(autor.id)
    db.session.add(Review(post_id=post.id, user_id=critico.id, rating=4, comment="Rico"))
    db.session.commit()
    post_id = post.id

    db.session.delete(db.session.get(User, critico.id))
    db.session.commit()

    assert Review.query.count() == 0
    assert db.session.get(Post, post_id) is not None


def test_borrar_un_usuario_se_lleva_sus_denuncias(db, crear_usuario, crear_post):
    """reports.reporter_id. Si la denuncia estaba pendiente desaparece de la
    cola del admin sin resolver, que es la contrapartida asumida."""
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    db.session.add(Report(reporter_id=denunciante.id, post_id=post.id, reason="spam"))
    db.session.commit()
    post_id = post.id

    db.session.delete(db.session.get(User, denunciante.id))
    db.session.commit()

    assert Report.query.count() == 0
    assert db.session.get(Post, post_id) is not None


# ------------------------------------------------- las dos FK de messages

def test_borrar_al_cliente_se_lleva_el_hilo_entero(db, crear_usuario, crear_post):
    """messages.client_id. El hilo se identifica por (post_id, client_id), asi
    que la cascada de esa columna se lleva la conversacion completa, incluidos
    los mensajes que escribio el emprendedor del otro lado: un hilo sin el
    cliente que lo abrio no es una conversacion, es media."""
    duenio = crear_usuario(username="duenio")
    cliente = crear_usuario(username="cliente")
    post = crear_post(duenio.id)
    db.session.add_all([
        _mensaje(post.id, cliente.id, cliente.id, "¿Hacen envios?"),
        _mensaje(post.id, cliente.id, duenio.id, "Si, hasta las 18"),
        _mensaje(post.id, cliente.id, cliente.id, "Genial, gracias"),
    ])
    db.session.commit()
    post_id, duenio_id = post.id, duenio.id

    db.session.delete(db.session.get(User, cliente.id))
    db.session.commit()

    # Las tres, no solo las dos que escribio el cliente.
    assert Message.query.count() == 0
    assert db.session.get(Post, post_id) is not None
    assert db.session.get(User, duenio_id) is not None


def test_borrar_a_un_remitente_suelto_deja_el_resto_del_hilo(
    db, crear_usuario, crear_post
):
    """messages.sender_id. Se lleva solo lo que escribio esa persona, porque es
    contenido suyo, y la conversacion sigue en pie.

    El tercer remitente se arma a mano: hoy la app solo pone como sender al
    cliente o al dueño del emprendimiento, y con cualquiera de esos dos la
    cascada de client_id o la de posts.author se llevarian el hilo igual y no
    se veria que hace sender_id por su cuenta.
    """
    duenio = crear_usuario(username="duenio")
    cliente = crear_usuario(username="cliente")
    tercero = crear_usuario(username="tercero")
    post = crear_post(duenio.id)
    db.session.add_all([
        _mensaje(post.id, cliente.id, cliente.id, "¿Hacen envios?"),
        _mensaje(post.id, cliente.id, tercero.id, "Yo tambien quiero saber"),
        _mensaje(post.id, cliente.id, duenio.id, "Si, hasta las 18"),
    ])
    db.session.commit()
    cliente_id = cliente.id

    db.session.delete(db.session.get(User, tercero.id))
    db.session.commit()

    assert Message.query.count() == 2
    assert [m.body for m in Message.query.order_by(Message.id)] == [
        "¿Hacen envios?", "Si, hasta las 18",
    ]
    # Y el cliente del hilo sigue existiendo: no se lo llevo de arrastre.
    assert db.session.get(User, cliente_id) is not None


def test_borrar_los_dos_lados_de_una_conversacion_no_depende_del_orden(
    db, crear_usuario, crear_post
):
    """La pregunta que abre tener dos FK a users en la misma tabla: si se van
    las dos personas, ninguna de las dos cascadas puede quedar apuntando a un
    id que ya no existe. Lo que se borro primero ya no esta cuando se evalua la
    segunda, asi que el orden no cambia el resultado."""
    duenio = crear_usuario(username="duenio")
    cliente = crear_usuario(username="cliente")
    post = crear_post(duenio.id)
    db.session.add_all([
        _mensaje(post.id, cliente.id, cliente.id, "hola"),
        _mensaje(post.id, cliente.id, duenio.id, "buenas"),
    ])
    db.session.commit()

    db.session.delete(db.session.get(User, cliente.id))
    db.session.delete(db.session.get(User, duenio.id))
    db.session.commit()  # el mismo flush se lleva a los dos

    assert Message.query.count() == 0
    assert Post.query.count() == 0
    assert User.query.count() == 0


def test_un_mensaje_donde_el_usuario_es_cliente_y_remitente_se_borra_una_vez(
    db, crear_usuario, crear_post
):
    """La fila cae bajo las dos cascadas a la vez. No es un error ni un doble
    borrado: la fila se va una sola vez y el commit no levanta nada."""
    duenio = crear_usuario(username="duenio")
    cliente = crear_usuario(username="cliente")
    post = crear_post(duenio.id)
    db.session.add(_mensaje(post.id, cliente.id, cliente.id, "solo yo"))
    db.session.commit()
    duenio_id = duenio.id

    db.session.delete(db.session.get(User, cliente.id))
    db.session.commit()

    assert Message.query.count() == 0
    assert db.session.get(User, duenio_id) is not None


# ------------------------------------------------------ todo junto

def test_borrar_un_usuario_con_actividad_en_las_cinco_tablas(
    db, crear_usuario, crear_post
):
    """El caso que motivo el lote: un usuario que participo de todo. Antes
    fallaba con IntegrityError en la primera FK que encontrara."""
    autor = crear_usuario(username="autor")
    activo = crear_usuario(username="activo")
    post = crear_post(autor.id)
    resenia = Review(post_id=post.id, user_id=activo.id, rating=3, comment="Ni fu")
    db.session.add(resenia)
    db.session.commit()
    db.session.add_all([
        Favorite(user_id=activo.id, post_id=post.id),
        Report(reporter_id=activo.id, review_id=resenia.id, reason="ofensiva"),
        _mensaje(post.id, activo.id, activo.id, "¿abren el domingo?"),
        _mensaje(post.id, activo.id, autor.id, "no, solo sabados"),
    ])
    db.session.commit()
    post_id, autor_id = post.id, autor.id

    db.session.delete(db.session.get(User, activo.id))
    db.session.commit()

    assert Favorite.query.count() == 0
    assert Review.query.count() == 0
    assert Report.query.count() == 0
    assert Message.query.count() == 0
    # Lo del otro sigue intacto.
    assert db.session.get(Post, post_id) is not None
    assert db.session.get(User, autor_id) is not None


def test_borrar_un_usuario_no_toca_la_actividad_de_los_demas(
    db, crear_usuario, crear_post
):
    """El contrapeso: la cascada tiene que llevarse lo del usuario borrado y
    nada mas. Sin este test, un CASCADE de mas pasaria igual de desapercibido
    que el IntegrityError que se vino a arreglar."""
    autor = crear_usuario(username="autor")
    uno = crear_usuario(username="uno")
    otro = crear_usuario(username="otro")
    post = crear_post(autor.id)
    db.session.add_all([
        Favorite(user_id=uno.id, post_id=post.id),
        Favorite(user_id=otro.id, post_id=post.id),
        Review(post_id=post.id, user_id=uno.id, rating=5, comment="de uno"),
        Review(post_id=post.id, user_id=otro.id, rating=1, comment="de otro"),
        _mensaje(post.id, uno.id, uno.id, "hilo de uno"),
        _mensaje(post.id, otro.id, otro.id, "hilo de otro"),
    ])
    db.session.commit()
    otro_id = otro.id

    db.session.delete(db.session.get(User, uno.id))
    db.session.commit()

    assert [f.user_id for f in Favorite.query] == [otro_id]
    assert [r.comment for r in Review.query] == ["de otro"]
    assert [m.body for m in Message.query] == ["hilo de otro"]


def test_borrar_un_usuario_sin_nada_sigue_funcionando(db, crear_usuario):
    """El caso de 0 filas, que es el unico que la version vieja tampoco rompia:
    que la cascada nueva no lo haya complicado."""
    solo = crear_usuario(username="solo")
    solo_id = solo.id

    db.session.delete(db.session.get(User, solo_id))
    db.session.commit()

    assert db.session.get(User, solo_id) is None


def test_las_cinco_fk_declaran_cascade_en_el_esquema(db):
    """El esquema y no el comportamiento: si alguien recrea una de estas FK sin
    ondelete, los tests de arriba siguen pasando en cualquier motor que no
    verifique FK, y este no."""
    esperadas = {
        ("favorites", "user_id"), ("reviews", "user_id"),
        ("reports", "reporter_id"),
        ("messages", "client_id"), ("messages", "sender_id"),
    }
    encontradas = set()
    for tabla, columna in esperadas:
        modelo = db.metadata.tables[tabla]
        for fk in modelo.c[columna].foreign_keys:
            if fk.column.table.name == "users":
                assert fk.ondelete == "CASCADE", f"{tabla}.{columna} sin CASCADE"
                encontradas.add((tabla, columna))

    assert encontradas == esperadas


def test_las_fk_a_users_se_verifican_de_verdad_en_los_tests(db, crear_usuario):
    """El control del control: si SQLite corriera con las FK apagadas, todos
    los tests de arriba pasarian sin probar nada. Se fuerza una violacion a
    mano y tiene que saltar."""
    autor = crear_usuario(username="autor")
    post = Post(author=autor.id, title="P", body="B")
    db.session.add(post)
    db.session.commit()

    db.session.add(Favorite(user_id=999999, post_id=post.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_un_evento_viejo_no_bloquea_el_borrado(db, crear_usuario, crear_post):
    """Cierra el lote por el otro lado: lo que ya cascadeaba antes (posts y lo
    que cuelga de ellos) sigue haciendolo despues del cambio."""
    from models.event import Event

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Event(post_id=post.id, titulo="Feria", fecha=datetime.date(2026, 9, 1)))
    db.session.commit()

    db.session.delete(db.session.get(User, autor.id))
    db.session.commit()

    assert Post.query.count() == 0
    assert Event.query.count() == 0


# ------------------------------------------- reviews.post_id (c1f4a90b6e35)

def test_borrar_al_autor_se_lleva_las_resenias_que_le_dejaron(
    db, crear_usuario, crear_post
):
    """El complemento de test_borrar_un_usuario_se_lleva_sus_resenias: aca la
    resenia es de otro y el que se va es el AUTOR del emprendimiento. La
    resenia tiene que irse con el post, no quedar apuntando a un post que ya no
    esta ni frenar el borrado."""
    autor = crear_usuario(username="autor")
    critico = crear_usuario(username="critico")
    post = crear_post(autor.id)
    db.session.add(Review(post_id=post.id, user_id=critico.id, rating=2, comment="Meh"))
    db.session.commit()
    critico_id = critico.id

    db.session.delete(db.session.get(User, autor.id))
    db.session.commit()

    assert Post.query.count() == 0
    assert Review.query.count() == 0
    # El que la escribio sigue existiendo: se fue la resenia, no la persona.
    assert db.session.get(User, critico_id) is not None


def test_borrar_al_autor_por_sql_crudo_tambien_se_lleva_la_resenia_ajena(
    db, crear_usuario, crear_post
):
    """El mismo caso pero sin pasar por la sesion, que es donde se veia el bug.

    db.session.delete(user) hace que el ORM baje post por post y borre las
    resenias con DELETE propios (Post.reviews tiene cascade="all,
    delete-orphan"), asi que el test de arriba pasa aunque la FK este en NO
    ACTION: el motor nunca llega a evaluarla. Con un DELETE crudo no hay ORM en
    el medio y la cascada la tiene que hacer la base o nada.
    """
    autor = crear_usuario(username="autor")
    critico = crear_usuario(username="critico")
    post = crear_post(autor.id)
    db.session.add(Review(post_id=post.id, user_id=critico.id, rating=5, comment="Top"))
    db.session.commit()
    autor_id, critico_id = autor.id, critico.id

    db.session.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": autor_id})
    db.session.commit()

    # Contado por SQL y no por el ORM: la sesion todavia tiene los objetos
    # viejos en su identity map y responderia con lo que ya no esta.
    contar = lambda tabla: db.session.execute(
        sa.text(f"SELECT COUNT(*) FROM {tabla}")
    ).scalar()
    assert contar("posts") == 0
    assert contar("reviews") == 0
    assert contar("users") == 1  # queda el critico


def test_reviews_post_id_declara_cascade_en_el_esquema(db):
    """Igual que test_las_cinco_fk_declaran_cascade_en_el_esquema pero para la
    FK a posts: el comportamiento de arriba se puede conseguir por el camino
    del ORM, la declaracion no."""
    columna = db.metadata.tables["reviews"].c["post_id"]
    fks = [fk for fk in columna.foreign_keys if fk.column.table.name == "posts"]
    assert fks, "reviews.post_id ya no apunta a posts"
    for fk in fks:
        assert fk.ondelete == "CASCADE", "reviews.post_id sin CASCADE"


def test_borrar_los_dos_lados_de_un_hilo_ajeno_al_post(db, crear_usuario, crear_post):
    """La asimetria de messages sin que la tape la cascada del post.

    test_borrar_los_dos_lados_de_una_conversacion_no_depende_del_orden borra al
    cliente y al dueño, pero el dueño se lleva el post y el post se lleva los
    mensajes por posts.author, asi que no prueba que las dos FK a users
    convivan: probaria lo mismo sin ninguna de las dos. Aca el dueño del
    emprendimiento no se toca y los dos que se borran son terceros, uno como
    client_id y otro solo como sender_id.
    """
    duenio = crear_usuario(username="duenio")
    cliente = crear_usuario(username="cliente")
    tercero = crear_usuario(username="tercero")
    post = crear_post(duenio.id)
    db.session.add_all([
        _mensaje(post.id, cliente.id, cliente.id, "¿hacen envios?"),
        _mensaje(post.id, cliente.id, tercero.id, "yo tambien pregunto"),
        _mensaje(post.id, cliente.id, duenio.id, "si, hasta las 18"),
    ])
    db.session.commit()
    post_id, duenio_id = post.id, duenio.id

    db.session.delete(db.session.get(User, cliente.id))
    db.session.delete(db.session.get(User, tercero.id))
    db.session.commit()

    # Las tres: dos por sender_id y la del dueño por client_id.
    assert Message.query.count() == 0
    # Y lo que no era de ellos sigue en pie.
    assert db.session.get(Post, post_id) is not None
    assert db.session.get(User, duenio_id) is not None
