"""Panel de administrador: usuarios, moderacion de emprendimientos y metricas.

Vista simple pensada para el rol admin: no hay nada de esto en la API JSON,
solo paginas HTML protegidas con @admin_required (ver views/auth.py).
"""

from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
import sqlalchemy as sa
from sqlalchemy import func

from db import db, utcnow
from app.blog.modelo_post import Categorias, Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
# Las verificaciones son del dominio de servicios: las consultas salen de su
# capa (app/servicios/consultas.py) y no se arman aca, aunque el resto de este
# modulo todavia hable con db.session directo. Lo que si se escribe aca es la
# decision, que es lo unico de este flujo que le toca al admin.
from app.servicios import consultas as consultas_servicios
from app.servicios.modelo_verificacion import EstadosVerificacion
from models.user import Roles, User
from views.auth import admin_required

admin = Blueprint("admin", __name__, url_prefix="/admin")


# La ventana de los "ultimos 30 dias" de las metricas del panel.
DIAS_DE_LA_VENTANA = 30

# Cuantos elementos de cada cola se muestran en el resumen. El panel es para
# ver de un vistazo que hay pendiente, no para atender todo desde ahi: cada
# cola tiene su pantalla, con la lista entera.
COLA_EN_EL_RESUMEN = 3


@admin.context_processor
def _badges_del_menu():
    """Los pendientes de cada cola, para el menu lateral del panel.

    Va como context processor del blueprint y no como argumento de cada vista
    porque el menu esta en las cinco pantallas: pasarlo a mano seria repetir lo
    mismo cinco veces y olvidarselo en la sexta. Solo corre para las plantillas
    que renderiza este blueprint.

    Son dos COUNT por pagina del panel. Es el precio de que los numeros del
    menu sean los de ahora y no los de cuando se cargo otra pantalla.
    """
    return {
        "badge_reportes": (
            db.session.query(func.count(Report.id))
            .filter(Report.resolved.is_(False))
            .scalar() or 0
        ),
        "badge_verificaciones": consultas_servicios.cuantas_verificaciones_pendientes(),
    }


def _cuantos(modelo, columna_fecha):
    """(total, altas en la ventana) para un modelo con fecha de creacion.

    Los dos son COUNT con WHERE, no una serie temporal: no hace falta una tabla
    de historico para responder "cuantos se sumaron este mes", alcanza con la
    fecha de alta que las filas ya tienen.
    """
    desde = utcnow() - timedelta(days=DIAS_DE_LA_VENTANA)
    total = db.session.query(func.count(modelo.id)).scalar() or 0
    nuevos = (
        db.session.query(func.count(modelo.id))
        .filter(columna_fecha >= desde)
        .scalar() or 0
    )
    return total, nuevos


@admin.route("/")
@admin_required
def dashboard():
    """Las colas pendientes primero, y abajo las metricas de la plataforma.

    Las tres metricas llevan su delta de los ultimos 30 dias porque los tres
    modelos guardan cuando se creo cada fila (User.created_at, Post.created,
    Review.created). No hay un cuarto tile de "emprendimientos sin actividad":
    "actividad" no esta definida en el modelo -- Post no tiene updated_at, y
    habria que elegir entre su ultimo evento, su ultimo producto o su ultima
    resenia -- asi que seria una metrica inventada.

    Las dos colas se muestran recortadas (COLA_EN_EL_RESUMEN) y con las
    acciones que ya existen, que son las mismas de sus pantallas propias. El
    link "Ver todos" lleva a la lista entera.
    """
    usuarios_total, usuarios_nuevos = _cuantos(User, User.created_at)
    posts_total, posts_nuevos = _cuantos(Post, Post.created)
    resenias_total, resenias_nuevas = _cuantos(Review, Review.created)

    reportes_pendientes = (
        db.session.query(func.count(Report.id)).filter(Report.resolved.is_(False)).scalar() or 0
    )
    verificaciones_pendientes = consultas_servicios.cuantas_verificaciones_pendientes()

    metricas = {
        "usuarios": usuarios_total,
        "posts": posts_total,
        "resenias": resenias_total,
        "usuarios_nuevos": usuarios_nuevos,
        "posts_nuevos": posts_nuevos,
        "resenias_nuevas": resenias_nuevas,
        "reportes_pendientes": reportes_pendientes,
        "verificaciones_pendientes": verificaciones_pendientes,
    }

    return render_template(
        "admin/dashboard.html",
        metricas=metricas,
        dias_ventana=DIAS_DE_LA_VENTANA,
        pendientes=reportes_pendientes + verificaciones_pendientes,
        reportes=(
            Report.query
            .filter_by(resolved=False)
            .order_by(Report.created.desc())
            .limit(COLA_EN_EL_RESUMEN)
            .all()
        ),
        # El slice es en memoria y no un LIMIT: verificaciones_pendientes()
        # devuelve la lista entera, que es lo que ya hace la pantalla de la
        # cola y por el mismo motivo (esa cola no deberia crecer).
        verificaciones=(
            consultas_servicios.verificaciones_pendientes()[:COLA_EN_EL_RESUMEN]
        ),
    )


