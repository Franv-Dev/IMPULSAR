"""Eventos y ferias de los emprendimientos."""

from datetime import date, time, timedelta

import pytest

from models.event import Event
from services.eventos import hoy_en_argentina, parsear_fecha, pasados, proximos


@pytest.fixture
def crear_evento(db):
    """Fabrica de eventos. `dias` es a cuantos dias de hoy cae el evento."""

    def _crear(post_id, titulo="Feria de la plaza", dias=7, hora=None, descripcion=None):
        evento = Event(
            post_id=post_id,
            titulo=titulo,
            descripcion=descripcion,
            fecha=hoy_en_argentina() + timedelta(days=dias),
            hora=hora,
        )
        db.session.add(evento)
        db.session.commit()
        return evento

    return _crear


@pytest.fixture
def emprendedor_con_post(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio."""

    def _crear(username="tomy"):
        usuario = crear_usuario(username=username)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


# --- fechas

def test_parsear_fecha_acepta_el_formato_del_input_date():
    assert parsear_fecha("2026-09-13") == date(2026, 9, 13)


@pytest.mark.parametrize("texto", ["", None, "13/09/2026", "no es una fecha", "2026-13-40"])
def test_parsear_fecha_devuelve_none_si_no_se_entiende(texto):
    assert parsear_fecha(texto) is None


# --- alta

def test_publicar_un_evento_lo_guarda(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id,
        "titulo": "Feria de emprendedores",
        "descripcion": "En la plaza principal",
        "fecha": "2026-09-13",
        "hora": "10:30",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    evento = Event.query.one()
    assert evento.titulo == "Feria de emprendedores"
    assert evento.fecha == date(2026, 9, 13)
    assert evento.hora == time(10, 30)
    assert evento.post_id == post.id


def test_la_hora_es_opcional(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13", "hora": "",
    })

    assert Event.query.one().hora is None


@pytest.mark.parametrize("campos, faltante", [
    ({"titulo": "", "fecha": "2026-09-13"}, "titulo"),
    ({"titulo": "Feria", "fecha": ""}, "fecha vacia"),
    ({"titulo": "Feria", "fecha": "13/09/2026"}, "fecha con formato invalido"),
])
def test_un_evento_incompleto_no_se_guarda(client, emprendedor_con_post, campos, faltante):
    _usuario, post = emprendedor_con_post()

    respuesta = client.post(
        "/eventos/nuevo", data={"post_id": post.id, **campos}, follow_redirects=True
    )

    assert respuesta.status_code == 200
    assert Event.query.count() == 0, f"se guardo un evento con {faltante}"


def test_no_se_puede_colgar_un_evento_del_emprendimiento_de_otro(
    client, crear_usuario, crear_post, login
):
    """El post_id viaja en el formulario: sin validarlo, cualquiera podria
    publicar un evento en el emprendimiento ajeno mandando otro id."""
    ajeno = crear_usuario(username="ajeno")
    post_ajeno = crear_post(ajeno.id, title="Panadería ajena")
    intruso = crear_usuario(username="intruso")
    crear_post(intruso.id, title="Lo mío")
    login(intruso.id)

    client.post("/eventos/nuevo", data={
        "post_id": post_ajeno.id, "titulo": "Feria colada", "fecha": "2026-09-13",
    }, follow_redirects=True)

    assert Event.query.count() == 0


def test_sin_emprendimientos_no_se_puede_publicar(client, crear_usuario, login):
    usuario = crear_usuario()
    login(usuario.id)

    respuesta = client.get("/eventos/nuevo")

    assert respuesta.status_code == 302
    assert "/blog/mis-emprendimientos" in respuesta.headers["Location"]


def test_publicar_requiere_estar_logueado(client):
    respuesta = client.get("/eventos/nuevo")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


# --- edicion y borrado

def test_el_dueño_edita_su_evento(client, emprendedor_con_post, crear_evento):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id, titulo="Nombre viejo")

    client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": "Nombre nuevo", "fecha": "2026-10-01",
    }, follow_redirects=True)

    assert Event.query.get(evento.id).titulo == "Nombre nuevo"


def test_el_dueño_elimina_su_evento(client, emprendedor_con_post, crear_evento):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id)

    client.post(f"/eventos/{evento.id}/eliminar", follow_redirects=True)

    assert Event.query.count() == 0


def test_un_extraño_no_puede_editar_un_evento_ajeno(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id, titulo="Original")
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": "Secuestrado", "fecha": "2026-10-01",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    assert Event.query.get(evento.id).titulo == "Original"


def test_un_extraño_no_puede_eliminar_un_evento_ajeno(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id)
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    client.post(f"/eventos/{evento.id}/eliminar", follow_redirects=True)

    assert Event.query.count() == 1


def test_eliminar_no_acepta_get(client, emprendedor_con_post, crear_evento):
    """Un GET no debe tener efectos secundarios: lo puede disparar un prefetch."""
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id)

    respuesta = client.get(f"/eventos/{evento.id}/eliminar")

    assert respuesta.status_code == 405
    assert Event.query.count() == 1


# --- cascade

def test_borrar_un_emprendimiento_se_lleva_sus_eventos(
    client, emprendedor_con_post, crear_evento
):
    """En MySQL el default de la FK es RESTRICT: sin el ondelete="CASCADE" esto
    falla con IntegrityError. Los tests usan SQLite, que valida las FK gracias
    al PRAGMA de db.py, asi que el caso queda cubierto de verdad."""
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id)
    crear_evento(post.id, titulo="Otra feria", dias=14)

    respuesta = client.post(f"/blog/delete/{post.id}", follow_redirects=True)

    assert respuesta.status_code == 200
    assert Event.query.count() == 0


# --- seccion del perfil

def test_el_perfil_muestra_los_proximos_eventos(
    client, crear_usuario, crear_post, crear_evento
):
    usuario = crear_usuario(username="Panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="Feria de septiembre", dias=10)

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "Próximos eventos" in html
    assert "Feria de septiembre" in html


def test_un_evento_pasado_no_se_mezcla_con_los_proximos(
    client, crear_usuario, crear_post, crear_evento
):
    """Lo que ya paso va en el desplegable de abajo, no arriba con los que
    todavia se pueden ir a ver."""
    usuario = crear_usuario(username="Panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="Feria vieja", dias=-10)

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    # Aparece, pero adentro del bloque de pasados.
    assert "Eventos que ya pasaron" in html
    seccion_pasados = html.split("Eventos que ya pasaron", 1)[1]
    assert "Feria vieja" in seccion_pasados
    assert "Feria vieja" not in html.split("Eventos que ya pasaron", 1)[0]


def test_un_evento_de_hoy_sigue_contando_como_proximo(
    client, crear_usuario, crear_post, crear_evento
):
    """El corte es por dia y no por hora: a las 11 todavia se puede ir a una
    feria que abrio a las 10."""
    usuario = crear_usuario(username="Panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="Feria de hoy", dias=0, hora=time(1, 0))

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "Feria de hoy" in html.split("Eventos que ya pasaron")[0]


def test_los_eventos_del_perfil_los_ve_cualquier_visitante(
    client, crear_usuario, crear_post, crear_evento
):
    """A diferencia de las estadisticas, un evento es un anuncio, no un dato
    privado del dueño."""
    usuario = crear_usuario(username="Panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="Feria abierta")

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "Feria abierta" in html
    assert "Tus estadísticas" not in html


def test_los_controles_de_edicion_son_solo_del_dueño(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id)

    anonimo = client.get(f"/perfil/{dueño.slug}").get_data(as_text=True)
    assert f"/eventos/{evento.id}/eliminar" not in anonimo
    assert "/eventos/nuevo" not in anonimo

    login(dueño.id)
    propio = client.get(f"/perfil/{dueño.slug}").get_data(as_text=True)
    assert f"/eventos/{evento.id}/eliminar" in propio
    assert "/eventos/nuevo" in propio


def test_un_extraño_no_ve_los_controles_de_edicion(
    client, crear_usuario, crear_post, crear_evento, login
):
    dueño = crear_usuario(username="dueño")
    post = crear_post(dueño.id)
    evento = crear_evento(post.id)
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    html = client.get(f"/perfil/{dueño.slug}").get_data(as_text=True)

    assert f"/eventos/{evento.id}/editar" not in html


def test_el_perfil_muestra_los_avisos(client, emprendedor_con_post):
    """profile.html no renderizaba los flashes, asi que el aviso de "Evento
    publicado" se perdia al redirigir al perfil."""
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13",
    }, follow_redirects=True)

    assert "Evento publicado correctamente." in respuesta.get_data(as_text=True)


