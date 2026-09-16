"""Un emprendimiento en borrador no existe para nadie mas que su dueño.

LO QUE HAY QUE ENTENDER ANTES DE TOCAR ESTE ARCHIVO. El estado no se guarda para
mostrar una etiqueta: se guarda para que la fila no aparezca. Y "no aparecer" no
es una pantalla, son ONCE superficies publicas distintas, cada una con su propia
consulta: el listado, la busqueda, el home, la ficha, las dos APIs, el perfil
publico, las reseñas recibidas, el catalogo de productos, la busqueda de
servicios y la cartelera de eventos. Mas los dos listados de marcados
(emprendimientos y productos guardados), que son de un tercero.

Por eso el test central es un BARRIDO y no un test por pantalla: lo que se
prueba es una propiedad del sistema ("no hay ninguna puerta"), y un test por
pantalla deja pasar justamente la puerta que nadie se acordo de escribir. Cuando
se agregue una superficie publica nueva, va en la lista de abajo.

Y CADA AFIRMACION VA CONTRA UN CONTROL PUBLICADO. Sin eso, el barrido pasaria
igual con las paginas rotas, vacias, o con un filtro que se lleva todo puesto:
"no aparece el borrador" es trivialmente cierto en una pagina que no muestra
nada. El control es lo que distingue "filtra bien" de "no muestra nada".
"""

from datetime import timedelta

import pytest

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import EstadosPost
from app.blog.modelo_resenia import Review
from app.servicios.modelo import Rubros, Service
from models.event import Event
from models.product import Product
from models.product_favorite import ProductFavorite
from models.user import Roles
from services.eventos import hoy_en_argentina

#: Lo que se busca en cada pantalla para saber si el emprendimiento se filtro.
#: Son nombres inventados y distintos entre si a proposito: si el borrador y el
#: control se llamaran parecido, un assert podria dar positivo por el otro.
BORRADOR = "Taller Secreto"
PUBLICADO = "Panaderia Abierta"


@pytest.fixture
def dos_emprendimientos(db, crear_usuario, crear_post):
    """Un borrador y un publicado, cada uno con todo lo que cuelga de un post.

    Los dos con producto, servicio, evento y reseña: son las cuatro cosas que
    tienen pantalla publica propia y que salen de una consulta que NO es la de
    posts, asi que cada una es una puerta distinta por la que el borrador podria
    colarse.
    """
    dueno = crear_usuario(username="dueno", rol=Roles.EMPRENDEDOR)
    visitante = crear_usuario(username="visitante")

    def armar(titulo, estado):
        post = crear_post(
            dueno.id, title=titulo, body=f"Descripcion de {titulo}",
            category="alimentos", estado=estado,
        )
        db.session.add(Product(
            post_id=post.id, nombre=f"Producto de {titulo}", precio=1500,
        ))
        db.session.add(Service(
            post_id=post.id, titulo=f"Servicio de {titulo}",
            rubro=Rubros.PLOMERIA, descripcion="Arreglos",
            zona_cobertura="Toda la ciudad",
        ))
        db.session.add(Event(
            post_id=post.id, titulo=f"Feria de {titulo}",
            fecha=hoy_en_argentina() + timedelta(days=5),
        ))
        db.session.add(Review(
            post_id=post.id, user_id=visitante.id, rating=5,
            comment=f"Muy bueno {titulo}",
        ))
        db.session.commit()
        return post

    borrador = armar(BORRADOR, EstadosPost.BORRADOR)
    publicado = armar(PUBLICADO, EstadosPost.PUBLICADO)

    # El visitante marca los dos como favoritos, y tambien sus productos: los
    # dos listados de marcados son pantallas mas por las que el borrador podria
    # seguir viendose despues de que su dueño lo saco de circulacion.
    for post in (borrador, publicado):
        db.session.add(Favorite(user_id=visitante.id, post_id=post.id))
        producto = Product.query.filter_by(post_id=post.id).first()
        db.session.add(ProductFavorite(
            user_id=visitante.id, product_id=producto.id,
        ))
    db.session.commit()

    return {
        "dueno": dueno, "visitante": visitante,
        "borrador": borrador, "publicado": publicado,
    }