# Los filtros de la pantalla de usuarios. La clave es lo que viaja en ?filtro=
# y el valor, como se recorta la consulta. "baneados" no es un rol: es un
# estado, y por eso no sale de Roles.
FILTROS_DE_USUARIO = {
    "todos": ("Todos", None),
    "emprendedores": ("Emprendedores", Roles.EMPRENDEDOR),
    "usuarios": ("Usuarios", Roles.USUARIO),
    "administradores": ("Administradores", Roles.ADMIN),
    "baneados": ("Baneados", None),
}


def _conteos_de_usuarios():
    """Cuantos usuarios cae en cada filtro, para los chips de la pantalla.

    Un GROUP BY y no un COUNT por chip: cinco consultas para cinco numeros de
    la misma tabla es justamente el N+1 que ya se corrigio en otras pantallas.
    Los baneados van aparte porque son un estado y no un rol, asi que no salen
    del mismo agrupado.
    """
    por_rol = dict(
        db.session.query(User.rol, func.count(User.id)).group_by(User.rol).all()
    )
    baneados = (
        db.session.query(func.count(User.id)).filter(User.is_banned.is_(True)).scalar() or 0
    )
    return {
        "todos": sum(por_rol.values()),
        "emprendedores": por_rol.get(Roles.EMPRENDEDOR, 0),
        "usuarios": por_rol.get(Roles.USUARIO, 0),
        "administradores": por_rol.get(Roles.ADMIN, 0),
        "baneados": baneados,
    }


@admin.route("/usuarios")
@admin_required
def usuarios():
    """Listado de usuarios, con buscador, filtros y accion de banear/desbanear.

    Pagina, a diferencia de antes: la version anterior hacia .all() y traia la
    tabla entera a memoria y al HTML. Con una plataforma chica eso no se nota;
    con mil usuarios es toda la base en cada carga del panel.

    El buscador y los filtros son de verdad y no adorno: si la pantalla los
    muestra, tienen que recortar la consulta. Los dos se combinan (se puede
    buscar dentro de un rol) y los dos viajan en la URL, asi que la paginacion
    los conserva.
    """
    filtro = request.args.get("filtro", "todos")
    if filtro not in FILTROS_DE_USUARIO:
        filtro = "todos"
    busqueda = (request.args.get("q") or "").strip()

    query = User.query

    if filtro == "baneados":
        query = query.filter(User.is_banned.is_(True))
    else:
        _etiqueta, rol = FILTROS_DE_USUARIO[filtro]
        if rol is not None:
            query = query.filter(User.rol == rol)

    if busqueda:
        # Por nombre o por mail, que son los dos datos con los que un admin
        # llega a un usuario cuando alguien le reporta algo.
        patron = f"%{busqueda}%"
        query = query.filter(
            db.or_(User.username.ilike(patron), User.email.ilike(patron))
        )

    paginacion = query.order_by(User.username.asc()).paginate(
        page=request.args.get("page", 1, type=int),
        per_page=20,
        error_out=False,
    )

    return render_template(
        "admin/usuarios.html",
        paginacion=paginacion,
        conteos=_conteos_de_usuarios(),
        filtros=FILTROS_DE_USUARIO,
        filtro_actual=filtro,
        busqueda=busqueda,
        Roles=Roles,
    )


@admin.route("/usuarios/<int:user_id>/ban", methods=["POST"])
@admin_required
def toggle_ban(user_id):
    """Banea o desbanea (toggle) a un usuario. No se puede banear a otro admin."""
    usuario = User.query.get_or_404(user_id)

    if usuario.rol == Roles.ADMIN:
        flash("No podés banear a otro administrador.")
        return redirect(url_for("admin.usuarios"))

    usuario.is_banned = not usuario.is_banned
    db.session.commit()
    flash(f"{'Baneado' if usuario.is_banned else 'Desbaneado'}: {usuario.username}.")
    return redirect(url_for("admin.usuarios"))