# --- cartelera general

def test_la_cartelera_responde_sin_login(client):
    assert client.get("/eventos/").status_code == 200


def test_la_cartelera_junta_eventos_de_varios_emprendedores(
    client, crear_usuario, crear_post, crear_evento
):
    una = crear_usuario(username="panaderia")
    otra = crear_usuario(username="ceramica")
    crear_evento(crear_post(una.id).id, titulo="Feria de pan")
    crear_evento(crear_post(otra.id, title="Taller").id, titulo="Feria de ceramica")

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Feria de pan" in html
    assert "Feria de ceramica" in html


def test_la_cartelera_no_muestra_lo_que_ya_paso(
    client, crear_usuario, crear_post, crear_evento
):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="Feria vieja", dias=-3)
    crear_evento(post.id, titulo="Feria que viene", dias=3)

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Feria que viene" in html
    assert "Feria vieja" not in html


def test_la_cartelera_ordena_del_mas_cercano_al_mas_lejano(
    client, crear_usuario, crear_post, crear_evento
):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="La lejana", dias=30)
    crear_evento(post.id, titulo="La cercana", dias=2)

    html = client.get("/eventos/").get_data(as_text=True)

    assert html.index("La cercana") < html.index("La lejana")


def test_cada_evento_linkea_al_perfil_de_quien_lo_publico(
    client, crear_usuario, crear_post, crear_evento
):
    usuario = crear_usuario(username="Panadería del barrio")
    crear_evento(crear_post(usuario.id).id)

    html = client.get("/eventos/").get_data(as_text=True)

    assert f'/perfil/{usuario.slug}"' in html


