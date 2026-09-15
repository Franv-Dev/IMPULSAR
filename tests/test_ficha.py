"""Tests de la ficha del emprendimiento (`blog/detail.html`).

El rediseño de `disenio-ficha/` arregla siete cosas que la ficha vieja hacía
mal, y cada una tiene su test acá: el "Usuario #7" en vez del nombre, las
estrellas escritas como glifos, las ferias que no aparecían, el "abierto ahora"
sin hora de cierre, las miniaturas que abrían el archivo suelto, y la ausencia
de cualquier estado vacío pensado.

Los recortes se hacen con html.parser y no con índices de string: los bloques
de la ficha están anidados y varias afirmaciones son sobre lo que un bloque NO
tiene.
"""

import re
from datetime import date, time, timedelta

from app.blog.modelo_resenia import Review
from app.perfil.modelo_horario import Horario
from models.event import Event
from services.horarios import ahora_en_argentina
from tests.test_navegacion import _recortar


def _html(respuesta):
    return respuesta.get_data(as_text=True)


def _ficha(client, post_id):
    return _html(client.get(f"/blog/{post_id}"))


def _horarios_de_toda_la_semana(db, user_id, abre=time(9), cierra=time(20)):
    """Abierto todos los días a la misma hora, para que el test no dependa de
    qué día se corre."""
    for dia in range(7):
        db.session.add(Horario(
            user_id=user_id, dia_semana=dia, cerrado=False, abre=abre, cierra=cierra,
        ))
    db.session.commit()


# --- las reseñas llevan el nombre de quien las escribió


def test_la_resenia_se_firma_con_el_nombre_y_no_con_el_id(
    client, db, crear_usuario, crear_post, login
):
    """Decía "Usuario #7". El nombre de quien escribió no se mostraba en ningún
    lado, ni siquiera en el perfil enlazado."""
    autor = crear_usuario(username="autor")
    clienta = crear_usuario(username="Camila Suárez")
    post = crear_post(autor.id)

    login(clienta.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Impecable"})

    resenias = _recortar(_ficha(client, post.id), "resenias-ficha")

    assert "Camila Suárez" in resenias
    assert f"Usuario #{clienta.id}" not in resenias


def test_las_estrellas_son_svg_y_no_glifos(client, db, crear_usuario, crear_post, login):
    """Eran ★ y ☆ escritos como texto: cambian de dibujo según la fuente y en
    algunos sistemas el ☆ sale como recuadro."""
    autor = crear_usuario(username="autor")
    clienta = crear_usuario(username="clienta")
    post = crear_post(autor.id)

    login(clienta.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "3", "comment": "Ahí va"})

    resenias = _recortar(_ficha(client, post.id), "resenias-ficha")

    assert "★" not in resenias
    assert "☆" not in resenias
    # El modificador contiene el nombre de la clase base, asi que hay que contar
    # la apertura del atributo y no el substring pelado.
    assert resenias.count('class="estrellas__una') == 5
    assert resenias.count("estrellas__una--llena") == 3


