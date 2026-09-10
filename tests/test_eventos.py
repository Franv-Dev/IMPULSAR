"""Eventos y ferias de los emprendimientos."""

from datetime import date, time, timedelta

import pytest

from models.event import Event, TiposEvento
from services.eventos import (
    agrupar_por_mes, en_rango, hoy_en_argentina, mes_y_anio, parsear_fecha,
    parsear_mes, pasados, proximos, rango_del_mes, tipo_valido,
)
from views import eventos_api


@pytest.fixture
def crear_evento(db):
    """Fabrica de eventos. `dias` es a cuantos dias de hoy cae el evento."""

    def _crear(post_id, titulo="Feria de la plaza", dias=7, hora=None,
               descripcion=None, lugar=None):
        evento = Event(
            post_id=post_id,
            titulo=titulo,
            descripcion=descripcion,
            lugar=lugar,
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
        "tipo": "feria",
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
        "tipo": "feria",
    })

    assert Event.query.one().hora is None


def test_publicar_un_evento_guarda_el_lugar(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13",
        "lugar": "Plaza San Martín", "tipo": "feria",
    })

    assert Event.query.one().lugar == "Plaza San Martín"


def test_el_lugar_es_opcional_y_queda_en_none(client, emprendedor_con_post):
    """Vacio se guarda como NULL y no como "", que es "no lo dijo".

    La tarjeta pregunta por `evento.lugar` para decidir si muestra la linea, y
    una cadena vacia la haria mostrar un separador sin nada atras.
    """
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13", "lugar": "",
        "tipo": "feria",
    })

    assert Event.query.one().lugar is None


def test_el_lugar_no_sale_de_la_direccion_del_emprendimiento(
    client, db, emprendedor_con_post
):
    """Un evento sin lugar no hereda posts.address_street.

    La feria de una panaderia normalmente no es en la panaderia: mostrar su
    direccion como lugar del evento seria un dato equivocado con cara de dato
    real (ver el comentario de Event.lugar).
    """
    _usuario, post = emprendedor_con_post()
    post.address_street = "Av. San Martín 1240"
    db.session.commit()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13", "lugar": "",
        "tipo": "feria",
    })

    evento = Event.query.one()
    assert evento.lugar is None

    html = client.get("/eventos/").get_data(as_text=True)
    assert "Av. San Martín 1240" not in html


def test_la_cartelera_muestra_el_lugar_cuando_esta(
    client, emprendedor_con_post, crear_evento
):
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id, titulo="Feria", lugar="Plaza San Martín")

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Plaza San Martín" in html


def test_editar_un_evento_actualiza_el_lugar(
    client, emprendedor_con_post, crear_evento
):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id, lugar="Plaza San Martín")

    client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": evento.titulo,
        "fecha": evento.fecha.isoformat(), "lugar": "Centro cultural",
        "tipo": "feria",
    })

    assert Event.query.one().lugar == "Centro cultural"


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
        "tipo": "feria",
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
        "tipo": "feria",
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
        "tipo": "feria",
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
        "tipo": "feria",
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


# === Calendario del home: consulta por rango y API JSON ===
#
# La consulta y el endpoint se prueban aparte de proximos()/pasados() porque
# responden otra pregunta: en_rango() NO filtra por "todavia no paso" (ver su
# docstring), asi que lo que hay que fijar aca es justamente lo contrario de lo
# que fijan los tests de proximos().


@pytest.fixture
def crear_evento_en(db):
    """Fabrica de eventos en una fecha exacta, no relativa a hoy.

    crear_evento trabaja con "dentro de N dias", que sirve para el corte de
    vencidos pero no para probar bordes de mes: el 1 y el 31 tienen que caer
    donde caen, sin depender de que dia se corra la suite.
    """

    def _crear(post_id, fecha, titulo="Feria", hora=None, descripcion=None):
        evento = Event(
            post_id=post_id, titulo=titulo, descripcion=descripcion,
            fecha=fecha, hora=hora,
        )
        db.session.add(evento)
        db.session.commit()
        return evento

    return _crear


def test_parsear_mes_acepta_el_formato_del_calendario():
    assert parsear_mes("2026-08") == (2026, 8)
    assert parsear_mes("  2026-01  ") == (2026, 1)


@pytest.mark.parametrize("texto", ["", None, "2026", "2026-13", "agosto", "2026-8-1"])
def test_parsear_mes_rechaza_lo_que_no_es_un_mes(texto):
    """Devuelve None en vez de explotar: la vista decide que hacer con eso."""
    assert parsear_mes(texto) is None