def _conteos_de_la_pagina(ids):
    """Reportes sin resolver y reseñas de cada emprendimiento de esta pagina.

    Dos consultas AGRUPADAS acotadas a los ids que se van a dibujar, no un
    COUNT por fila: contar dentro del for serian dos consultas por
    emprendimiento, que es el mismo N+1 que ya se corrigio en "Mis
    emprendimientos". Asi la pagina cuesta lo mismo con 3 filas que con 20.

    Devuelve un dict por id con los dos numeros ya en cero cuando no hay nada,
    para que la plantilla no tenga que preguntar.
    """
    if not ids:
        return {}

    reportes = dict(
        db.session.query(Report.post_id, func.count(Report.id))
        .filter(
            Report.resolved.is_(False),
            Report.post_id.in_(ids),
        )
        .group_by(Report.post_id)
        .all()
    )
    resenias = dict(
        db.session.query(Review.post_id, func.count(Review.id))
        .filter(Review.post_id.in_(ids))
        .group_by(Review.post_id)
        .all()
    )

    return {
        id_: {"reportes": reportes.get(id_, 0), "resenias": resenias.get(id_, 0)}
        for id_ in ids
    }


@admin.route("/emprendimientos")
@admin_required
def emprendimientos():
    """Listado de emprendimientos para moderacion, los reportados primero.

    Cada fila muestra cuantos reportes sin resolver tiene y cuantas reseñas
    recibio. Los dos numeros salen de subconsultas AGRUPADAS que se unen a la
    consulta principal, no de un COUNT por fila: contar dentro del for seria
    dos consultas por emprendimiento, que es el mismo N+1 que ya se corrigio
    en "Mis emprendimientos".

    Que los reportados salgan primero es la razon de que el conteo entre en la
    consulta y no se resuelva despues sobre la pagina ya paginada: para poder
    ordenar por el, el motor tiene que conocerlo antes del LIMIT.

    Se usa db.paginate() sobre un select() y no Post.query.paginate() porque
    la consulta tiene que unirse a la subconsulta de reportes para poder
    ORDENAR por ella: sin eso, "los reportados primero" solo valdria dentro de
    la pagina que ya toco, no sobre el listado entero.
    """
    reportes_por_post = (
        sa.select(Report.post_id, func.count(Report.id).label("total"))
        .where(Report.resolved.is_(False), Report.post_id.isnot(None))
        .group_by(Report.post_id)
        .subquery()
    )

    # coalesce porque el LEFT JOIN devuelve NULL para el emprendimiento que no
    # tiene ninguno, y a la hora de ordenar eso es un cero.
    reportes = func.coalesce(reportes_por_post.c.total, 0)

    consulta = (
        sa.select(Post)
        .outerjoin(reportes_por_post, reportes_por_post.c.post_id == Post.id)
    )

    busqueda = (request.args.get("q") or "").strip()
    if busqueda:
        # Por titulo o por autor: son las dos formas de llegar a un
        # emprendimiento cuando alguien lo reporta por afuera del panel.
        patron = f"%{busqueda}%"
        consulta = consulta.join(User, User.id == Post.author).where(
            db.or_(Post.title.ilike(patron), User.username.ilike(patron))
        )

    categoria = request.args.get("categoria") or ""
    if categoria in Categorias.TODAS:
        consulta = consulta.where(Post.category == categoria)
    else:
        categoria = ""

    paginacion = db.paginate(
        consulta.order_by(reportes.desc(), Post.created.desc()),
        page=request.args.get("page", 1, type=int),
        per_page=20,
        error_out=False,
    )

    return render_template(
        "admin/emprendimientos.html",
        paginacion=paginacion,
        conteos=_conteos_de_la_pagina([post.id for post in paginacion.items]),
        busqueda=busqueda,
        categoria_actual=categoria,
        categorias=Categorias.ETIQUETAS,
    )


@admin.route("/emprendimientos/<int:post_id>/eliminar", methods=["POST"])
@admin_required
def delete_post(post_id):
    """Eliminar cualquier emprendimiento (moderacion), sin importar el dueño."""
    post = Post.query.get_or_404(post_id)
    titulo = post.title

    try:
        db.session.delete(post)
        db.session.commit()
        flash(f"Se eliminó el emprendimiento «{titulo}».")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al eliminar el post %s desde el panel de admin", post_id)
        flash("Error al eliminar el emprendimiento.")

    return redirect(url_for("admin.emprendimientos"))


@admin.route("/resenias/<int:review_id>/eliminar", methods=["POST"])
@admin_required
def delete_review(review_id):
    """Eliminar cualquier resenia (moderacion), sin importar quien la escribio.

    Hasta ahora el unico borrado de resenia era blog.delete_review, que exige
    ser SU autor (reglas.es_el_autor_de_la_resenia). O sea que un reporte de
    tipo "Resena" se podia marcar resuelto pero no se podia actuar sobre el:
    la unica salida era borrar el emprendimiento entero, que es de otro.

    Es el espejo de delete_post y por eso repite su forma, incluido el
    try/except: un borrado que falla tiene que dejar la sesion limpia y
    avisar, no tumbar el panel.

    El reporte no se marca resuelto a mano: reports.review_id es ON DELETE
    CASCADE, asi que se va con la resenia y sale solo de la cola. Igual que
    cuando se borra un emprendimiento reportado.
    """
    review = Review.query.get_or_404(review_id)
    autor = review.user.username if review.user else "usuario borrado"

    try:
        db.session.delete(review)
        db.session.commit()
        flash(f"Se eliminó la reseña de «{autor}».")
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Error al eliminar la resenia %s desde el panel de admin", review_id
        )
        flash("Error al eliminar la reseña.")

    return redirect(url_for("admin.reportes"))


