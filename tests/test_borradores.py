"""Un emprendimiento en borrador no existe para nadie mas que su dueño.

LO QUE HAY QUE ENTENDER ANTES DE TOCAR ESTE ARCHIVO. El estado no se guarda para
mostrar una etiqueta: se guarda para que la fila no aparezca. Y "no aparecer" no
es una pantalla ni una docena: es CUALQUIER ruta que pueda nombrar un
emprendimiento o algo que cuelgue de el, hoy y las que se escriban mañana.

Por eso el test central es un BARRIDO DINAMICO sobre el url_map entero y no una
lista de pantallas. La diferencia no es de estilo. Con lista fija se prueba lo
que alguien se acordo de anotar, asi que la ruta nueva siempre nace afuera de la
garantia: la lista tenia nueve pantallas y habia cuatro rutas mas que mostraban
el borrador a cualquiera con sesion --pedir presupuesto, sacar turno, reportar y
la conversacion-- y dos de ellas ademas DEJABAN actuar sobre el. Recorriendo el
url_map, una ruta entra en la garantia el dia que se escribe, sin que nadie
tenga que acordarse de nada.

DOS FORMAS DE QUE UN BARRIDO PASE SIN PROBAR NADA, y las dos pasaron de verdad
mientras se escribia esto:

  - QUE PIERDA LA SESION A MITAD DE CAMINO. /auth/logout es un GET y ordena
    antes que /servicios/... : recorriendo el url_map se deslogueaba solo, y
    todo lo que venia despues se pedia como anonimo. Ver RUTAS_FUERA_DEL_BARRIDO
    y el comentario del bucle;
  - QUE LOS DATOS DE PRUEBA NO HABILITEN LA PANTALLA. El servicio de la fixture
    no tenia turnos habilitados, asi que turnos.reservar cortaba antes de
    dibujar nada y su "no filtra" era un falso negativo. Ver la fixture.

Y EL BARRIDO VA CONTRA UN CONTROL PUBLICADO (SUPERFICIES_PUBLICAS). Sin eso
pasaria igual con las paginas rotas, vacias, o con un filtro que se lleva todo
puesto: "no aparece el borrador" es trivialmente cierto en una pagina que no
muestra nada. El control es lo que distingue "filtra bien" de "no muestra nada",
y es lo unico que el barrido dinamico no puede contestar solo.
"""

from datetime import timedelta

import pytest