def test_rango_del_mes_cubre_el_mes_entero():
    assert rango_del_mes(2026, 8) == (date(2026, 8, 1), date(2026, 8, 31))
    # Meses de 30, y febrero, que es el que se rompe si alguien hardcodea 31.
    assert rango_del_mes(2026, 4) == (date(2026, 4, 1), date(2026, 4, 30))
    assert rango_del_mes(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert rango_del_mes(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))


def test_en_rango_trae_solo_los_del_mes_pedido(db, crear_usuario, crear_post, crear_evento_en):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, date(2026, 7, 31), titulo="Se fue por un dia")
    dentro_primero = crear_evento_en(post.id, date(2026, 8, 1), titulo="Primer dia")
    dentro_ultimo = crear_evento_en(post.id, date(2026, 8, 31), titulo="Ultimo dia")
    crear_evento_en(post.id, date(2026, 9, 1), titulo="Se pasa por un dia")

    desde, hasta = rango_del_mes(2026, 8)
    ids = [evento.id for evento in en_rango(Event.query, desde, hasta).all()]

    # Los dos bordes entran (el rango es inclusivo en las dos puntas) y los
    # vecinos de afuera no.
    assert ids == [dentro_primero.id, dentro_ultimo.id]


def test_en_rango_no_esconde_los_que_ya_pasaron(db, crear_usuario, crear_post, crear_evento):
    """A diferencia de proximos(): sin esto, moverse a un mes anterior mostraria
    un mes vacio y la navegacion del calendario no serviria para nada."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    viejo = crear_evento(post.id, titulo="Feria de la semana pasada", dias=-7)

    hoy = hoy_en_argentina()
    desde, hasta = rango_del_mes(viejo.fecha.year, viejo.fecha.month)
    ids = [evento.id for evento in en_rango(Event.query, desde, hasta).all()]

    assert viejo.id in ids
    # Y proximos() sobre el mismo dato sigue escondiendolo, que es su trabajo.
    assert viejo.id not in [evento.id for evento in proximos(Event.query, hoy).all()]


def test_en_rango_sin_eventos_no_revienta(db):
    desde, hasta = rango_del_mes(2026, 8)

    assert en_rango(Event.query, desde, hasta).all() == []


def test_en_rango_ordena_por_fecha_y_hora(db, crear_usuario, crear_post, crear_evento_en):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    tarde = crear_evento_en(post.id, date(2026, 8, 14), titulo="Tarde", hora=time(18, 0))
    temprano = crear_evento_en(post.id, date(2026, 8, 14), titulo="Temprano", hora=time(9, 0))
    otro_dia = crear_evento_en(post.id, date(2026, 8, 2), titulo="Antes")

    desde, hasta = rango_del_mes(2026, 8)
    ids = [evento.id for evento in en_rango(Event.query, desde, hasta).all()]

    assert ids == [otro_dia.id, temprano.id, tarde.id]


# --- el endpoint ---------------------------------------------------------


def test_api_devuelve_el_mes_pedido(client, crear_usuario, crear_post, crear_evento_en):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id, title="Panadería del barrio")
    crear_evento_en(post.id, date(2026, 8, 14), titulo="Feria de la plaza", hora=time(10, 0))
    crear_evento_en(post.id, date(2026, 9, 1), titulo="Del mes que viene")

    respuesta = client.get("/api/eventos/?mes=2026-08")

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["mes"] == "2026-08"
    assert datos["desde"] == "2026-08-01"
    assert datos["hasta"] == "2026-08-31"
    assert datos["total"] == 1
    assert datos["truncado"] is False
    assert [item["titulo"] for item in datos["items"]] == ["Feria de la plaza"]


def test_api_incluye_el_emprendimiento_y_su_link(client, crear_usuario, crear_post, crear_evento_en):
    """El panel del dia muestra de quien es el evento y linkea al emprendimiento."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id, title="Panadería del barrio")
    crear_evento_en(post.id, date(2026, 8, 14), hora=time(10, 30), descripcion="Traé bolsa")

    datos = client.get("/api/eventos/?mes=2026-08").get_json()
    item = datos["items"][0]

    assert item["emprendimiento"] == "Panadería del barrio"
    assert item["url"] == f"/blog/{post.id}"
    assert item["hora"] == "10:30"
    assert item["descripcion"] == "Traé bolsa"


