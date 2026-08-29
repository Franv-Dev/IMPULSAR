"""Tests del panel de administrador: acceso, metricas, baneo y moderacion."""

from datetime import timedelta

from db import utcnow
from app.blog.modelo_post import Categorias, Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from models.user import Roles, User


def test_un_usuario_comun_no_puede_entrar_al_panel(client, crear_usuario, login):
    usuario = crear_usuario(username="tomy", rol=Roles.USUARIO)
    login(usuario.id)

    resp = client.get("/admin/")

    assert resp.status_code == 403


def test_un_anonimo_es_redirigido_al_login(client):
    resp = client.get("/admin/", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_el_admin_ve_las_metricas(client, crear_usuario, crear_post, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "Usuarios" in html
    assert "Emprendimientos" in html


def test_el_admin_puede_banear_y_desbanear_a_un_usuario(
    client, db, crear_usuario, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    usuario = crear_usuario(username="molesto")

    login(admin.id)
    client.post(f"/admin/usuarios/{usuario.id}/ban")

    db.session.refresh(usuario)
    assert usuario.is_banned is True

    client.post(f"/admin/usuarios/{usuario.id}/ban")
    db.session.refresh(usuario)
    assert usuario.is_banned is False


def test_banear_a_un_usuario_corta_su_sesion_activa(client, db, crear_usuario, login):
    """No alcanza con chequear is_banned en el login: si banean a alguien que
    ya esta navegando, tiene que perder el acceso en el proximo request."""
    usuario = crear_usuario(username="molesto")

    login(usuario.id)
    assert client.get("/blog/mis-emprendimientos").status_code == 200

    usuario.is_banned = True
    db.session.commit()

    resp = client.get("/blog/mis-emprendimientos", follow_redirects=False)

    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    with client.session_transaction() as sesion:
        assert sesion.get("user_id") is None


def test_un_usuario_desbaneado_recupera_el_acceso_iniciando_sesion_de_nuevo(
    client, db, crear_usuario, login
):
    usuario = crear_usuario(username="tomy")
    usuario.is_banned = True
    db.session.commit()

    login(usuario.id)
    assert client.get("/blog/mis-emprendimientos", follow_redirects=False).status_code == 302

    usuario.is_banned = False
    db.session.commit()

    login(usuario.id)
    assert client.get("/blog/mis-emprendimientos").status_code == 200


def test_no_se_puede_banear_a_otro_admin(client, db, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    otro_admin = crear_usuario(username="jefe2", rol=Roles.ADMIN)

    login(admin.id)
    client.post(f"/admin/usuarios/{otro_admin.id}/ban")

    db.session.refresh(otro_admin)
    assert otro_admin.is_banned is False


def test_un_admin_no_puede_banearse_a_si_mismo(client, db, crear_usuario, login):
    """Se cae en el mismo chequeo que bloquea banear a otro admin (todo admin
    esta exento), pero lo fijamos como comportamiento intencional aparte."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    client.post(f"/admin/usuarios/{admin.id}/ban")

    db.session.refresh(admin)
    assert admin.is_banned is False


def test_un_usuario_baneado_no_puede_iniciar_sesion(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    usuario.is_banned = True
    db.session.commit()

    resp = client.post(
        "/auth/login",
        data={"username": "tomy", "password": "secreta123"},
        follow_redirects=False,
    )

    assert resp.status_code == 200  # se queda en el form con el error
    with client.session_transaction() as sesion:
        assert sesion.get("user_id") is None


def test_un_usuario_baneado_no_puede_iniciar_sesion_por_api(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy", email="tomy@test.com")
    usuario.is_banned = True
    db.session.commit()

    resp = client.post("/auth/api/login", json={
        "email": "tomy@test.com", "password": "secreta123",
    })

    assert resp.status_code == 403


def test_el_admin_puede_eliminar_cualquier_emprendimiento(
    client, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(admin.id)
    client.post(f"/admin/emprendimientos/{post.id}/eliminar")

    assert Post.query.get(post.id) is None


def test_un_usuario_comun_no_puede_eliminar_desde_el_panel_de_admin(
    client, crear_usuario, crear_post, login
):
    usuario = crear_usuario(username="tomy", rol=Roles.USUARIO)
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(usuario.id)
    resp = client.post(f"/admin/emprendimientos/{post.id}/eliminar")

    assert resp.status_code == 403
    assert Post.query.get(post.id) is not None


# --- moderacion de resenias

def _resenia_reportada(db, crear_usuario, crear_post):
    """Una resenia de un tercero, ya reportada. Devuelve (post, review)."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1, comment="Insultos")
    db.session.add(review)
    db.session.commit()
    db.session.add(Report(
        reporter_id=denunciante.id, review_id=review.id, reason="Lenguaje ofensivo"
    ))
    db.session.commit()
    return post, review


def test_el_admin_puede_eliminar_cualquier_resenia(
    client, db, crear_usuario, crear_post, login
):
    """El unico borrado de resenia era blog.delete_review, que pide ser su autor.

    Sin esta ruta, un reporte de tipo "Reseña" se podia marcar resuelto pero
    no se podia actuar sobre el.
    """
    _post, review = _resenia_reportada(db, crear_usuario, crear_post)
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    client.post(f"/admin/resenias/{review.id}/eliminar")

    assert Review.query.get(review.id) is None


def test_eliminar_una_resenia_reportada_la_saca_de_la_cola(
    client, db, crear_usuario, crear_post, login
):
    """El reporte no se marca resuelto a mano: se va en cascada con la resenia.

    reports.review_id es ON DELETE CASCADE, igual que reports.post_id.
    """
    _post, review = _resenia_reportada(db, crear_usuario, crear_post)
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    client.post(f"/admin/resenias/{review.id}/eliminar")

    assert Report.query.filter_by(review_id=review.id).count() == 0


def test_un_usuario_comun_no_puede_eliminar_una_resenia_desde_el_panel(
    client, db, crear_usuario, crear_post, login
):
    _post, review = _resenia_reportada(db, crear_usuario, crear_post)
    entrometido = crear_usuario(username="entrometido", rol=Roles.USUARIO)

    login(entrometido.id)
    resp = client.post(f"/admin/resenias/{review.id}/eliminar")

    assert resp.status_code == 403
    assert Review.query.get(review.id) is not None


def test_la_cola_de_reportes_ofrece_eliminar_la_resenia(
    client, db, crear_usuario, crear_post, login
):
    """Antes la fila de un reporte de resenia solo tenia "Marcar resuelto"."""
    _post, review = _resenia_reportada(db, crear_usuario, crear_post)
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/reportes").get_data(as_text=True)

    assert f"/admin/resenias/{review.id}/eliminar" in html


# --- resumen: metricas y colas

def test_el_resumen_muestra_las_altas_del_periodo(
    client, db, crear_usuario, crear_post, login
):
    """El delta sale de un COUNT con WHERE sobre la fecha de alta.

    No hace falta ninguna tabla de historico: User.created_at, Post.created y
    Review.created ya dicen cuando se creo cada fila.
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    reciente = crear_post(autor.id, title="Panadería nueva")
    viejo = crear_post(autor.id, title="Panadería vieja")
    viejo.created = utcnow() - timedelta(days=90)
    db.session.commit()

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    # Dos emprendimientos en total, pero uno solo entra en la ventana.
    assert "+1 en 30 días" in html
    assert reciente.id and viejo.id


def test_el_resumen_no_inventa_la_metrica_de_actividad(
    client, crear_usuario, crear_post, login
):
    """El cuarto tile del diseño no va: "actividad" no existe en el modelo.

    Post no tiene updated_at, asi que habria que elegir entre su ultimo
    evento, su ultimo producto o su ultima resenia. Cualquiera de las tres
    seria una definicion inventada presentada como dato.
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "sin actividad" not in html.lower()
    assert "sin publicar hace" not in html.lower()


def test_el_resumen_no_ofrece_exportar(client, crear_usuario, login):
    """No hay exportacion de metricas ni de nada: el boton no se dibuja."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "Exportar" not in html


def test_el_resumen_cuenta_lo_que_hay_pendiente(
    client, db, crear_usuario, crear_post, login
):
    _post, _review = _resenia_reportada(db, crear_usuario, crear_post)
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "Hoy hay 1 cosa para revisar" in html


def test_sin_nada_pendiente_el_resumen_no_dice_que_hay_cosas(
    client, crear_usuario, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "No hay nada pendiente" in html
    assert "cosas para revisar" not in html


def test_el_resumen_permite_actuar_sobre_la_cola_de_reportes(
    client, db, crear_usuario, crear_post, login
):
    """Las acciones del resumen son las mismas rutas de la pantalla de la cola."""
    _post, review = _resenia_reportada(db, crear_usuario, crear_post)
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    reporte = Report.query.filter_by(review_id=review.id).one()
    assert f"/admin/reportes/{reporte.id}/resolver" in html
    assert f"/admin/resenias/{review.id}/eliminar" in html


# --- usuarios: buscador, filtros y paginado

def test_el_listado_de_usuarios_pagina(client, crear_usuario, login):
    """Antes hacia .all() y traia la tabla entera a memoria y al HTML."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    for numero in range(25):
        crear_usuario(username=f"vecino{numero:02d}")

    login(admin.id)
    html = client.get("/admin/usuarios").get_data(as_text=True)

    # 26 usuarios en total, 20 por pagina.
    assert "Mostrando 20 de 26" in html
    assert "vecino00" in html
    assert "vecino23" not in html


def test_el_buscador_de_usuarios_filtra_de_verdad(client, crear_usuario, login):
    """Si la pantalla muestra un buscador, tiene que recortar la consulta."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    crear_usuario(username="panaderia.sur", email="hola@laespiga.com.ar")
    crear_usuario(username="tallerbarro", email="taller@elbarro.ar")

    login(admin.id)
    html = client.get("/admin/usuarios?q=panaderia").get_data(as_text=True)

    assert "panaderia.sur" in html
    assert "tallerbarro" not in html


def test_el_buscador_de_usuarios_tambien_busca_por_mail(client, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    crear_usuario(username="panaderia.sur", email="hola@laespiga.com.ar")
    crear_usuario(username="tallerbarro", email="taller@elbarro.ar")

    login(admin.id)
    html = client.get("/admin/usuarios?q=elbarro").get_data(as_text=True)

    assert "tallerbarro" in html
    assert "panaderia.sur" not in html


def test_el_filtro_por_rol_recorta_la_lista(client, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    crear_usuario(username="vendedora", rol=Roles.EMPRENDEDOR)
    crear_usuario(username="visitante", rol=Roles.USUARIO)

    login(admin.id)
    html = client.get("/admin/usuarios?filtro=emprendedores").get_data(as_text=True)

    assert "vendedora" in html
    assert "visitante" not in html


def test_el_filtro_de_baneados_es_por_estado_y_no_por_rol(
    client, db, crear_usuario, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    castigado = crear_usuario(username="molesto", rol=Roles.EMPRENDEDOR)
    crear_usuario(username="tranquilo", rol=Roles.EMPRENDEDOR)
    castigado.is_banned = True
    db.session.commit()

    login(admin.id)
    html = client.get("/admin/usuarios?filtro=baneados").get_data(as_text=True)

    assert "molesto" in html
    assert "tranquilo" not in html


def test_el_buscador_y_el_filtro_se_combinan(client, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    crear_usuario(username="pan.emprende", rol=Roles.EMPRENDEDOR)
    crear_usuario(username="pan.visita", rol=Roles.USUARIO)

    login(admin.id)
    html = client.get("/admin/usuarios?filtro=emprendedores&q=pan").get_data(as_text=True)

    assert "pan.emprende" in html
    assert "pan.visita" not in html


def test_un_filtro_inventado_no_rompe_la_pantalla(client, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    crear_usuario(username="vecina")

    login(admin.id)
    resp = client.get("/admin/usuarios?filtro=marcianos")

    assert resp.status_code == 200
    assert "vecina" in resp.get_data(as_text=True)


def test_el_panel_de_usuarios_no_promete_ocultar_publicaciones(
    client, crear_usuario, login
):
    """is_banned corta la sesion, pero no filtra ningun listado.

    El diseño decia "Banear cierra la sesión y oculta sus publicaciones". La
    segunda mitad es falsa hoy: no hay ni un filtro por is_banned fuera del
    login. Mismo criterio que el sello "Verificado".
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/usuarios").get_data(as_text=True)

    assert "Banear cierra la sesión" in html
    assert "oculta sus publicaciones" not in html


def test_el_panel_de_usuarios_no_ofrece_exportar_csv(client, crear_usuario, login):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)

    login(admin.id)
    html = client.get("/admin/usuarios").get_data(as_text=True)

    assert "CSV" not in html


# --- moderacion de emprendimientos

def test_la_lista_de_moderacion_muestra_los_reportes_por_fila(
    client, db, crear_usuario, crear_post, login
):
    """El conteo por fila sale de una subconsulta agrupada, no de un COUNT por fila."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    otro = crear_usuario(username="otro")
    reportado = crear_post(autor.id, title="Ofertas Express")
    crear_post(autor.id, title="Panadería tranquila")
    db.session.add(Report(reporter_id=denunciante.id, post_id=reportado.id, reason="Precios falsos"))
    db.session.add(Report(reporter_id=otro.id, post_id=reportado.id, reason="Fotos ajenas"))
    db.session.commit()

    login(admin.id)
    html = client.get("/admin/emprendimientos").get_data(as_text=True)

    assert "2 reportes sin resolver" in html


def test_un_reporte_resuelto_no_cuenta_en_la_lista_de_moderacion(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id, title="Ya revisado")
    db.session.add(Report(
        reporter_id=denunciante.id, post_id=post.id, reason="x", resolved=True
    ))
    db.session.commit()

    login(admin.id)
    html = client.get("/admin/emprendimientos").get_data(as_text=True)

    assert "Ya revisado" in html
    assert "sin resolver" not in html


def test_los_emprendimientos_reportados_aparecen_primero(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    crear_post(autor.id, title="Tranquilo")
    reportado = crear_post(autor.id, title="Denunciado")
    db.session.add(Report(reporter_id=denunciante.id, post_id=reportado.id, reason="x"))
    db.session.commit()

    login(admin.id)
    html = client.get("/admin/emprendimientos").get_data(as_text=True)

    assert html.index("Denunciado") < html.index("Tranquilo")


def test_la_lista_de_moderacion_avisa_que_borra_la_cascada(
    client, crear_usuario, crear_post, login
):
    """Antes solo habia un confirm() generico de "no se puede deshacer".

    El borrado en cascada es real: Post declara cascade="all, delete-orphan"
    en imagenes, eventos, productos y servicios, y las FK de reviews y reports
    son ON DELETE CASCADE. Si se lleva todo eso, hay que decirlo.
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    crear_post(autor.id)

    login(admin.id)
    html = client.get("/admin/emprendimientos").get_data(as_text=True)

    for cosa in ("productos", "servicios", "reseñas", "eventos"):
        assert cosa in html


def test_el_buscador_de_moderacion_filtra_por_titulo_y_por_autor(
    client, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    una = crear_usuario(username="panaderia.sur")
    otra = crear_usuario(username="tallerbarro")
    crear_post(una.id, title="Panadería La Espiga")
    crear_post(otra.id, title="Taller El Barro")

    login(admin.id)

    por_titulo = client.get("/admin/emprendimientos?q=Espiga").get_data(as_text=True)
    assert "Panadería La Espiga" in por_titulo
    assert "Taller El Barro" not in por_titulo

    por_autor = client.get("/admin/emprendimientos?q=tallerbarro").get_data(as_text=True)
    assert "Taller El Barro" in por_autor
    assert "Panadería La Espiga" not in por_autor


def test_el_filtro_por_categoria_de_moderacion_recorta(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    comida = crear_post(autor.id, title="Panadería")
    crear_post(autor.id, title="Reparo PC")
    comida.category = Categorias.ALIMENTOS
    db.session.commit()

    login(admin.id)
    html = client.get(
        f"/admin/emprendimientos?categoria={Categorias.ALIMENTOS}"
    ).get_data(as_text=True)

    assert "Panadería" in html
    assert "Reparo PC" not in html


def test_una_categoria_inventada_no_rompe_la_moderacion(
    client, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    crear_post(autor.id, title="Panadería")

    login(admin.id)
    resp = client.get("/admin/emprendimientos?categoria=marcianos")

    assert resp.status_code == 200
    assert "Panadería" in resp.get_data(as_text=True)


def test_la_moderacion_no_consulta_de_mas_por_cada_fila(
    app, client, db, crear_usuario, crear_post, login
):
    """El costo no puede depender de cuantos emprendimientos hay en la pagina.

    Los conteos de reportes y reseñas por fila salen de subconsultas agrupadas.
    Si se resolvieran con un COUNT por fila, la pagina crecería dos consultas
    por emprendimiento -- el mismo N+1 que ya se corrigio en "Mis
    emprendimientos".
    """
    from sqlalchemy import event

    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    login(admin.id)

    def contar_consultas():
        consultas = []

        def escuchar(conn, cursor, statement, params, context, many):
            consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", escuchar)
        try:
            client.get("/admin/emprendimientos")
        finally:
            event.remove(db.engine, "before_cursor_execute", escuchar)
        return len(consultas)

    for numero in range(3):
        crear_post(autor.id, title=f"Emprendimiento {numero}")
    con_tres = contar_consultas()

    for numero in range(3, 9):
        crear_post(autor.id, title=f"Emprendimiento {numero}")
    con_nueve = contar_consultas()

    assert con_nueve == con_tres
def test_un_titulo_con_comilla_no_se_escapa_del_confirm(
    client, crear_usuario, crear_post, login
):
    """Un titulo con comilla simple no puede terminar siendo codigo JS.

    Esto era un XSS almacenado. El confirm de borrado se armaba dentro de un
    onsubmit="return confirm('... «{{ post.title }}» ...')", y ahi el escape de
    Jinja no alcanza: convierte la comilla a &#39;, pero el parser HTML
    decodifica las entidades del atributo ANTES de compilar el handler, asi que
    la comilla reaparecia del lado de JS y cerraba el string. Un emprendimiento
    llamado  X' + (codigo) + '  ejecutaba ese codigo en la sesion del admin que
    apretaba Eliminar.

    Ahora el texto viaja en data-confirm, que nunca se compila como JS, y el
    confirm lo arma el listener delegado de main.js. El test fija las dos
    mitades: que el dato no vuelva a un atributo de evento, y que dentro de
    data-confirm la comilla quede escapada.
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    payload = "X' + (window.__pwned = 1) + '"
    crear_post(autor.id, title=payload)

    login(admin.id)
    html = client.get("/admin/emprendimientos").get_data(as_text=True)

    # El titulo llega a la pagina (si no, el test pasaria por no probar nada).
    assert "window.__pwned" in html

    # No quedan atributos de evento inline donde el payload pudiera compilarse.
    assert "onsubmit=" not in html
    assert "onclick=" not in html

    # Y en data-confirm la comilla esta escapada, asi que no corta el atributo.
    assert payload not in html
    assert "X&#39; + (window.__pwned = 1) + &#39;" in html


def test_una_pagina_fuera_de_rango_deja_volver(client, crear_usuario, login):
    """?page=999 tiene que seguir mostrando por donde salir.

    Las vistas paginan con error_out=False, asi que una pagina inexistente no
    da 404: devuelve la lista vacia. La paginacion estaba adentro del
    {% if paginacion.items %}, asi que desaparecia justo cuando es lo unico
    que sirve para volver, y encima quedaba el cartel de "no hay usuarios",
    que es falso.

    "Anterior" tiene que apuntar a la ultima pagina real (2), no a page - 1
    (998), que estaria igual de vacia.
    """
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    for numero in range(25):  # 25 + la admin = 26 usuarios, 20 por pagina => 2
        crear_usuario(username=f"usuario{numero:02d}")

    login(admin.id)
    html = client.get("/admin/usuarios?page=999").get_data(as_text=True)

    assert 'class="pagination"' in html
    assert "/admin/usuarios?page=2" in html
    assert "/admin/usuarios?page=998" not in html
