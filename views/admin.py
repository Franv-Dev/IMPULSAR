"""Panel de administrador: usuarios, moderacion de emprendimientos y metricas.

Vista simple pensada para el rol admin: no hay nada de esto en la API JSON,
solo paginas HTML protegidas con @admin_required (ver views/auth.py).
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from db import db, utcnow
from app.blog.modelo_post import Post
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


@admin.route("/")
@admin_required
def dashboard():
    """Metricas basicas de la plataforma."""
    metricas = {
        "usuarios": db.session.query(func.count(User.id)).scalar() or 0,
        "posts": db.session.query(func.count(Post.id)).scalar() or 0,
        "resenias": db.session.query(func.count(Review.id)).scalar() or 0,
        "reportes_pendientes": (
            db.session.query(func.count(Report.id)).filter(Report.resolved.is_(False)).scalar() or 0
        ),
        "verificaciones_pendientes": (
            consultas_servicios.cuantas_verificaciones_pendientes()
        ),
    }
    return render_template("admin/dashboard.html", metricas=metricas)


@admin.route("/usuarios")
@admin_required
def usuarios():
    """Listado de usuarios, con accion para banear/desbanear."""
    lista = User.query.order_by(User.username.asc()).all()
    return render_template("admin/usuarios.html", usuarios=lista, Roles=Roles)


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


@admin.route("/emprendimientos")
@admin_required
def emprendimientos():
    """Listado de todos los emprendimientos, para moderacion."""
    paginacion = (
        Post.query
        .order_by(Post.created.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=20,
            error_out=False,
        )
    )
    return render_template("admin/emprendimientos.html", paginacion=paginacion)


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