def test_api_sin_mes_usa_el_mes_en_curso(client, crear_usuario, crear_post, crear_evento):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento(post.id, titulo="De este mes", dias=0)

    datos = client.get("/api/eventos/").get_json()
    hoy = hoy_en_argentina()

    assert datos["mes"] == f"{hoy.year:04d}-{hoy.month:02d}"
    # `hoy` viaja en la respuesta para que el JS marque el dia sin usar el reloj
    # del visitante, que puede estar en otro huso.
    assert datos["hoy"] == hoy.isoformat()
    assert [item["titulo"] for item in datos["items"]] == ["De este mes"]


@pytest.mark.parametrize("mes", ["", "2026", "2026-13", "cualquiera"])
def test_api_con_mes_invalido_cae_al_mes_en_curso(client, mes):
    """No es un 400: el parametro lo escribe el JS, y si algo lo rompe es mejor
    mostrar el mes actual que dejar el calendario en blanco."""
    respuesta = client.get(f"/api/eventos/?mes={mes}")
    hoy = hoy_en_argentina()

    assert respuesta.status_code == 200
    assert respuesta.get_json()["mes"] == f"{hoy.year:04d}-{hoy.month:02d}"


def test_api_sin_eventos_devuelve_lista_vacia(client):
    respuesta = client.get("/api/eventos/?mes=2026-08")

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["items"] == []
    assert datos["total"] == 0
    assert datos["truncado"] is False


def test_api_agrupa_varios_eventos_del_mismo_dia(client, crear_usuario, crear_post, crear_evento_en):
    """El caso que dibuja mas de un punto en la celda y lista varios en el panel."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, date(2026, 8, 20), titulo="Tarde", hora=time(16, 0))
    crear_evento_en(post.id, date(2026, 8, 20), titulo="Temprano", hora=time(9, 0))
    crear_evento_en(post.id, date(2026, 8, 20), titulo="Sin hora")

    datos = client.get("/api/eventos/?mes=2026-08").get_json()

    assert datos["total"] == 3
    assert all(item["fecha"] == "2026-08-20" for item in datos["items"])
    # Sin hora primero: es como los ordena la base (NULL va antes en ASC) y es
    # el mismo orden que ya usa la cartelera.
    assert [item["titulo"] for item in datos["items"]] == ["Sin hora", "Temprano", "Tarde"]


def test_api_es_publica_y_no_depende_de_la_sesion(
    client, crear_usuario, crear_post, crear_evento_en, login
):
    """Event no tiene ningun campo de visibilidad: todo evento es publico, igual
    que en la cartelera de /eventos/ y en el perfil, las dos sin login. Este
    test fija que la respuesta no cambie segun quien mire, para que el dia que
    Event gane un estado (borrador, cancelado) haya que decidirlo a proposito."""
    autor = crear_usuario(username="panaderia")
    post = crear_post(autor.id)
    crear_evento_en(post.id, date(2026, 8, 14))

    anonimo = client.get("/api/eventos/?mes=2026-08").get_json()

    otro = crear_usuario(username="mirona")
    login(otro.id)
    logueado = client.get("/api/eventos/?mes=2026-08").get_json()

    login(autor.id)
    duenio = client.get("/api/eventos/?mes=2026-08").get_json()

    assert anonimo == logueado == duenio


def test_api_no_expone_campos_de_mas(client, crear_usuario, crear_post, crear_evento_en):
    """Fija el contrato: si alguien suma una columna a Event, no se filtra sola
    por serialize() sin que un test lo note."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, date(2026, 8, 14))

    item = client.get("/api/eventos/?mes=2026-08").get_json()["items"][0]

    # `lugar` entra a proposito: es tan publico como el titulo o la
    # descripcion, se muestra en la cartelera y dejarlo afuera del contrato
    # seria arbitrario. El calendario del home todavia no lo pinta.
    # `tipo` y `entrada_libre` entran por lo mismo que `lugar`: son tan
    # publicos como el titulo, ya se muestran en la cartelera, y dejarlos
    # afuera del contrato seria arbitrario. El calendario del home todavia no
    # los pinta.
    assert set(item) == {
        "id", "post_id", "titulo", "descripcion", "fecha", "hora", "lugar",
        "tipo", "tipo_label", "entrada_libre", "emprendimiento", "url",
    }