@admin.route("/reportes")
@admin_required
def reportes():
    """Reportes pendientes de emprendimientos y reseñas, mas nuevos primero."""
    pendientes = (
        Report.query
        .filter_by(resolved=False)
        .order_by(Report.created.desc())
        .all()
    )
    return render_template("admin/reportes.html", reportes=pendientes)


@admin.route("/reportes/<int:report_id>/resolver", methods=["POST"])
@admin_required
def resolve_report(report_id):
    """Marca un reporte como resuelto. No borra el contenido reportado: para
    eso esta la eliminacion en admin.emprendimientos()."""
    reporte = Report.query.get_or_404(report_id)
    reporte.resolved = True
    reporte.resolved_at = utcnow()
    db.session.commit()
    flash("Reporte marcado como resuelto.")
    return redirect(url_for("admin.reportes"))


@admin.route("/verificaciones")
@admin_required
def verificaciones():
    """Pedidos de verificacion de credenciales sin revisar.

    Mismo shape que reportes(): una lista, sin paginar, porque la cola de lo
    que falta atender no deberia crecer. Lo que si cambia es el orden, mas
    viejos primero (ver consultas.verificaciones_pendientes): del otro lado hay
    alguien esperando desde que lo mando.
    """
    return render_template(
        "admin/verificaciones.html",
        verificaciones=consultas_servicios.verificaciones_pendientes(),
    )


@admin.route("/verificaciones/<int:verificacion_id>/aprobar", methods=["POST"])
@admin_required
def aprobar_verificacion(verificacion_id):
    """Aprueba el pedido y marca el servicio como verificado.

    Este es el unico lugar del proyecto que escribe Service.verificado, y es a
    proposito: si el dueño del servicio pudiera marcarlo, el sello no
    significaria nada (ver el comentario de la columna en
    app/servicios/modelo.py).
    """
    verificacion = consultas_servicios.verificacion_por_id_o_404(verificacion_id)

    if verificacion.estado != EstadosVerificacion.PENDIENTE:
        # Ya la resolvio alguien: puede ser el otro admin, o esta misma pestaña
        # abierta dos veces. No se vuelve a tocar la fila.
        flash("Ese pedido de verificación ya estaba resuelto.")
        return redirect(url_for("admin.verificaciones"))

    verificacion.estado = EstadosVerificacion.APROBADA
    verificacion.resuelto_at = utcnow()
    verificacion.servicio.verificado = True
    db.session.commit()

    flash(f"Servicio «{verificacion.servicio.titulo}» verificado.")
    return redirect(url_for("admin.verificaciones"))


@admin.route("/verificaciones/<int:verificacion_id>/rechazar", methods=["POST"])
@admin_required
def rechazar_verificacion(verificacion_id):
    """Rechaza el pedido, con el motivo si el admin lo escribio.

    NO toca Service.verificado, ni para ponerlo en False: queda como estaba. La
    unica cosa que este flujo puede hacer es agregar el sello, nunca sacarlo,
    porque un rechazo puede ser "la foto salio movida" y no "este tipo no tiene
    matricula". Sacar un sello ya puesto seria otra accion, con otro boton y
    otra decision.

    El motivo viaja en el mismo POST que el rechazo, en un textarea al lado del
    boton: pedirlo en una pantalla aparte agrega un paso a lo unico que el
    prestador necesita para poder corregir y volver a mandarlo.
    """
    verificacion = consultas_servicios.verificacion_por_id_o_404(verificacion_id)

    if verificacion.estado != EstadosVerificacion.PENDIENTE:
        flash("Ese pedido de verificación ya estaba resuelto.")
        return redirect(url_for("admin.verificaciones"))

    motivo = (request.form.get("motivo_rechazo") or "").strip()

    verificacion.estado = EstadosVerificacion.RECHAZADA
    verificacion.resuelto_at = utcnow()
    # None y no "" cuando el admin no escribio nada: la columna es nullable
    # justamente para distinguir "no dijo por que" de un motivo vacio.
    verificacion.motivo_rechazo = motivo or None
    db.session.commit()

    flash("Pedido de verificación rechazado.")
    return redirect(url_for("admin.verificaciones"))