def _texto(respuesta):
    return respuesta.get_data(as_text=True)


#: Las superficies publicas que listan emprendimientos o algo que cuelga de
#: ellos. Cada una es (para que sirve, la URL, que se busca del borrador, que se
#: busca del publicado). Las dos ultimas columnas son distintas por pantalla
#: porque el catalogo muestra el nombre del PRODUCTO y la cartelera el del
#: EVENTO, no el del emprendimiento.
SUPERFICIES_PUBLICAS = [
    ("el listado", "/blog/", BORRADOR, PUBLICADO),
    ("la busqueda por texto", "/blog/?q=de", BORRADOR, PUBLICADO),
    ("la busqueda por rubro", "/blog/?category=alimentos", BORRADOR, PUBLICADO),
    ("la API de posts", "/api/posts/", BORRADOR, PUBLICADO),
    ("la API de posts con busqueda", "/api/posts/?q=Descripcion", BORRADOR, PUBLICADO),
    ("el catalogo de productos", "/productos/",
     f"Producto de {BORRADOR}", f"Producto de {PUBLICADO}"),
    ("la busqueda de servicios", "/servicios/buscar",
     f"Servicio de {BORRADOR}", f"Servicio de {PUBLICADO}"),
    ("la cartelera de eventos", "/eventos/",
     f"Feria de {BORRADOR}", f"Feria de {PUBLICADO}"),
    ("la API del calendario", "/api/eventos/",
     f"Feria de {BORRADOR}", f"Feria de {PUBLICADO}"),
]


def test_un_borrador_no_aparece_en_ninguna_vista_publica(
    client, db, dos_emprendimientos
):
    """El barrido: ninguna de las nueve pantallas sin sesion lo muestra.

    Se recorren todas y se juntan los fallos antes de afirmar, en vez de cortar
    en la primera: si un cambio abre una puerta, lo util es ver cuales quedaron
    abiertas y no solo la primera de la lista.
    """
    filtradas, ausencias = [], []

    for nombre, url, del_borrador, del_publicado in SUPERFICIES_PUBLICAS:
        html = _texto(client.get(url))
        if del_borrador in html:
            filtradas.append(f"{nombre} ({url}) muestra el borrador")
        # El control: si el publicado tampoco esta, el assert de arriba no
        # probaba nada.
        if del_publicado not in html:
            ausencias.append(f"{nombre} ({url}) no muestra ni el publicado")

    assert filtradas == []
    assert ausencias == []


def test_la_ficha_y_el_detalle_de_un_borrador_son_404_para_un_extranio(
    client, dos_emprendimientos
):
    """Sacarlo de los listados no alcanza: las URLs son /<id> incremental.

    Sin este corte, el borrador se lee probando numeros. Y ademas le sumaria una
    vista, que es lo que hace blog.detail antes de renderizar.

    404 y no 403 a proposito: un 403 confirmaria que ese id existe y esta sin
    publicar, que es exactamente lo que el dueño todavia no quiso contar.
    """
    borrador = dos_emprendimientos["borrador"]
    publicado = dos_emprendimientos["publicado"]
    producto_del_borrador = Product.query.filter_by(post_id=borrador.id).first()
    producto_publicado = Product.query.filter_by(post_id=publicado.id).first()

    assert client.get(f"/blog/{borrador.id}").status_code == 404
    assert client.get(f"/api/posts/{borrador.id}").status_code == 404
    assert client.get(f"/productos/{producto_del_borrador.id}").status_code == 404

    # Los mismos tres del publicado siguen abiertos, o sea que el 404 es por el
    # estado y no porque las rutas se rompieron.
    assert client.get(f"/blog/{publicado.id}").status_code == 200
    assert client.get(f"/api/posts/{publicado.id}").status_code == 200
    assert client.get(f"/productos/{producto_publicado.id}").status_code == 200


