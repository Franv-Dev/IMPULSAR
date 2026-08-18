"""Eventos y ferias de los emprendimientos.

El ABM vive aca junto con la cartelera publica en vez de colgar del blog porque
/eventos es una ruta de primer nivel: partirlo dejaria la cartelera en un
archivo y el alta en otro sin ninguna ganancia.

Un evento pertenece a un emprendimiento (Post), no a un usuario, asi que el
permiso se resuelve mirando el dueño de ese emprendimiento.
"""

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.orm import joinedload

from db import db
from models.event import Event
from app.blog.modelo_post import Post
from services.eventos import parsear_fecha, proximos
from services.horarios import formatear as formatear_hora, parsear_hora
from views.auth import login_required

eventos = Blueprint("eventos", __name__, url_prefix="/eventos")


@eventos.route("/")
def index():
    """Cartelera publica: los proximos eventos de todos los emprendimientos.

    Paginada con el mismo criterio que blog.index: traer todo con .all() se
    rompe solo cuando la cartelera crece. El joinedload trae el emprendimiento
    en la misma consulta (y con el su autor, que ya es lazy="joined"), para no
    disparar un SELECT por evento al armar el link al perfil (problema N+1).
    """
    paginacion = (
        proximos(Event.query.options(joinedload(Event.post)))
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["POSTS_POR_PAGINA"],
            error_out=False,
        )
    )
    return render_template("eventos/index.html", paginacion=paginacion)


def _evento_propio(id):
    """El evento con ese id si es de un emprendimiento del usuario actual.

    Devuelve (evento, None) si puede tocarlo, o (None, respuesta) con el
    redirect ya armado si no. Mismo criterio que blog.update/blog.delete: flash
    y vuelta a "mis emprendimientos", no un 403 crudo.
    """
    evento = Event.query.get_or_404(id)
    if evento.post.author != g.user.id:
        flash("No tenés permiso para modificar este evento.")
        return None, redirect(url_for("blog.my_posts"))
    return evento, None


def _mis_emprendimientos():
    return Post.query.filter_by(author=g.user.id).order_by(Post.title).all()


def _leer_formulario():
    """Los campos del evento tal como los mando el usuario, ya parseados.

    La validacion es a mano (con flash y una variable `error`) porque asi valida
    todo el proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
    """
    titulo = (request.form.get("titulo") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    fecha_texto = (request.form.get("fecha") or "").strip()
    hora_texto = (request.form.get("hora") or "").strip()

    fecha = parsear_fecha(fecha_texto)
    hora = parsear_hora(hora_texto)

    error = None
    if not titulo:
        error = "Se requiere un título para el evento."
    elif not fecha_texto:
        error = "Se requiere una fecha."
    elif fecha is None:
        error = "La fecha no es válida."
    elif hora_texto and hora is None:
        error = "La hora no es válida. Usá el formato HH:MM."

    # Se devuelve lo que escribio el usuario (los textos crudos) y no lo
    # parseado: si la fecha estaba mal, el formulario tiene que volver con lo
    # que puso, no vacio.
    datos = {
        "titulo": titulo, "descripcion": descripcion,
        "fecha": fecha_texto, "hora": hora_texto,
    }
    return datos, titulo, descripcion, fecha, hora, error


@eventos.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Publicar un evento en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder publicar eventos.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, titulo, descripcion, fecha, hora, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un evento del emprendimiento de otro
        # mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error:
            flash(error)
            return render_template(
                "eventos/form.html", posts=posts, datos=datos, evento=None
            )

        db.session.add(Event(
            post_id=post_id, titulo=titulo,
            descripcion=descripcion or None, fecha=fecha, hora=hora,
        ))
        db.session.commit()
        flash("Evento publicado correctamente.")
        return redirect(url_for("profile.view_profile", slug=g.user.slug))

    datos = {"titulo": "", "descripcion": "", "fecha": "", "hora": "", "post_id": None}
    return render_template("eventos/form.html", posts=posts, datos=datos, evento=None)


@eventos.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un evento propio."""
    evento, rechazo = _evento_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        datos, titulo, descripcion, fecha, hora, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error:
            flash(error)
            return render_template(
                "eventos/form.html", posts=posts, datos=datos, evento=evento
            )

        evento.post_id = post_id
        evento.titulo = titulo
        evento.descripcion = descripcion or None
        evento.fecha = fecha
        evento.hora = hora
        db.session.commit()
        flash("Evento actualizado correctamente.")
        return redirect(url_for("profile.view_profile", slug=g.user.slug))

    datos = {
        "titulo": evento.titulo,
        "descripcion": evento.descripcion or "",
        "fecha": evento.fecha.isoformat(),
        "hora": formatear_hora(evento.hora),
        "post_id": evento.post_id,
    }
    return render_template("eventos/form.html", posts=posts, datos=datos, evento=evento)


@eventos.route("/<int:id>/eliminar", methods=("POST",))
@login_required
def eliminar(id):
    """Eliminar un evento propio.

    Solo POST, con la misma razon que blog.delete: un GET no debe tener efectos
    secundarios (lo puede disparar un prefetch del navegador o un crawler).
    """
    evento, rechazo = _evento_propio(id)
    if rechazo:
        return rechazo

    db.session.delete(evento)
    db.session.commit()
    flash("Evento eliminado correctamente.")
    return redirect(url_for("profile.view_profile", slug=g.user.slug))
