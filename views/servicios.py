"""Servicios de los emprendimientos: el ABM del prestador.

El ABM vive aca y no en views/blog.py por lo mismo que el de productos y el de
eventos: es su propia entidad, con su propio formulario y su propio panel.

El archivo se llama servicios.py y no services.py a proposito: `services` ya es
el paquete de servicios de dominio del proyecto (services/precios.py,
services/uploads.py), y un modulo de vistas con ese nombre, que ademas importa
de ese paquete, se lee como si fuera lo mismo. El modelo si es models/Service,
que es la convencion de los modelos.

Un servicio pertenece a un emprendimiento (Post), no a un usuario, asi que el
permiso siempre se resuelve mirando el dueño de ese emprendimiento. El chequeo
va en la vista y no solo en el template: esconder un boton no es un permiso,
cualquiera puede mandar el POST a mano.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.orm import joinedload

from db import db
from models.post import Post
from models.service import MAX_SERVICIOS_POR_POST, Rubros, Service
from services.precios import parsear_precio, texto_para_formulario
from views.auth import login_required

servicios = Blueprint("servicios", __name__, url_prefix="/servicios")


def _servicio_propio(id):
    """El servicio con ese id si es de un emprendimiento del usuario actual.

    Devuelve (servicio, None) si puede tocarlo, o (None, respuesta) con el
    redirect ya armado si no. Mismo criterio que products._producto_propio:
    flash y vuelta al panel, no un 403 crudo.
    """
    servicio = Service.query.get_or_404(id)
    if servicio.post.author != g.user.id:
        flash("No tenés permiso para modificar este servicio.")
        return None, redirect(url_for("servicios.index"))
    return servicio, None


def _mis_emprendimientos():
    return Post.query.filter_by(author=g.user.id).order_by(Post.title).all()


def _leer_formulario():
    """Los campos del servicio tal como los mando el usuario, ya parseados.

    La validacion es a mano (con flash y una variable `error`) porque asi
    valida todo el proyecto: Flask-WTF esta instalado pero solo se usa para el
    CSRF.
    """
    titulo = (request.form.get("titulo") or "").strip()
    rubro = (request.form.get("rubro") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    zona = (request.form.get("zona_cobertura") or "").strip()
    precio_texto = (request.form.get("precio_estimado") or "").strip()
    # Un checkbox que no se marca directamente no viaja en el POST.
    disponible = request.form.get("disponible") is not None

    # obligatorio=False: un servicio sin precio es "a presupuestar", que es un
    # caso valido y no un formulario incompleto.
    precio, error_precio = parsear_precio(precio_texto, obligatorio=False)

    error = None
    if not titulo:
        error = "Se requiere un título para el servicio."
    elif rubro not in Rubros.TODOS:
        # El rubro llega de un <select>, pero se valida igual: el POST se puede
        # mandar a mano con cualquier cosa, y un rubro invalido dejaria la fila
        # fuera de la busqueda por rubro sin que nadie se entere.
        error = "Elegí uno de los rubros de la lista."
    elif error_precio:
        error = error_precio

    # Se devuelve el texto crudo del precio y no el Decimal: si estaba mal
    # escrito, el formulario tiene que volver con lo que puso el usuario.
    datos = {
        "titulo": titulo, "rubro": rubro, "descripcion": descripcion,
        "zona_cobertura": zona, "precio_estimado": precio_texto,
        "disponible": disponible,
    }
    return datos, titulo, rubro, descripcion, zona, precio, disponible, error


@servicios.route("/")
@login_required
def index():
    """El panel: todos los servicios de los emprendimientos propios.

    joinedload trae el emprendimiento en la misma consulta, para no disparar un
    SELECT por servicio al mostrar de cual es (el mismo N+1 que el panel de
    productos).
    """
    lista = (
        Service.query
        .join(Post, Post.id == Service.post_id)
        .options(joinedload(Service.post))
        .filter(Post.author == g.user.id)
        .order_by(Post.title, Service.titulo)
        .all()
    )
    return render_template(
        "servicios/index.html",
        servicios=lista,
        posts=_mis_emprendimientos(),
        maximo=MAX_SERVICIOS_POR_POST,
        rubros=Rubros,
    )


@servicios.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Cargar un servicio en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder cargar servicios.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, titulo, rubro, descripcion, zona, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un servicio del emprendimiento de
        # otro mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error is None and _cuantos_tiene(post_id) >= MAX_SERVICIOS_POR_POST:
            error = (
                f"Ese emprendimiento ya tiene {MAX_SERVICIOS_POR_POST} servicios, "
                "que es el máximo. Borrá alguno para cargar uno nuevo."
            )

        if error:
            flash(error)
            return render_template(
                "servicios/form.html", posts=posts, datos=datos,
                servicio=None, rubros=Rubros,
            )

        db.session.add(Service(
            post_id=post_id, titulo=titulo, rubro=rubro,
            descripcion=descripcion or None, zona_cobertura=zona or None,
            precio_estimado=precio, disponible=disponible,
        ))
        db.session.commit()
        flash("Servicio agregado correctamente.")
        return redirect(url_for("servicios.index"))

    datos = {
        "titulo": "", "rubro": Rubros.OTROS, "descripcion": "",
        "zona_cobertura": "", "precio_estimado": "",
        "disponible": True, "post_id": None,
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=None, rubros=Rubros
    )


@servicios.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un servicio propio."""
    servicio, rechazo = _servicio_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        datos, titulo, rubro, descripcion, zona, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        # El tope solo aplica si el servicio se esta MUDANDO a otro
        # emprendimiento: si se queda donde estaba, ya esta contado.
        if (
            error is None
            and post_id != servicio.post_id
            and _cuantos_tiene(post_id) >= MAX_SERVICIOS_POR_POST
        ):
            error = (
                f"Ese emprendimiento ya tiene {MAX_SERVICIOS_POR_POST} servicios, "
                "que es el máximo."
            )

        if error:
            flash(error)
            return render_template(
                "servicios/form.html", posts=posts, datos=datos,
                servicio=servicio, rubros=Rubros,
            )

        servicio.post_id = post_id
        servicio.titulo = titulo
        servicio.rubro = rubro
        servicio.descripcion = descripcion or None
        servicio.zona_cobertura = zona or None
        servicio.precio_estimado = precio
        servicio.disponible = disponible
        db.session.commit()

        flash("Servicio actualizado correctamente.")
        return redirect(url_for("servicios.index"))

    datos = {
        "titulo": servicio.titulo,
        "rubro": servicio.rubro,
        "descripcion": servicio.descripcion or "",
        "zona_cobertura": servicio.zona_cobertura or "",
        "precio_estimado": texto_para_formulario(servicio.precio_estimado),
        "disponible": servicio.disponible,
        "post_id": servicio.post_id,
    }
    return render_template(
        "servicios/form.html", posts=posts, datos=datos, servicio=servicio, rubros=Rubros
    )


@servicios.route("/<int:id>/eliminar", methods=("POST",))
@login_required
def eliminar(id):
    """Eliminar un servicio propio.

    Solo POST, con la misma razon que blog.delete y products.eliminar: un GET
    no debe tener efectos secundarios (lo puede disparar un prefetch del
    navegador o un crawler).
    """
    servicio, rechazo = _servicio_propio(id)
    if rechazo:
        return rechazo

    db.session.delete(servicio)
    db.session.commit()

    flash("Servicio eliminado correctamente.")
    return redirect(url_for("servicios.index"))


def _cuantos_tiene(post_id):
    """Cuantos servicios tiene ya ese emprendimiento.

    Un COUNT y no len(post.servicios): trae un numero en vez de todas las
    filas solo para contarlas.
    """
    return Service.query.filter_by(post_id=post_id).count()