def test_el_borrador_no_se_cuela_por_el_perfil_publico_ni_por_las_resenias(
    client, dos_emprendimientos
):
    """El perfil del dueño es publico y lista sus emprendimientos y sus reseñas.

    La reseña es el caso que menos se ve venir: trae adentro el nombre del
    emprendimiento reseñado (el joinedload del post es justamente para
    mostrarlo), asi que la pagina de reseñas filtra el borrador aunque la
    consulta sea sobre Review y no sobre Post. Puede haberlas: un emprendimiento
    publicado que recibio reseñas y despues volvio a borrador.
    """
    dueno = dos_emprendimientos["dueno"]

    perfil = _texto(client.get(f"/perfil/{dueno.slug}"))
    assert BORRADOR not in perfil
    assert PUBLICADO in perfil

    resenias = _texto(client.get(f"/perfil/{dueno.slug}/resenias"))
    assert BORRADOR not in resenias
    assert PUBLICADO in resenias


def test_los_marcados_de_un_tercero_tampoco_muestran_el_borrador(
    client, login, dos_emprendimientos
):
    """Favoritos y "Mis guardados" son de OTRO usuario, no del dueño.

    Es el caso que la marca vuelve raro: un emprendimiento que se guardo cuando
    estaba publicado y su dueño volvio a borrador no se puede seguir mirando
    desde los favoritos de un tercero. La marca no se borra --si vuelve a
    publicarse, reaparece--, solo deja de listarse.
    """
    login(dos_emprendimientos["visitante"].id)

    favoritos = _texto(client.get("/blog/favoritos"))
    assert BORRADOR not in favoritos
    assert PUBLICADO in favoritos

    guardados = _texto(client.get("/productos/guardados"))
    assert f"Producto de {BORRADOR}" not in guardados
    assert f"Producto de {PUBLICADO}" in guardados


def test_los_contadores_publicos_no_cuentan_los_borradores(
    client, dos_emprendimientos
):
    """Los numeros tienen que contar lo mismo que la grilla muestra.

    Son tres y los tres salen de consultas distintas: el total del home, el
    numero al lado de cada rubro en el listado, y el de emprendimientos del
    encabezado del catalogo de productos. Un contador que incluya borradores
    promete resultados que la pantalla siguiente no tiene, que es peor que no
    tener el numero.
    """
    from app.blog import consultas as consultas_blog
    from app.servicios import consultas as consultas_servicios

    assert consultas_blog.conteo_por_categoria().get("alimentos") == 1

    # El home dice el tamaño de la plataforma que se puede visitar: "1
    # publicado" y no "2", que es el total de la tabla.
    assert "1 publicado" in _texto(client.get("/"))

    # Y el contador por rubro de servicios, que es el que mas facil se rompia:
    # su consulta es un GROUP BY sobre services que NO joinea posts, asi que un
    # filtro mal escrito ahi da un producto cartesiano en vez de filtrar.
    conteos = consultas_servicios.conteos_por_rubro(
        zona=None, solo_verificados=False, precio=None,
    )
    assert conteos.get(Rubros.PLOMERIA) == 1


def test_el_dueno_si_ve_su_borrador_y_etiquetado(
    client, login, dos_emprendimientos
):
    """La unica pantalla donde un borrador se ve es "Mis emprendimientos".

    Y se ve DISTINTO: con su etiqueta, porque en una lista de varias filas la
    diferencia entre publicado y borrador es justamente lo que hay que poder
    leer de un vistazo.
    """
    dueno = dos_emprendimientos["dueno"]
    borrador = dos_emprendimientos["borrador"]
    login(dueno.id)

    mis = _texto(client.get("/blog/mis-emprendimientos"))
    assert BORRADOR in mis
    assert PUBLICADO in mis
    assert "Borrador" in mis
    # Y el boton para publicarlo sin volver a pasar por el formulario.
    assert f"/blog/{borrador.id}/publicar" in mis

    # Su propia ficha si la puede abrir, que es como lo revisa antes de publicar.
    assert client.get(f"/blog/{borrador.id}").status_code == 200

    # En su perfil lo ve; en "ver como visitante" no, porque esa vista previa es
    # la consulta de verdad y no un dibujo.
    assert BORRADOR in _texto(client.get(f"/perfil/{dueno.slug}"))
    assert BORRADOR not in _texto(
        client.get(f"/perfil/{dueno.slug}?ver=visitante")
    )