def test_la_resenia_dice_hace_cuanto_es(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    clienta = crear_usuario(username="clienta")
    post = crear_post(autor.id)

    login(clienta.id)
    client.post(f"/blog/{post.id}/review", data={"rating": "5", "comment": "Hoy mismo"})

    resenias = _recortar(_ficha(client, post.id), "resenias-ficha")

    assert "recién" in resenias or "hace" in resenias


# --- abierto ahora, con hora de cierre


def test_abierto_ahora_dice_a_que_hora_cierra(client, db, crear_usuario, crear_post):
    """Con un sí/no pelado hay que bajar hasta la tabla de horarios para saber
    si conviene salir ahora."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    # Una ventana que cubre cualquier hora del día menos la madrugada; el test
    # se saltea si corre justo ahí, en vez de afirmar algo falso.
    ahora = ahora_en_argentina().time()
    if not (time(1) < ahora < time(22, 30)):
        return
    _horarios_de_toda_la_semana(db, autor.id, abre=time(1), cierra=time(23))

    ficha = _ficha(client, post.id)

    assert "Abierto ahora" in ficha
    assert "cierra 23:00" in ficha


def test_cerrado_no_inventa_una_hora_de_cierre(client, db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for dia in range(7):
        db.session.add(Horario(user_id=autor.id, dia_semana=dia, cerrado=True))
    db.session.commit()

    ficha = _ficha(client, post.id)

    assert "Cerrado ahora" in ficha
    assert "cierra" not in ficha


def test_sin_horarios_no_se_pinta_ningun_estado(client, crear_usuario, crear_post):
    """Sin horarios cargados no se sabe si está abierto: no se dice ni que sí
    ni que no."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    identidad = _recortar(_ficha(client, post.id), "ficha-bloque--identidad")

    assert "Abierto" not in identidad
    assert "Cerrado" not in identidad


# --- las ferias


def test_la_ficha_muestra_las_ferias_que_vienen(client, db, crear_usuario, crear_post):
    """Post.eventos existe desde la tanda de eventos y la ficha no lo mostraba.
    Es el dato que ni Mercado Libre ni Marketplace tienen."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Event(
        post_id=post.id, titulo="Feria de Plaza Mitre",
        fecha=date.today() + timedelta(days=6), hora=time(10), lugar="Plaza Mitre",
    ))
    db.session.commit()

    ficha = _ficha(client, post.id)

    assert "Dónde encontrarla" in ficha
    assert "Feria de Plaza Mitre" in ficha


def test_una_feria_que_ya_paso_no_se_muestra(client, db, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Event(
        post_id=post.id, titulo="Feria del mes pasado",
        fecha=date.today() - timedelta(days=30),
    ))
    db.session.commit()

    assert "Feria del mes pasado" not in _ficha(client, post.id)


def test_la_feria_de_otro_emprendimiento_no_se_cuela(
    client, db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    mio = crear_post(autor.id, title="El mío")
    ajeno = crear_post(autor.id, title="El otro")
    db.session.add(Event(
        post_id=ajeno.id, titulo="Feria ajena", fecha=date.today() + timedelta(days=3),
    ))
    db.session.commit()

    assert "Feria ajena" not in _ficha(client, mio.id)


# --- la galería


def test_las_fotos_abren_en_el_visor_y_no_en_el_archivo_suelto(
    client, db, crear_usuario, crear_post
):
    """Antes las miniaturas eran <a> a /static/uploads/: abrían la foto cruda en
    otra pestaña, sin el emprendimiento, sin las otras fotos y sin volver."""
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, image="uno.png")
    db.session.add(PostImage(post_id=post.id, filename="dos.png"))
    db.session.commit()

    galeria = _recortar(_ficha(client, post.id), "ficha-galeria")

    # Botones que abren el visor, no enlaces que se van del sitio.
    assert 'data-visor="0"' in galeria
    assert "<a " not in galeria
    assert 'target="_blank"' not in galeria


def test_el_visor_solo_se_arma_si_hay_mas_de_una_foto(
    client, db, crear_usuario, crear_post
):
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    una = crear_post(autor.id, title="Una sola", image="uno.png")
    assert 'id="visor"' not in _ficha(client, una.id)
    assert "js/visor.js" not in _ficha(client, una.id)

    varias = crear_post(autor.id, title="Varias", image="uno.png")
    db.session.add(PostImage(post_id=varias.id, filename="dos.png"))
    db.session.commit()
    assert 'id="visor"' in _ficha(client, varias.id)
    assert "js/visor.js" in _ficha(client, varias.id)


def test_el_contador_de_fotos_dice_cuantas_hay(client, db, crear_usuario, crear_post):
    from app.blog.modelo_imagen import PostImage

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id, image="uno.png")
    for nombre in ("dos.png", "tres.png"):
        db.session.add(PostImage(post_id=post.id, filename=nombre))
    db.session.commit()

    assert "Ver las 3 fotos" in _recortar(_ficha(client, post.id), "ficha-galeria")


# --- lo que ve la dueña y lo que ve un visitante


def test_la_duenia_sabe_que_esta_parada_en_su_propia_ficha(
    client, crear_usuario, crear_post, login
):
    """La app no lo decía en ningún lado, y sin eso los bloques vacíos se leen
    como una pantalla rota."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    login(autor.id)

    assert "Ésta es tu ficha" in _ficha(client, post.id)


def test_un_visitante_no_ve_la_barra_de_duenia_ni_las_visitas(
    client, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    ficha = _ficha(client, post.id)

    assert "Ésta es tu ficha" not in ficha
    assert "visitas" not in ficha


def test_a_la_duenia_se_le_muestran_los_dos_bloques_aunque_esten_vacios(
    client, crear_usuario, crear_post, login
):
    """Si no, nunca se entera de que puede cargar servicios."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    login(autor.id)

    ficha = _ficha(client, post.id)

    assert "Todavía no cargaste productos" in ficha
    assert "Todavía no cargaste servicios" in ficha


def test_a_un_visitante_no_se_le_dibuja_un_bloque_vacio(
    client, crear_usuario, crear_post
):
    """Un emprendimiento que es puro servicio no muestra un "Lo que vende" en
    blanco."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    ficha = _ficha(client, post.id)

    assert "Lo que vende" not in ficha
    assert "Lo que hace por encargo" not in ficha


def test_la_lista_de_lo_que_falta_cuenta_bien(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)  # nombre y descripción, nada más
    login(autor.id)

    assert "1 de 5" in _ficha(client, post.id)

    _horarios_de_toda_la_semana(db, autor.id)
    assert "2 de 5" in _ficha(client, post.id)


def test_la_lista_de_lo_que_falta_desaparece_cuando_esta_completa(
    client, db, crear_usuario, crear_post, login
):
    from models.product import Product

    autor = crear_usuario(username="autor")
    post = crear_post(
        autor.id, image="uno.png", latitude=-32.89, longitude=-68.82,
    )
    _horarios_de_toda_la_semana(db, autor.id)
    db.session.add(Product(post_id=post.id, nombre="Algo", precio=100))
    db.session.commit()
    login(autor.id)

    assert "Completá tu ficha" not in _ficha(client, post.id)


def test_la_barra_fija_del_telefono_no_se_le_dibuja_a_la_duenia(
    client, crear_usuario, crear_post, login
):
    """Sus acciones están arriba, en la barra de dueña: una barra fija que
    dijera "enviá un mensaje" a su propia ficha no tiene sentido."""
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    assert 'class="ficha-barra"' not in _ficha(client, post.id)

    otra = crear_usuario(username="otra")
    login(otra.id)
    assert 'class="ficha-barra"' in _ficha(client, post.id)


def test_sin_sesion_no_se_ofrece_pedir_presupuesto_sino_entrar(
    client, db, crear_usuario, crear_post
):
    """La solicitud necesita a quién atribuírsela."""
    from app.servicios.modelo import Rubros, Service

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Service(post_id=post.id, rubro=Rubros.OTROS, titulo="Arreglos"))
    db.session.commit()

    servicios = _recortar(_ficha(client, post.id), "ficha-servicios")

    assert "Entrá para pedir presupuesto" in servicios
    assert "/servicios/" not in servicios or "solicitar" not in servicios


# --- iconografía


def test_la_ficha_no_usa_emoji_como_icono(client, db, crear_usuario, crear_post):
    """Había un 📍 en cada servicio. Los emoji cambian de dibujo según el
    sistema y no se pueden recolorear (regla de la guía de diseño)."""
    from app.servicios.modelo import Rubros, Service

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    db.session.add(Service(
        post_id=post.id, rubro=Rubros.OTROS, titulo="Arreglos",
        zona_cobertura="Godoy Cruz",
    ))
    db.session.commit()

    servicios = _recortar(_ficha(client, post.id), "ficha-servicios")

    assert "📍" not in servicios
    assert "Godoy Cruz" in servicios


# --- las consultas


def test_las_resenias_no_disparan_una_consulta_por_autor(
    client, db, crear_usuario, crear_post, login
):
    """El nombre de cada autor viene en el mismo query (joinedload). Sin eso
    serían tantas consultas como reseñas tenga el emprendimiento.

    Se mide con el identity map vaciado: si queda poblado, los autores salen de
    memoria y el contador da un falso negativo.
    """
    from sqlalchemy import event

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)
    for n in range(4):
        clienta = crear_usuario(username=f"clienta{n}", email=f"c{n}@test.com")
        db.session.add(Review(
            post_id=post.id, user_id=clienta.id, rating=5, comment=f"Reseña {n}",
        ))
    db.session.commit()

    from app.blog import consultas

    consultas_hechas = []

    def contar(conn, cursor, sentencia, *_resto):
        consultas_hechas.append(sentencia)

    # El id se guarda ANTES de vaciar el identity map: despues de expunge_all()
    # leer post.id dispara un refresh sobre una instancia ya desprendida.
    post_id = post.id
    db.session.expunge_all()
    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        resenias = consultas.resenias_de(post_id)
        nombres = [r.user.username for r in resenias]
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)

    assert len(nombres) == 4
    assert len(consultas_hechas) == 1, (
        f"{len(consultas_hechas)} consultas para 4 reseñas: volvió el N+1"
    )