from app.blog.modelo_favorito import Favorite
from app.blog.modelo_post import EstadosPost
from app.blog.modelo_resenia import Review
from app.servicios.modelo import Rubros, Service
from models.event import Event
from models.message import Message
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
        # CON TURNOS HABILITADOS, y no es decoracion: turnos.reservar corta
        # antes de dibujar nada si el servicio no los acepta, asi que con el
        # default el barrido no llegaba nunca a esa pantalla y su "no filtra"
        # era un falso negativo. Lo mismo vale para cualquier pantalla nueva
        # que este detras de un flag: si el dato de prueba no la habilita, el
        # barrido la recorre sin probarla.
        db.session.add(Service(
            post_id=post.id, titulo=f"Servicio de {titulo}",
            rubro=Rubros.PLOMERIA, descripcion="Arreglos",
            zona_cobertura="Toda la ciudad",
            turnos_habilitados=True, duracion_turno_minutos=30,
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
        # Y YA CONVERSO CON LOS DOS. Es el caso real de un borrador: uno que
        # estuvo publicado, hablo con clientes y despues su dueño lo saco de
        # circulacion. Sin estos mensajes el barrido no llega a la bandeja ni a
        # la conversacion --no hay nada que listar-- y las dos pantallas pasan
        # sin probarse; la bandeja seguia nombrando el emprendimiento.
        db.session.add(Message(
            post_id=post.id, client_id=visitante.id, sender_id=visitante.id,
            body=f"Hola, consulta sobre {post.title}",
        ))
    db.session.commit()

    return {
        "dueno": dueno, "visitante": visitante,
        "borrador": borrador, "publicado": publicado,
    }


def _texto(respuesta):
    return respuesta.get_data(as_text=True)


#: EL CONTROL POSITIVO, y solo eso. Esta lista era antes tambien la que definia
#: "las superficies publicas" para el barrido negativo, y ahi estaba el
#: problema: una lista fija solo cubre las pantallas que alguien se acordo de
#: anotar, asi que una ruta nueva nace descubierta -- y asi nacieron cuatro
#: (pedir presupuesto, sacar turno, reportar y la conversacion). El barrido
#: negativo pasa a recorrer el url_map entero, ver
#: test_un_borrador_no_aparece_en_ninguna_ruta_get.
#:
#: Esta lista queda para lo unico que un barrido dinamico NO puede contestar:
#: que el publicado SI se vea. Sin eso, "no aparece el borrador" es
#: trivialmente cierto en una pagina rota, vacia o con un filtro que se lleva
#: todo puesto.
#:
#: Cada una es (para que sirve, la URL, que se busca del borrador, que se busca
#: del publicado). Las dos ultimas columnas son distintas por pantalla porque el
#: catalogo muestra el nombre del PRODUCTO y la cartelera el del EVENTO, no el
#: del emprendimiento.
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


def test_las_superficies_publicas_si_muestran_el_publicado(
    client, db, dos_emprendimientos
):
    """El control positivo del barrido de abajo.

    Sin esto, "el borrador no aparece" pasaria igual con las paginas rotas,
    vacias, o con un filtro que se lleva todo puesto. Es la mitad que el barrido
    dinamico no puede afirmar: el sabe recorrer todas las rutas, pero no cuales
    tendrian que estar mostrando algo.
    """
    ausencias = []

    for nombre, url, _, del_publicado in SUPERFICIES_PUBLICAS:
        html = _texto(client.get(url))
        if del_publicado not in html:
            ausencias.append(f"{nombre} ({url}) no muestra ni el publicado")

    assert ausencias == []


#: Rutas que el barrido no pide, cada una con su motivo. Es una lista corta y
#: con nombre y apellido a proposito: agregar algo aca es sacarlo de la
#: garantia, asi que tiene que costar y quedar escrito por que.
RUTAS_FUERA_DEL_BARRIDO = {
    # DESLOGUEA AL BARRIDO. Es un GET, y recorriendo el url_map ordenado cae
    # antes que /servicios/... y que /turnos/...: sin saltearla, todo lo que
    # viene despues se pide como anonimo y el barrido pasa en verde sin haber
    # probado ninguna pantalla con sesion. Paso de verdad mientras se escribia
    # esto, y es exactamente la clase de falso negativo que un barrido tiene que
    # tener prohibido.
    "auth.logout",
    # El panel de moderacion VE los borradores a proposito: es su trabajo. No
    # es una superficie publica y no le aplica la regla.
    "admin.dashboard", "admin.emprendimientos", "admin.reportes",
    "admin.usuarios", "admin.verificaciones",
}


def _urls_del_url_map(app, ids):
    """Todas las rutas GET del url_map, resueltas con los ids del borrador.

    Devuelve (url, endpoint). Para las rutas con parametros se prueban todos los
    ids del borrador que encajen en ese nombre: /<int:id> puede ser un post, un
    producto, un servicio o un evento segun el blueprint, y el barrido no tiene
    por que saber cual -- pide los cuatro y que conteste 404 el que no sea.
    """
    import itertools

    candidatos = {
        "id": [ids["post"], ids["producto"], ids["servicio"], ids["evento"]],
        "post_id": [ids["post"]],
        "target_id": [ids["post"], ids["resenia"]],
        "user_id": [ids["dueno"]],
        "client_id": [ids["visitante"]],
        "slug": [ids["slug"]],
        "tipo": ["post", "resenia"],
    }

    salida = []
    for regla in app.url_map.iter_rules():
        if "GET" not in (regla.methods or ()):
            continue
        if regla.endpoint == "static" or regla.endpoint in RUTAS_FUERA_DEL_BARRIDO:
            continue
        argumentos = sorted(regla.arguments)
        if not argumentos:
            salida.append((str(regla.rule), regla.endpoint))
            continue
        listas = [candidatos.get(nombre, [1]) for nombre in argumentos]
        for combinacion in itertools.product(*listas):
            url = str(regla.rule)
            for nombre, valor in zip(argumentos, combinacion):
                for molde in (f"<int:{nombre}>", f"<string:{nombre}>", f"<{nombre}>"):
                    url = url.replace(molde, str(valor))
            salida.append((url, regla.endpoint))
    return sorted(set(salida))


#: Quien mira, en cada corrida del barrido. No alcanza con uno solo:
#:
#:   - un EMPRENDEDOR no puede pedir presupuesto, asi que usandolo de unico
#:     "extraño" las pantallas que si le abren a un cliente quedan sin probar;
#:   - EL VISITANTE es el que marco el emprendimiento y dejo la reseña, o sea
#:     el tercero que ya tuvo trato con el. Es el unico que pasa el permiso de
#:     /mensajes/<post>/<client_id>, asi que sin el esa pantalla contesta 403
#:     antes de mostrar nada y el barrido no la prueba. Es tambien el caso mas
#:     realista: el que ya conocia el emprendimiento cuando estaba publicado.
CURIOSOS = ["anonimo", "cliente_nuevo", "emprendedor_nuevo", "el_visitante"]


@pytest.mark.parametrize("quien_mira", CURIOSOS)
def test_un_borrador_no_aparece_en_ninguna_ruta_get(
    app, client, db, crear_usuario, dos_emprendimientos, quien_mira
):
    """EL BARRIDO: ninguna ruta GET del url_map nombra el borrador.

    POR QUE ES DINAMICO Y NO UNA LISTA. Una lista fija prueba las pantallas que
    alguien se acordo de anotar, y la propiedad que se quiere garantizar es otra
    ("no hay ninguna puerta"), asi que la ruta nueva siempre nace afuera. Paso:
    la lista cubria nueve pantallas y habia cuatro rutas mas que mostraban el
    borrador a cualquiera con sesion -- pedir presupuesto y sacar turno ademas
    DEJABAN actuar sobre el. Recorriendo el url_map, una ruta nueva entra en la
    garantia el dia que se escribe, sin que nadie tenga que acordarse.

    QUIEN MIRA IMPORTA, y por eso son cuatro corridas: cada uno pasa permisos
    distintos y por lo tanto llega a pantallas distintas (ver CURIOSOS). El
    borrador no tiene que existir para ninguno.

    ALCANZA CON BUSCAR EL NOMBRE DEL EMPRENDIMIENTO: todo lo que cuelga de el se
    llama "<algo> de {BORRADOR}" (ver la fixture), asi que un solo marcador
    cubre el producto, el servicio, el evento y la reseña.
    """
    datos = dos_emprendimientos
    borrador = datos["borrador"]

    if quien_mira == "anonimo":
        curioso_id = None
    elif quien_mira == "el_visitante":
        curioso_id = datos["visitante"].id
    else:
        rol = Roles.USUARIO if quien_mira == "cliente_nuevo" else Roles.EMPRENDEDOR
        curioso_id = crear_usuario(username="curioso", rol=rol).id

    ids = {
        "post": borrador.id,
        "producto": Product.query.filter_by(post_id=borrador.id).first().id,
        "servicio": Service.query.filter_by(post_id=borrador.id).first().id,
        "evento": Event.query.filter_by(post_id=borrador.id).first().id,
        "resenia": Review.query.filter_by(post_id=borrador.id).first().id,
        "dueno": datos["dueno"].id,
        "visitante": datos["visitante"].id,
        "slug": datos["dueno"].slug,
    }

    filtradas = []
    for url, endpoint in _urls_del_url_map(app, ids):
        # La sesion se reafirma ANTES DE CADA REQUEST y no una vez al empezar:
        # cualquier ruta que la toque dejaria anonimo a todo lo que sigue, y el
        # barrido pasaria sin haber probado nada. Ver RUTAS_FUERA_DEL_BARRIDO.
        if curioso_id is not None:
            with client.session_transaction() as sesion:
                sesion["user_id"] = curioso_id
        respuesta = client.get(url, follow_redirects=True)
        if BORRADOR in _texto(respuesta):
            filtradas.append(f"{endpoint} ({url}) muestra el borrador")

    assert filtradas == []


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


def test_no_se_puede_pedir_presupuesto_ni_sacar_turno_a_un_borrador(
    client, db, crear_usuario, login, dos_emprendimientos
):
    """Las dos pantallas que ademas DEJABAN ACTUAR sobre el borrador.

    El barrido de arriba mira que el borrador no se NOMBRE; esto mira la otra
    mitad, que es la que dolia: sobre el servicio de un emprendimiento sin
    publicar se podia mandar una solicitud de presupuesto y reservar un turno.
    Al dueño le llegaba un pedido --y un turno agendado-- de algo que todavia
    no habia decidido mostrarle a nadie.

    Se afirma sobre la BASE y no sobre el codigo de respuesta: un 404 con una
    fila escrita seria igual de malo, y es justo lo que un `abort` puesto
    despues del INSERT dejaria pasar.
    """
    from app.servicios.modelo_solicitud import ServiceRequest
    from app.turnos.modelo_turno import Turno

    borrador = dos_emprendimientos["borrador"]
    servicio = Service.query.filter_by(post_id=borrador.id).first()
    cliente = crear_usuario(username="cliente_curioso", rol=Roles.USUARIO)
    login(cliente.id)

    respuestas = {
        "GET solicitar": client.get(f"/servicios/{servicio.id}/solicitar"),
        "POST solicitar": client.post(
            f"/servicios/{servicio.id}/solicitar",
            data={"descripcion": "quiero esto", "zona": "centro"},
        ),
        "GET turnos": client.get(f"/turnos/servicio/{servicio.id}"),
        "POST turno": client.post(
            f"/turnos/servicio/{servicio.id}",
            data={
                "fecha": (hoy_en_argentina() + timedelta(days=2)).isoformat(),
                "hora_inicio": "09:00",
            },
        ),
    }

    assert {nombre: r.status_code for nombre, r in respuestas.items()} == {
        "GET solicitar": 404, "POST solicitar": 404,
        "GET turnos": 404, "POST turno": 404,
    }
    assert ServiceRequest.query.count() == 0
    assert Turno.query.count() == 0


def test_sobre_el_emprendimiento_publicado_las_dos_pantallas_siguen_andando(
    client, db, crear_usuario, login, dos_emprendimientos
):
    """El control de la guarda de arriba.

    Una guarda puesta de mas --o puesta sobre el post equivocado-- rompe el
    camino normal y ningun assert de "no se pudo" lo notaria: los dos tests
    pasarian, uno porque bloquea el borrador y el otro porque bloquea todo.
    """
    from app.servicios.modelo_solicitud import ServiceRequest

    publicado = dos_emprendimientos["publicado"]
    servicio = Service.query.filter_by(post_id=publicado.id).first()
    cliente = crear_usuario(username="cliente_real", rol=Roles.USUARIO)
    login(cliente.id)

    assert client.get(f"/servicios/{servicio.id}/solicitar").status_code == 200
    assert client.get(f"/turnos/servicio/{servicio.id}").status_code == 200

    client.post(
        f"/servicios/{servicio.id}/solicitar",
        data={"descripcion": "necesito un arreglo", "zona": "centro"},
    )
    assert ServiceRequest.query.count() == 1


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