def test_guardar_borrador_desde_el_formulario_no_publica_nada(
    client, db, login, crear_usuario
):
    """Los dos botones del formulario son el mismo form con distinto "accion"."""
    from app.blog.modelo_post import Post

    dueno = crear_usuario(username="dueno", rol=Roles.EMPRENDEDOR)
    login(dueno.id)

    client.post("/blog/create", data={
        "title": "Con boton de borrador", "body": "Todavia no",
        "category": "alimentos", "address_street": "", "accion": "borrador",
    }, follow_redirects=True)
    guardado = Post.query.filter_by(title="Con boton de borrador").one()
    assert guardado.estado == EstadosPost.BORRADOR

    # El submit normal sigue publicando, como antes de que existieran los
    # borradores.
    client.post("/blog/create", data={
        "title": "Con el boton de siempre", "body": "Esto va",
        "category": "alimentos", "address_street": "", "accion": "publicar",
    }, follow_redirects=True)
    assert Post.query.filter_by(
        title="Con el boton de siempre"
    ).one().estado == EstadosPost.PUBLICADO

    # Y un POST sin el campo --uno armado a mano, o un formulario viejo-- cae en
    # publicado, que es lo que hacia antes: no se crea un emprendimiento
    # invisible sin que nadie lo haya pedido.
    client.post("/blog/create", data={
        "title": "Sin el campo accion", "body": "Compatible",
        "category": "alimentos", "address_street": "",
    }, follow_redirects=True)
    assert Post.query.filter_by(
        title="Sin el campo accion"
    ).one().estado == EstadosPost.PUBLICADO


def test_publicar_un_borrador_lo_mete_en_las_vistas_publicas(
    client, db, login, dos_emprendimientos
):
    """El viaje completo: de invisible a publicado, por las mismas pantallas.

    Se recorre el mismo barrido que el test de arriba pero al reves: despues de
    publicar, el que antes no estaba en ninguna tiene que estar en todas. Asi el
    filtro queda probado en los dos sentidos y no solo escondiendo cosas.
    """
    borrador = dos_emprendimientos["borrador"]
    login(dos_emprendimientos["dueno"].id)

    respuesta = client.post(
        f"/blog/{borrador.id}/publicar", follow_redirects=True
    )
    assert respuesta.status_code == 200
    db.session.expire_all()
    assert borrador.estado == EstadosPost.PUBLICADO

    # Ya no es un borrador en su propia lista.
    mis = _texto(client.get("/blog/mis-emprendimientos"))
    assert f"/blog/{borrador.id}/publicar" not in mis

    # Y ahora si esta en las nueve superficies publicas, mirando sin sesion.
    client.get("/auth/logout")
    faltantes = []
    for nombre, url, del_borrador, _ in SUPERFICIES_PUBLICAS:
        if del_borrador not in _texto(client.get(url)):
            faltantes.append(f"{nombre} ({url}) no lo muestra despues de publicar")
    assert faltantes == []

    assert client.get(f"/blog/{borrador.id}").status_code == 200


def test_publicar_pide_ser_el_dueno(client, db, login, dos_emprendimientos):
    """Publicar cambia quien puede ver el emprendimiento, asi que es del dueño.

    Un extraño no puede publicar el borrador de otro: seria sacarle a la calle
    algo que todavia no decidio mostrar.

    El corte es el mismo _post_propio que ya usan editar, borrar y reordenar las
    fotos, o sea que la respuesta es el redirect con el mensaje y no un 403: la
    convencion del proyecto para "esto no es tuyo" en una accion del panel. Lo
    que este test fija es el efecto, que es lo que importa -- el estado no se
    movio --, no el codigo HTTP.
    """
    borrador = dos_emprendimientos["borrador"]
    login(dos_emprendimientos["visitante"].id)

    respuesta = client.post(
        f"/blog/{borrador.id}/publicar", follow_redirects=True
    )
    assert "No tenés permiso para publicar" in _texto(respuesta)

    db.session.expire_all()
    assert borrador.estado == EstadosPost.BORRADOR