def test_api_trunca_y_lo_avisa(client, crear_usuario, crear_post, crear_evento_en, monkeypatch):
    """El tope no se puede alcanzar con datos de verdad en un test, asi que se
    baja a 2: lo que importa es que avise en vez de recortar en silencio."""
    monkeypatch.setattr(eventos_api, "MAX_EVENTOS_POR_MES", 2)
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    for numero in range(4):
        crear_evento_en(post.id, date(2026, 8, 10 + numero), titulo=f"Feria {numero}")

    datos = client.get("/api/eventos/?mes=2026-08").get_json()

    assert datos["truncado"] is True
    assert datos["total"] == 2
    assert len(datos["items"]) == 2


def test_el_home_carga_el_calendario(client):
    """El contenedor y el script tienen que estar en el HTML del home: si alguien
    saca el bloque scripts, el calendario queda mudo sin que falle nada."""
    html = client.get("/").get_data(as_text=True)

    assert 'id="calendario-grid"' in html
    assert 'id="calendario-card"' in html
    assert "js/calendario.js" in html


def test_el_home_no_repite_ids(client):
    """Ningun id duplicado en el home, y en particular no "calendario".

    La <section> ancla y la tarjeta que maneja el JS se llamaban las dos
    "calendario". Como getElementById devuelve el PRIMERO, calendario.js se
    quedaba con la section y la clase is-loading no le llegaba nunca a la
    tarjeta, que es la que la usa. No falla nada a la vista, por eso hace falta
    un test.
    """
    import re
    from collections import Counter

    html = client.get("/").get_data(as_text=True)
    # Solo los id= de atributo real, no los que aparecen dentro de comentarios.
    sin_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    # El lookbehind deja afuera data-id="..." y cualquier otro atributo que
    # termine en "id": lo que interesa es el id de verdad.
    ids = re.findall(r'(?<![-\w])id="([^"]+)"', sin_comentarios)
    repetidos = [nombre for nombre, veces in Counter(ids).items() if veces > 1]

    # Que el patron encuentre ALGO: si dejara de matchear, la lista de
    # repetidos quedaria vacia y el test pasaria sin mirar nada. Paso de
    # verdad al escribirlo: un  se colo en el archivo como caracter de
    # backspace y el test daba verde con el id duplicado puesto.
    assert ids, "el patron no encontro ningun id: el test no esta probando nada"
    assert repetidos == []


# --- cartelera: agrupado por mes y honestidad de datos

def test_mes_y_anio_no_depende_del_locale():
    """Escrito a mano y no strftime("%B"), que en el servidor puede dar ingles."""
    assert mes_y_anio(date(2026, 8, 22)) == "agosto 2026"
    assert mes_y_anio(None) == ""


def test_agrupar_por_mes_corta_cuando_cambia_el_mes(
    db, crear_usuario, crear_post, crear_evento
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    # crear_evento toma dias desde hoy; se fuerzan las fechas para que caigan
    # en meses distintos sin depender de cuando corre el test.
    uno = crear_evento(post.id, titulo="Feria de agosto")
    dos = crear_evento(post.id, titulo="Otra de agosto")
    tres = crear_evento(post.id, titulo="Feria de septiembre")
    uno.fecha = date(2026, 8, 22)
    dos.fecha = date(2026, 8, 30)
    tres.fecha = date(2026, 9, 5)
    db.session.commit()

    grupos = agrupar_por_mes([uno, dos, tres])

    assert [g["nombre"] for g in grupos] == ["agosto 2026", "septiembre 2026"]
    assert [len(g["eventos"]) for g in grupos] == [2, 1]


def test_agrupar_por_mes_de_una_lista_vacia():
    assert agrupar_por_mes([]) == []


def test_la_cartelera_agrupa_por_mes(client, emprendedor_con_post, crear_evento):
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id, titulo="Feria próxima", dias=3)

    html = client.get("/eventos/").get_data(as_text=True)

    esperado = mes_y_anio(hoy_en_argentina() + timedelta(days=3))
    assert esperado in html
    assert "1 evento" in html


def test_la_cartelera_cuenta_las_fechas_sin_inventar_la_ciudad(
    client, emprendedor_con_post, crear_evento
):
    """El mockup decia "18 fechas anunciadas por emprendimientos de San Rafael".

    La ciudad no es un dato que Post tenga: misma decision que ya se tomo en
    templates/auth/_panel.html. Queda el numero, que si es real.
    """
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id, dias=3)
    crear_evento(post.id, dias=5)

    html = client.get("/eventos/").get_data(as_text=True)

    assert "2 fechas anunciadas" in html
    assert "San Rafael" not in html