def _tareas_de_la_ficha(html):
    """Cada tarea del checklist de la dueña, con si esta marcada como hecha.

    Se leen las cinco filas y no solo el contador "3 de 5": el contador podria
    seguir dando el mismo numero con otra tarea marcada, y lo que hay que
    congelar es el estado de cada una.
    """
    tareas = []
    for clases, cuerpo in re.findall(
        r'<li class="ficha-tareas__item ([^"]*)">(.*?)</li>', html, re.S
    ):
        etiqueta = re.search(
            r'class="ficha-tareas__etiqueta">(.*?)</span>', cuerpo, re.S
        )
        assert etiqueta, "una tarea del checklist salio sin etiqueta"
        tareas.append((
            " ".join(etiqueta.group(1).split()),
            "ficha-tareas__item--hecha" in clases,
        ))
    return tareas


def test_una_pagina_fuera_de_rango_no_vacia_el_resto_de_la_ficha(
    client, db, crear_usuario, crear_post, login
):
    """Pedir una pagina que no existe no puede apagar lo que no es la lista.

    DE DONDE SALE ESTE TEST. Desde que el catalogo de la ficha pagina, la
    variable de los productos es la PAGINA y ya no el catalogo entero, asi que
    con `?page=99` viene vacia aunque el emprendimiento venda. Todo lo que
    preguntaba "hay productos?" mirando esa lista pasa a contestar que no:

      - a la dueña se le apagaba la tarea "Cargar un producto o un servicio"
        del checklist, o sea que la ficha le pedia cargar algo que ya tenia
        cargado (y con el contador, le movia el progreso para atras);
      - al visitante le desaparecia la seccion "Lo que vende" ENTERA, con su
        ancla incluida, de un emprendimiento que si vende.

    Por eso las preguntas de "hay productos" miran el TOTAL del paginado
    (`hay_productos`) y no la lista de la pagina. El guard es load-bearing y la
    suite no lo notaba: revertirlo a mano dejaba todo en verde.

    Se piden las dos formas de salirse del rango: `?page=99` --por arriba, que
    es la que devuelve una pagina vacia-- y `?page=0` --por abajo, que el
    paginado colapsa a la 1--. La segunda no ejercita el guard, pero congela
    que no conteste un 404 ni se coma la seccion por otro camino.

    El estado del checklist es real y no completo a proposito: quedan dos
    tareas sin hacer (la direccion en el mapa y las fotos), asi que el bloque
    se dibuja y se puede comparar. Con las cinco hechas no se dibuja y el test
    no probaria nada.
    """
    from models.product import Product

    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)          # nombre y descripcion, nada mas
    _horarios_de_toda_la_semana(db, autor.id)
    db.session.add(Product(post_id=post.id, nombre="Alfajores", precio=1500))
    db.session.commit()
    post_id = post.id

    fuera_de_rango = ("?page=99", "?page=0")

    # --- el visitante: las secciones que no son la lista siguen ahi
    en_la_primera = _ficha(client, post_id)
    assert 'id="ficha-productos"' in en_la_primera

    for cola in fuera_de_rango:
        respuesta = client.get(f"/blog/{post_id}{cola}")
        assert respuesta.status_code == 200, f"la ficha se rompio con {cola}"
        html = _html(respuesta)
        # La seccion de productos y su ancla, que es lo que desaparecia.
        assert 'id="ficha-productos"' in html, cola
        assert ">Lo que vende</a>" in html, cola
        # Y el resto de los bloques de la ficha, que nunca dependieron de la
        # pagina y tampoco tienen que empezar a depender.
        for ancla in ('id="ficha-arriba"', 'id="ficha-resenias"',
                      'id="ficha-informacion"'):
            assert ancla in html, f"{ancla} con {cola}"

    # --- la dueña: el checklist sigue con su estado real
    login(autor.id)
    tareas_en_la_primera = _tareas_de_la_ficha(_ficha(client, post_id))

    assert len(tareas_en_la_primera) == 5
    assert sum(1 for _, hecha in tareas_en_la_primera if hecha) == 3
    assert ("Cargar un producto o un servicio", True) in tareas_en_la_primera

    for cola in fuera_de_rango:
        html = _html(client.get(f"/blog/{post_id}{cola}"))
        assert "3 de 5" in html, f"el contador se movio con {cola}"
        assert _tareas_de_la_ficha(html) == tareas_en_la_primera, cola