def test_no_se_puede_proponer_a_una_oportunidad_desde_un_borrador(
    db, dos_emprendimientos
):
    """Una propuesta muestra el nombre del emprendimiento del que sale.

    O sea que proponer desde un borrador seria la puerta de atras para que el
    publicador lo vea. La regla lo rechaza del lado del servidor y el <select>
    del formulario no lo ofrece; las dos cosas, porque el post_id llega del POST
    y se puede escribir a mano.
    """
    from app.oportunidades import consultas as consultas_op
    from app.oportunidades import reglas as reglas_op
    from app.oportunidades.modelo_oportunidad import Oportunidad

    dueno = dos_emprendimientos["dueno"]
    otro = dos_emprendimientos["visitante"]
    oportunidad = Oportunidad(
        autor_id=otro.id, titulo="Necesito pan", descripcion="Para un evento",
    )
    db.session.add(oportunidad)
    db.session.commit()

    assert not reglas_op.puede_proponer(
        oportunidad, dos_emprendimientos["borrador"], dueno.id
    )
    assert reglas_op.puede_proponer(
        oportunidad, dos_emprendimientos["publicado"], dueno.id
    )

    ofrecidos = [post.title for post in consultas_op.posts_de(dueno.id)]
    assert BORRADOR not in ofrecidos
    assert PUBLICADO in ofrecidos


def test_excluir_borradores_no_agrega_una_consulta_por_fila(
    app, client, db, crear_usuario, crear_post
):
    """El filtro no puede costar una consulta por emprendimiento.

    Un WHERE sobre una columna indexada no deberia costar nada, pero dos de las
    formas que usa esta tanda SI podrian: el EXISTS correlacionado de
    de_post_publicado() se evalua por fila candidata, y un filtro sobre Post
    agregado a una consulta que no lo tiene en el FROM se lo agrega solo. Lo que
    se congela es que el numero de consultas NO DEPENDA de cuantas filas hay,
    que es la propiedad que distingue un WHERE de un N+1.

    Se compara con 2 emprendimientos contra 12, cada uno con su producto, su
    servicio y su evento, o sea que las cuatro superficies crecen a la vez. Con
    el identity map vaciado antes de cada medicion: con los objetos ya cargados
    un lazy load no llega a la base y el contador daria un falso negativo.
    """
    from sqlalchemy import event as evento_sql

    dueno = crear_usuario(username="dueno", rol=Roles.EMPRENDEDOR)
    dueno_id = dueno.id

    def sumar_emprendimientos(desde, hasta):
        for numero in range(desde, hasta):
            post = crear_post(
                dueno_id, title=f"Negocio {numero:02d}", body="Descripcion",
                category="alimentos",
            )
            db.session.add(Product(
                post_id=post.id, nombre=f"Producto {numero:02d}", precio=1000,
            ))
            db.session.add(Service(
                post_id=post.id, titulo=f"Servicio {numero:02d}",
                rubro=Rubros.PLOMERIA, descripcion="Arreglos",
                zona_cobertura="Toda la ciudad",
            ))
            db.session.add(Event(
                post_id=post.id, titulo=f"Feria {numero:02d}",
                fecha=hoy_en_argentina() + timedelta(days=3),
            ))
            db.session.commit()

    def contar_consultas(url):
        db.session.expunge_all()
        vistas = []

        def escuchar(conn, cursor, statement, params, context, many):
            vistas.append(statement)

        evento_sql.listen(db.engine, "before_cursor_execute", escuchar)
        try:
            respuesta = client.get(url)
        finally:
            evento_sql.remove(db.engine, "before_cursor_execute", escuchar)
        assert respuesta.status_code == 200, url
        return len(vistas)

    # La pagina entera, para que las 12 filas caigan en una sola y el numero sea
    # comparable con el de 2.
    app.config["POSTS_POR_PAGINA"] = 50
    app.config["PRODUCTOS_POR_PAGINA"] = 50

    urls = [url for _, url, _, _ in SUPERFICIES_PUBLICAS] + ["/"]

    sumar_emprendimientos(0, 2)
    con_dos = {url: contar_consultas(url) for url in urls}

    sumar_emprendimientos(2, 12)
    con_doce = {url: contar_consultas(url) for url in urls}

    crecieron = {
        url: (con_dos[url], con_doce[url])
        for url in urls
        if con_doce[url] != con_dos[url]
    }
    assert crecieron == {}