def test_la_cartelera_no_maqueta_lo_que_no_existe(
    client, emprendedor_con_post, crear_evento
):
    """De los tres que el canvas pedia, "Me interesa" sigue sin existir.

    Tipo y entrada libre entraron con la tanda de rediseño (columnas nuevas,
    migracion c7d92f4a1b83). "Me interesa" no: no es una etiqueta, es una
    feature entera -- tabla usuario x evento, ruta, permiso, y decidir si el
    dueño ve quienes son -- y sigue en backlog, no maquetada en falso.
    """
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id, titulo="Feria de la plaza")

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Me interesa" not in html
    assert "interesados" not in html


def test_un_evento_sin_tipo_no_dibuja_el_chip(
    client, emprendedor_con_post, crear_evento
):
    """Los cargados antes de la columna tienen tipo NULL, que es "no lo dijo".

    No se les inventa un tipo ni se los manda a un "Otros" que no existe: la
    tarjeta simplemente no lleva chip. Lo mismo con entrada libre, que nace en
    False y en False no afirma nada.
    """
    _usuario, post = emprendedor_con_post()
    crear_evento(post.id, titulo="Feria vieja")

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Feria vieja" in html
    assert "chip-tipo" not in html
    assert "chip-libre" not in html


def test_el_formulario_de_evento_no_ofrece_guardar_borrador(
    client, emprendedor_con_post
):
    """Event no tiene estado de borrador, ni Post tampoco."""
    emprendedor_con_post()

    html = client.get("/eventos/nuevo").get_data(as_text=True)

    assert "borrador" not in html.lower()


def test_la_vista_previa_aguanta_una_fecha_mal_escrita(
    client, emprendedor_con_post
):
    """Tras un error de validacion el formulario vuelve con el texto crudo.

    La vista previa pregunta por la fecha ya parseada, asi que "13/09/2026"
    -- que no es vacio pero tampoco es una fecha -- no la rompe.
    """
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "13/09/2026",
        "tipo": "feria",
    })

    assert respuesta.status_code == 200
    assert "Así se va a ver en la cartelera" in respuesta.get_data(as_text=True)


# ==========================================================================
# LO QUE AGREGA LA TANDA DE REDISEÑO DE EVENTOS
#
# Dos columnas nuevas (tipo y entrada_libre), el calendario que pasa de
# ilustracion a filtro, los dos vacios distintos, y /eventos/mios, que es la
# pantalla propia que le faltaba al menu del panel.
# ==========================================================================

# ------------------------------------------------ el tipo, puro y en la base

def test_tipo_valido_acepta_los_cuatro_y_nada_mas():
    for clave in TiposEvento.TODOS:
        assert tipo_valido(clave) == clave


@pytest.mark.parametrize("texto", ["", None, "  ", "otros", "FERIA?", "'; DROP"])
def test_un_tipo_inventado_se_ignora_en_vez_de_reventar(texto):
    """Un ?tipo= escrito a mano no rompe la pantalla: vale como "todos".

    Mismo criterio que blog.reglas.categoria_valida con un rubro inexistente.
    """
    assert tipo_valido(texto) is None


def test_tipo_valido_no_distingue_mayusculas():
    assert tipo_valido("Feria") == TiposEvento.FERIA