def test_la_cartelera_esta_paginada(client, app, crear_usuario, crear_post, crear_evento):
    """Sin paginar, la cartelera se trae todo con .all() y crece sin limite."""
    por_pagina = app.config["POSTS_POR_PAGINA"]
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    for numero in range(por_pagina + 2):
        crear_evento(post.id, titulo=f"Feria numero {numero}", dias=numero + 1)

    primera = client.get("/eventos/").get_data(as_text=True)
    segunda = client.get("/eventos/?page=2").get_data(as_text=True)

    # La pagina 1 llega hasta el indice por_pagina - 1; el siguiente ya cae en
    # la 2, que es justamente lo que no pasaria si la vista trajera todo junto.
    assert f"Feria numero {por_pagina - 1}" in primera
    assert f"Feria numero {por_pagina}" not in primera
    assert f"Feria numero {por_pagina}" in segunda
    assert "Página 1 de 2" in primera


def test_la_paginacion_no_repite_ni_saltea_eventos_del_mismo_dia(
    client, app, crear_usuario, crear_post, crear_evento
):
    """Todos el mismo dia y sin hora: comparten la clave de orden entera.

    Sin un desempate estable el orden entre ellos lo decide la base, que no
    garantiza ninguno, y con LIMIT/OFFSET eso alcanza para que un evento salga
    en las dos paginas o en ninguna.
    """
    por_pagina = app.config["POSTS_POR_PAGINA"]
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    # Titulos de ancho fijo para que ninguno sea subcadena de otro ("Feria 1"
    # matchearia dentro de "Feria 10" y el conteo daria cualquier cosa).
    titulos = [f"Feria {numero:02d} de prueba" for numero in range(por_pagina + 3)]
    for titulo in titulos:
        crear_evento(post.id, titulo=titulo, dias=5, hora=None)

    paginas = [
        client.get("/eventos/").get_data(as_text=True),
        client.get("/eventos/?page=2").get_data(as_text=True),
    ]

    for titulo in titulos:
        apariciones = sum(pagina.count(titulo) for pagina in paginas)
        assert apariciones == 1, f"{titulo} aparece {apariciones} veces entre las dos páginas"


def test_los_eventos_del_mismo_dia_sin_hora_salen_siempre_en_el_mismo_orden(
    db, crear_usuario, crear_post, crear_evento
):
    """El orden tiene que ser total, no "el que devuelva la base esta vez"."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    for numero in range(5):
        crear_evento(post.id, titulo=f"Feria {numero}", dias=5, hora=None)

    primera_vez = [evento.id for evento in proximos(Event.query).all()]
    segunda_vez = [evento.id for evento in proximos(Event.query).all()]

    assert primera_vez == segunda_vez
    assert primera_vez == sorted(primera_vez)


@pytest.mark.parametrize("consulta, sentido", [(proximos, "ASC"), (pasados, "DESC")])
def test_el_orden_incluye_el_id_como_desempate(app, consulta, sentido):
    """Se mira el ORDER BY y no solo el resultado a proposito.

    Con SQLite las filas suelen volver en orden de insercion aunque la consulta
    no lo pida, asi que un test que solo compare listas puede pasar en verde con
    el bug puesto y romperse recien en MySQL, en produccion y paginando.
    """
    # Solo el ORDER BY: "events.id" tambien aparece en el SELECT y en el JOIN,
    # asi que buscarlo en la consulta entera no probaria nada.
    orden = str(consulta(Event.query).statement.compile()).split("ORDER BY")[1]

    assert f"events.fecha {sentido}" in orden
    assert f"events.hora {sentido}" in orden
    assert f"events.id {sentido}" in orden
    # Y ultimo: si desempatara antes, mandaria el id por sobre la fecha.
    assert orden.index("events.id") > orden.index("events.hora")


def test_los_pasados_del_mismo_dia_tambien_desempatan(
    db, crear_usuario, crear_post, crear_evento
):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    for numero in range(5):
        crear_evento(post.id, titulo=f"Feria vieja {numero}", dias=-5, hora=None)

    ids = [evento.id for evento in pasados(Event.query).all()]

    # Al reves que los proximos: los pasados van del mas reciente al mas viejo.
    assert ids == sorted(ids, reverse=True)


def test_eventos_esta_en_los_slugs_reservados():
    """/eventos es una ruta de primer nivel: un usuario con ese slug no la tapa
    hoy (el perfil vive bajo /perfil/), pero se reserva igual, con el mismo
    criterio que "blog", "mensajes" y "favoritos"."""
    from services.slugs import SLUGS_RESERVADOS

    assert "eventos" in SLUGS_RESERVADOS