def test_guardar_la_edicion_no_despublica_ni_publica_sin_que_se_lo_pidan(
    client, db, crear_usuario, crear_post, login
):
    """El estado solo lo mueve el boton que lo nombra, y solo hacia donde ofrece.

    Los dos casos que faltaban, y los dos entran por el mismo lado: el estado
    salia del formulario sin rechequear contra la fila.

      - `accion=borrador` sobre un emprendimiento YA PUBLICADO lo despublicaba.
        Ese boton ni se dibuja en ese caso --despublicar es otra decision-- pero
        el POST se puede armar a mano, y sobre todo se puede apretar en una
        pestaña que quedo abierta de cuando todavia era borrador;
      - un POST de edicion SIN `accion` publicaba un borrador. En el alta ese
        default esta bien (es lo que el formulario hacia siempre); al editar
        pisa una decision que el dueño ya habia tomado.
    """
    dueno = crear_usuario(username="dueno", rol=Roles.EMPRENDEDOR)
    login(dueno.id)

    campos = {"title": "Mi negocio", "body": "Descripcion", "category": "alimentos",
              "address_street": ""}

    def estado_despues_de(estado_inicial, extra):
        post = crear_post(
            dueno.id, title="Mi negocio", body="Descripcion",
            category="alimentos", estado=estado_inicial,
        )
        client.post(f"/blog/update/{post.id}", data={**campos, **extra})
        db.session.refresh(post)
        return post.estado

    B, P = EstadosPost.BORRADOR, EstadosPost.PUBLICADO
    resultados = {
        "publicado + accion=borrador a mano": estado_despues_de(P, {"accion": "borrador"}),
        "publicado + sin accion": estado_despues_de(P, {}),
        "publicado + guardar cambios": estado_despues_de(P, {"accion": "publicar"}),
        "borrador + sin accion": estado_despues_de(B, {}),
        "borrador + accion desconocida": estado_despues_de(B, {"accion": "vaya-a-saber"}),
        "borrador + guardar borrador": estado_despues_de(B, {"accion": "borrador"}),
        "borrador + publicar emprendimiento": estado_despues_de(B, {"accion": "publicar"}),
    }

    assert resultados == {
        # Un publicado no se cae del listado por guardar, por ningun camino.
        "publicado + accion=borrador a mano": P,
        "publicado + sin accion": P,
        "publicado + guardar cambios": P,
        # Un borrador solo se publica si se apreta el boton que lo dice.
        "borrador + sin accion": B,
        "borrador + accion desconocida": B,
        "borrador + guardar borrador": B,
        "borrador + publicar emprendimiento": P,
    }


def test_el_alta_sigue_publicando_por_defecto(client, db, crear_usuario, login):
    """Lo de arriba cambia la EDICION, no el alta.

    En el alta no hay nada previo que respetar, asi que un POST sin `accion`
    --el formulario de siempre, antes de que existieran los borradores-- tiene
    que seguir creando un emprendimiento publicado. Si esto se rompe, el alta
    empieza a crear emprendimientos invisibles sin que nadie lo haya pedido.
    """
    from app.blog.modelo_post import Post

    dueno = crear_usuario(username="dueno", rol=Roles.EMPRENDEDOR)
    login(dueno.id)

    client.post("/blog/create", data={
        "title": "Recien creado", "body": "Descripcion",
        "category": "alimentos", "address_street": "",
    })

    creado = Post.query.filter_by(title="Recien creado").first()
    assert creado is not None
    assert creado.estado == EstadosPost.PUBLICADO