def test_un_evento_sin_tipo_no_tiene_etiqueta(db, crear_usuario, crear_post,
                                              crear_evento):
    """NULL es "no lo dijo", no un quinto tipo, y por eso la etiqueta es vacia."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    evento = crear_evento(post.id)

    assert evento.tipo is None
    assert evento.tipo_label == ""
    # entrada_libre, en cambio, nace en False y no en NULL: False no afirma
    # nada porque el chip solo se dibuja cuando es True.
    assert evento.entrada_libre is False


# ------------------------------------------------- guardar los dos campos

def test_publicar_guarda_el_tipo_y_la_entrada_libre(client, emprendedor_con_post):
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Taller de torno", "fecha": "2026-09-13",
        "tipo": "taller", "entrada_libre": "1",
    })

    evento = Event.query.one()
    assert evento.tipo == TiposEvento.TALLER
    assert evento.entrada_libre is True


def test_sin_marcar_entrada_libre_queda_en_false(client, emprendedor_con_post):
    """Un checkbox sin marcar no viaja en el POST: eso es False, no None."""
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Taller pago", "fecha": "2026-09-13",
        "tipo": "taller",
    })

    assert Event.query.one().entrada_libre is False


def test_el_tipo_es_obligatorio_al_publicar(client, emprendedor_con_post):
    """La columna es nullable para los eventos viejos, no para los nuevos.

    Si el formulario no lo exigiera, el NULL nunca se agotaria y el filtro por
    tipo dejaria de servir a medida que se carguen eventos.
    """
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Sin tipo", "fecha": "2026-09-13",
    }, follow_redirects=True)

    assert Event.query.count() == 0
    assert "Elegí qué tipo de evento es." in respuesta.get_data(as_text=True)


def test_un_tipo_que_no_existe_se_rechaza_como_si_faltara(
    client, emprendedor_con_post
):
    """El segmentado tiene cuatro botones, pero el POST se manda a mano."""
    _usuario, post = emprendedor_con_post()

    client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Colado", "fecha": "2026-09-13",
        "tipo": "asado",
    })

    assert Event.query.count() == 0


def test_editar_cambia_el_tipo_y_apaga_la_entrada_libre(
    client, db, emprendedor_con_post, crear_evento
):
    _usuario, post = emprendedor_con_post()
    evento = crear_evento(post.id)
    evento.tipo = TiposEvento.FERIA
    evento.entrada_libre = True
    db.session.commit()

    client.post(f"/eventos/{evento.id}/editar", data={
        "post_id": post.id, "titulo": evento.titulo,
        "fecha": evento.fecha.isoformat(), "tipo": "popup",
    })

    guardado = Event.query.get(evento.id)
    assert guardado.tipo == TiposEvento.POPUP
    assert guardado.entrada_libre is False


# ------------------------------------------------------ los filtros de la lista

def _crear_tres(db, crear_usuario, crear_post, crear_evento_en):
    """Una feria libre, un taller pago y un evento viejo sin tipo, el mismo dia."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    dia = hoy_en_argentina() + timedelta(days=5)

    feria = crear_evento_en(post.id, dia, titulo="Feria de la plaza")
    feria.tipo = TiposEvento.FERIA
    feria.entrada_libre = True

    taller = crear_evento_en(post.id, dia, titulo="Taller de torno")
    taller.tipo = TiposEvento.TALLER

    crear_evento_en(post.id, dia, titulo="Evento sin tipo")
    db.session.commit()
    return dia


def test_el_filtro_de_tipo_deja_solo_ese_tipo(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    _crear_tres(db, crear_usuario, crear_post, crear_evento_en)

    html = client.get("/eventos/?tipo=taller").get_data(as_text=True)

    assert "Taller de torno" in html
    assert "Feria de la plaza" not in html


def test_un_evento_sin_tipo_no_entra_en_ningun_filtro_de_tipo(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """NULL no es "de todos los tipos": es "no lo dijo"."""
    _crear_tres(db, crear_usuario, crear_post, crear_evento_en)

    for clave in TiposEvento.TODOS:
        html = client.get(f"/eventos/?tipo={clave}").get_data(as_text=True)
        assert "Evento sin tipo" not in html

    # Con "Todos" -- o sea sin ?tipo= -- sigue apareciendo.
    assert "Evento sin tipo" in client.get("/eventos/").get_data(as_text=True)


def test_el_filtro_de_entrada_libre_deja_solo_las_gratis(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    _crear_tres(db, crear_usuario, crear_post, crear_evento_en)

    html = client.get("/eventos/?libre=1").get_data(as_text=True)

    assert "Feria de la plaza" in html
    assert "Taller de torno" not in html


def test_los_dos_filtros_se_combinan(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """"Talleres con entrada libre" es la pregunta que se hace de verdad."""
    _crear_tres(db, crear_usuario, crear_post, crear_evento_en)

    html = client.get("/eventos/?tipo=taller&libre=1").get_data(as_text=True)

    assert "Taller de torno" not in html
    assert "Feria de la plaza" not in html
    assert "Nada con esos filtros" in html


# ------------------------------------------- el calendario, ahora que filtra

def test_elegir_un_dia_deja_solo_ese_dia(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    hoy = hoy_en_argentina()
    crear_evento_en(post.id, hoy + timedelta(days=3), titulo="La del jueves")
    crear_evento_en(post.id, hoy + timedelta(days=9), titulo="La de la otra semana")

    dia = (hoy + timedelta(days=3)).isoformat()
    html = client.get(f"/eventos/?dia={dia}").get_data(as_text=True)

    assert "La del jueves" in html
    assert "La de la otra semana" not in html


def test_un_dia_ya_pasado_se_puede_mirar(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """El calendario navega meses para atras: si ?dia= escondiera lo vencido,
    esos meses se verian vacios y la navegacion no serviria de nada."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    ayer = hoy_en_argentina() - timedelta(days=1)
    crear_evento_en(post.id, ayer, titulo="La feria de ayer")

    # Sin filtro no esta: la cartelera es lo que viene.
    assert "La feria de ayer" not in client.get("/eventos/").get_data(as_text=True)

    html = client.get(f"/eventos/?dia={ayer.isoformat()}").get_data(as_text=True)
    assert "La feria de ayer" in html


def test_un_dia_mal_escrito_no_filtra_ni_revienta(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() + timedelta(days=3),
                    titulo="La del jueves")

    respuesta = client.get("/eventos/?dia=13/09/2026")

    assert respuesta.status_code == 200
    assert "La del jueves" in respuesta.get_data(as_text=True)


def test_el_calendario_de_la_cartelera_enlaza_los_dias(client):
    """En la cartelera el dia es un ENLACE a ?dia=, no un boton de JavaScript.

    Es lo que lo vuelve un filtro de verdad: se comparte por link y vuelve con
    el boton de atras. El HTML solo lleva la base -- las celdas las arma el JS
    contra /api/eventos -- asi que lo que se chequea es que la base este.
    """
    html = client.get("/eventos/").get_data(as_text=True)

    assert "data-enlace-dia=" in html


def test_el_calendario_del_home_no_enlaza(client):
    """En el home el dia filtra el panel de al lado sin recargar la pagina."""
    html = client.get("/").get_data(as_text=True)

    assert "data-enlace-dia=" not in html


def test_el_dia_elegido_viaja_al_calendario(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """Para marcarlo y para que el calendario abra en SU mes, no en el actual."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    dia = hoy_en_argentina() + timedelta(days=3)
    crear_evento_en(post.id, dia)

    html = client.get(f"/eventos/?dia={dia.isoformat()}").get_data(as_text=True)

    assert f'data-dia-activo="{dia.isoformat()}"' in html


# --------------------------------------------------------- los tres vacios

def test_con_la_base_vacia_dice_que_todavia_no_hay_nada(client):
    html = client.get("/eventos/").get_data(as_text=True)

    assert "Todavía no hay eventos anunciados" in html
    assert "Nada con esos filtros" not in html


def test_con_un_dia_sin_nada_dice_como_salir_del_filtro(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """El vacio del filtro no es el vacio de la cartelera: decir "todavia no
    hay eventos" cuando hay tres la semana que viene es mentira."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() + timedelta(days=9))

    vacio = (hoy_en_argentina() + timedelta(days=3)).isoformat()
    html = client.get(f"/eventos/?dia={vacio}").get_data(as_text=True)

    assert "Nada con esos filtros" in html
    assert "Todavía no hay eventos anunciados" not in html
    assert "Ver todas las fechas" in html


def test_con_todo_vencido_no_dice_que_todavia_no_hay_eventos(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """EL TERCER VACIO. Sin filtros y con la cartelera vacia hay dos motivos
    distintos, y solo uno de los dos permite decir "todavia no hay eventos".

    Aca hay tres eventos cargados y los tres ya pasaron. Los eventos vencidos no
    se borran nunca (la cartelera publica solo los esconde), asi que este es el
    estado normal de una cartelera en temporada baja. Decir "todavia no hay
    eventos anunciados" seria mentira, y encima el calendario del costado les
    sigue pintando el puntito: la pantalla se contradecia sola.
    """
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    for dias in (30, 10, 1):
        crear_evento_en(post.id, hoy_en_argentina() - timedelta(days=dias))

    html = client.get("/eventos/").get_data(as_text=True)

    assert "Todavía no hay eventos anunciados" not in html
    assert "No hay fechas próximas" in html
    # Y dice donde estan: el calendario navega para atras.
    assert "calendario" in html
    # Sigue sin ser el vacio del filtro, porque no hay ningun filtro puesto.
    assert "Nada con esos filtros" not in html


def test_con_todo_vencido_y_un_filtro_gana_el_vacio_del_filtro(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """Con un filtro puesto manda el del filtro: es el que se puede soltar."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() - timedelta(days=10))

    html = client.get("/eventos/?tipo=taller").get_data(as_text=True)

    assert "Nada con esos filtros" in html
    assert "No hay fechas próximas" not in html
    assert "Todavía no hay eventos anunciados" not in html


def test_sin_filtros_no_hay_boton_de_limpiar(
    client, db, crear_usuario, crear_post, crear_evento_en
):
    """Un boton que no tiene nada que limpiar es un boton muerto."""
    usuario = crear_usuario(username="panaderia")
    post = crear_post(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() + timedelta(days=3))

    html = client.get("/eventos/").get_data(as_text=True)

    assert "cartelera__limpiar" not in html


# ------------------------------------------------------------- mis eventos

def test_mis_eventos_junta_los_de_todos_sus_emprendimientos(
    client, db, crear_usuario, crear_post, crear_evento_en, login
):
    """Es lo que no existia: quien tiene dos emprendimientos no tenia ningun
    lado donde ver sus fechas juntas."""
    usuario = crear_usuario(username="tomy")
    uno = crear_post(usuario.id, title="Panadería")
    otro = crear_post(usuario.id, title="Cerámica")
    login(usuario.id)
    crear_evento_en(uno.id, hoy_en_argentina() + timedelta(days=3),
                    titulo="Feria del pan")
    crear_evento_en(otro.id, hoy_en_argentina() + timedelta(days=5),
                    titulo="Pop-up de tazas")

    html = client.get("/eventos/mios").get_data(as_text=True)

    assert "Feria del pan" in html
    assert "Pop-up de tazas" in html


def test_mis_eventos_no_muestra_los_ajenos(
    client, db, crear_usuario, crear_post, crear_evento_en, login
):
    ajena = crear_usuario(username="ajena")
    post_ajeno = crear_post(ajena.id, title="Otra")
    crear_evento_en(post_ajeno.id, hoy_en_argentina() + timedelta(days=3),
                    titulo="Feria ajena")

    mia = crear_usuario(username="tomy")
    crear_post(mia.id)
    login(mia.id)

    html = client.get("/eventos/mios").get_data(as_text=True)

    assert "Feria ajena" not in html


def test_mis_eventos_parte_proximos_de_pasados(
    client, db, crear_usuario, crear_post, crear_evento_en, login
):
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    login(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() + timedelta(days=3),
                    titulo="La que viene")
    crear_evento_en(post.id, hoy_en_argentina() - timedelta(days=20),
                    titulo="La del mes pasado")

    html = client.get("/eventos/mios").get_data(as_text=True)

    # Lo que viene primero: es lo que hay que mirar. El historial se repasa.
    assert html.index("La que viene") < html.index("La del mes pasado")
    assert "Ya pasaron" in html


def test_los_pasados_no_se_borran_solos(
    client, db, crear_usuario, crear_post, crear_evento_en, login
):
    """La cartelera publica los esconde; la pantalla del dueño no."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    login(usuario.id)
    crear_evento_en(post.id, hoy_en_argentina() - timedelta(days=20),
                    titulo="La del mes pasado")

    assert "La del mes pasado" not in client.get("/eventos/").get_data(as_text=True)
    assert "La del mes pasado" in client.get("/eventos/mios").get_data(as_text=True)


def test_borrar_desde_mis_eventos_pide_confirmacion(
    client, db, crear_usuario, crear_post, crear_evento_en, login
):
    """Borrar un evento no se revierte: el POST vive detras de un aviso."""
    usuario = crear_usuario(username="tomy")
    post = crear_post(usuario.id)
    login(usuario.id)
    evento = crear_evento_en(post.id, hoy_en_argentina() + timedelta(days=3))

    html = client.get("/eventos/mios").get_data(as_text=True)

    assert "¿Borrás este evento?" in html
    assert "No se puede deshacer" in html
    assert f"/eventos/{evento.id}/eliminar" in html


def test_mis_eventos_pide_sesion(client):
    respuesta = client.get("/eventos/mios")

    assert respuesta.status_code == 302
    assert "login" in respuesta.headers["Location"]


def test_publicar_vuelve_a_mis_eventos(client, emprendedor_con_post):
    """Antes volvia al perfil, que era el unico lado donde se veian. Ahora hay
    una pantalla que los junta y es de donde se entro."""
    _usuario, post = emprendedor_con_post()

    respuesta = client.post("/eventos/nuevo", data={
        "post_id": post.id, "titulo": "Feria", "fecha": "2026-09-13",
        "tipo": "feria",
    })

    assert respuesta.headers["Location"].endswith("/eventos/mios")
