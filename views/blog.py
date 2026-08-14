from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort
from models.favorite import Favorite
from models.post import Categorias, Post
from models.report import Report
from models.user import User
from views.auth import login_required
from db import db, utcnow
import os
from models.review import Review
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from services.geocoding import get_coordinates_from_address
from services.ratings import query_posts_con_rating, serializar_con_rating
from services.uploads import ALLOWED_EXTENSIONS, allowed_file, save_post_image

blog = Blueprint("blog", __name__, url_prefix="/blog")

# Utilidades

def get_user(id):
    """Obtener usuario por ID o devolver 404."""
    return User.query.get_or_404(id)

def get_post(id, check_author=True):
    """Obtener post por ID y validar autor si corresponde."""
    post = Post.query.get(id)
    if post is None:
        abort(404, f"id {id} de la publicación no existe.")
    if check_author and post.author != g.user.id:
        flash("No tenés permiso para acceder a este emprendimiento.")
        return redirect(url_for("blog.my_posts"))
    return post

def _ids_favoritos(user_id):
    """IDs de los posts que el usuario marco como favoritos, en una sola consulta."""
    filas = db.session.query(Favorite.post_id).filter_by(user_id=user_id).all()
    return {post_id for (post_id,) in filas}


def _distancia_km(lat, lon):
    """Expresion SQL: distancia en km entre (lat, lon) y cada Post.

    Formula del semiverseno resuelta con funciones matematicas de MySQL, para
    que el ORDER BY y la paginacion los siga resolviendo la base de datos en
    vez de traer todos los posts a Python para ordenarlos ahi.
    """
    argumento = (
        func.cos(func.radians(lat)) * func.cos(func.radians(Post.latitude)) *
        func.cos(func.radians(Post.longitude) - func.radians(lon)) +
        func.sin(func.radians(lat)) * func.sin(func.radians(Post.latitude))
    )
    # Buscar cerca de un post con las mismas coordenadas puede dar, por
    # redondeo de punto flotante, un argumento apenas fuera de [-1, 1]; ACOS()
    # de eso es NULL. Se acota con CASE (no LEAST/GREATEST: no existen en
    # SQLite, que es lo que usan los tests).
    argumento_acotado = case(
        (argumento > 1, 1),
        (argumento < -1, -1),
        else_=argumento,
    )
    return 6371 * func.acos(argumento_acotado)

# Rutas públicas

@blog.route("/")
def index():
    """Lista pública de emprendimientos, paginada, con busqueda y filtro por categoria."""
    # La relacion author_user usa lazy="joined", asi que el autor viene en la
    # misma consulta y no se dispara un SELECT por cada post (problema N+1).
    # El promedio de reseñas se trae con el mismo criterio (ver services/ratings.py).
    query = query_posts_con_rating()

    busqueda = (request.args.get("q") or "").strip()
    if busqueda:
        patron = f"%{busqueda}%"
        query = query.filter(Post.title.ilike(patron) | Post.body.ilike(patron))

    categoria = (request.args.get("category") or "").strip()
    if categoria in Categorias.TODAS:
        query = query.filter(Post.category == categoria)

    # Busqueda por cercania: se puede pasar lat/lon directamente (por ejemplo
    # desde la geolocalizacion del navegador) o una direccion en texto para
    # geocodificar con MapTiler, igual que al cargar un emprendimiento.
    cerca_de = (request.args.get("near") or "").strip()
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if cerca_de and lat is None and lon is None:
        lat, lon = get_coordinates_from_address(cerca_de, current_app.config["MAPTILER_KEY"])
        if lat is None:
            flash("No pudimos ubicar esa dirección en el mapa. Probá con otro formato, o dejá el campo vacío.")

    ordenar_por_distancia = lat is not None and lon is not None
    if ordenar_por_distancia:
        # Sin coordenadas propias, un post no tiene con que calcular la
        # distancia: se excluye en vez de mostrarlo con un orden arbitrario.
        query = query.filter(Post.latitude.isnot(None), Post.longitude.isnot(None))
        distancia = _distancia_km(lat, lon)
        query = query.add_columns(distancia.label("distance_km"))
        orden = distancia.asc()
    else:
        orden = Post.created.desc()

    paginacion = (
        query
        .order_by(orden)
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["POSTS_POR_PAGINA"],
            error_out=False,
        )
    )
    favoritos = _ids_favoritos(g.user.id) if g.user else frozenset()
    if ordenar_por_distancia:
        posts = [
            {
                "post": post,
                "avg_rating": round(avg_rating, 1) if avg_rating else None,
                "review_count": review_count or 0,
                "is_favorite": post.id in favoritos,
                "distance_km": round(distance_km, 1) if distance_km is not None else None,
            }
            for post, avg_rating, review_count, distance_km in paginacion.items
        ]
    else:
        posts = serializar_con_rating(paginacion.items, favoritos)
        for item in posts:
            item["distance_km"] = None

    return render_template(
        "blog/index.html",
        posts=posts,
        paginacion=paginacion,
        categorias=Categorias.ETIQUETAS,
        categoria_actual=categoria,
        busqueda_actual=busqueda,
        cerca_de_actual=cerca_de,
        ordenado_por_distancia=ordenar_por_distancia,
    )

@blog.route("/<int:id>")
def detail(id):
    """Detalle de un emprendimiento + reseñas."""
    post = Post.query.get_or_404(id)
    author = post.author_user

    # No cuenta las vistas del propio dueño revisando su publicacion.
    if not (g.user and g.user.id == post.author):
        post.views_count += 1
        db.session.commit()

    reviews = (
        Review.query
        .filter_by(post_id=id)
        .order_by(Review.created.desc())
        .all()
    )

    avg_rating = (
        db.session.query(func.avg(Review.rating))
        .filter(Review.post_id == id)
        .scalar()
    )
    # Redondeo simple a 1 decimal
    avg_rating = round(avg_rating, 1) if avg_rating else None

    # La reseña propia (si existe) se usa para precargar el formulario en modo
    # edicion, en vez de mostrar siempre el formulario vacio de "dejar una
    # reseña" aunque el usuario ya haya dejado la suya.
    mi_review = (
        Review.query.filter_by(post_id=id, user_id=g.user.id).first()
        if g.user else None
    )

    is_favorite = (
        g.user is not None
        and Favorite.query.filter_by(user_id=g.user.id, post_id=id).first() is not None
    )

    return render_template(
            "blog/detail.html",
            post=post,
            author=author,
            reviews=reviews,
            avg_rating=avg_rating,
            mi_review=mi_review,
            is_favorite=is_favorite,
            MAPTILER_KEY=current_app.config["MAPTILER_KEY"]
    )

# Rutas privadas (usuario logueado)

@blog.route("/mis-emprendimientos")
@login_required
def my_posts():
    """Listado de emprendimientos del usuario actual, paginado."""
    paginacion = (
        Post.query.filter_by(author=g.user.id)
        .order_by(Post.created.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["POSTS_POR_PAGINA"],
            error_out=False,
        )
    )
    return render_template(
        "blog/my_posts.html", posts=paginacion.items, paginacion=paginacion
    )


@blog.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Registrar un nuevo emprendimiento."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        file = request.files.get("image")
        category = request.form.get("category", "").strip()

        address_street = request.form.get("address_street", "").strip()
        latitude = None
        longitude = None


        error = None
        filename = None

        if not title:
            error = "Se requiere un título."
        elif not body:
            error = "Se requiere una descripción."

        if error is None:
            upload_dir = os.path.join(current_app.root_path, "static", "uploads")
            filename, image_error = save_post_image(file, upload_dir)
            if image_error:
                error = image_error

        if error:
            flash(error)
        else:
            # --- LÓGICA DE GEOCODIFICACIÓN (CREATE) ---
            if address_street:
                api_key = current_app.config["MAPTILER_KEY"]
                latitude, longitude = get_coordinates_from_address(address_street, api_key)
                if not latitude:
                    flash("No se pudo encontrar la dirección en el mapa, pero el post se guardó sin ubicación. Revisá el formato de la dirección.")

            post = Post(
                author=g.user.id,
                title=title,
                body=body,
                image=filename,
                latitude=latitude,
                longitude=longitude,
                address_street=address_street if address_street else None,
                category=category,
            )
            # --- FIN CAMBIOS ---

            db.session.add(post)
            db.session.commit()
            flash("Emprendimiento registrado correctamente.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/create.html", categorias=Categorias.ETIQUETAS)


@blog.route("/update/<int:id>", methods=("GET", "POST"))
@login_required
def update(id):
    """Actualizar emprendimiento existente."""
    post = Post.query.get_or_404(id)
    if post.author != g.user.id:
        flash("No tenés permiso para editar este emprendimiento.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        file = request.files.get("image")
        category = request.form.get("category", "").strip()

        address_street = request.form.get("address_street", "").strip()
        latitude = post.latitude
        longitude = post.longitude


        error = None
        if not title:
            error = "Se requiere un título."

        # Imagen nueva (si no se sube ninguna, se conserva la que ya tenia)
        if error is None:
            upload_dir = os.path.join(current_app.root_path, "static", "uploads")
            filename, image_error = save_post_image(file, upload_dir)
            if image_error:
                error = image_error
            elif filename:
                post.image = filename

        if error:
            flash(error)
        else:
            # --- LÓGICA DE GEOCODIFICACIÓN (UPDATE) ---
            # Solo geocodificamos SI la dirección cambió
            if address_street != post.address_street:
                if address_street:
                    api_key = current_app.config["MAPTILER_KEY"]
                    latitude, longitude = get_coordinates_from_address(address_street, api_key)
                    if not latitude:
                        flash("No se pudo encontrar la nueva dirección, se mantuvo la anterior.")
                        latitude = post.latitude # Revertimos si falla
                        longitude = post.longitude
                else:
                    # El usuario borró la dirección
                    latitude = None
                    longitude = None

            post.title = title
            post.body = body
            post.latitude = latitude
            post.longitude = longitude
            post.address_street = address_street if address_street else None
            post.category = category if category in Categorias.TODAS else post.category
            # --- FIN CAMBIOS ---

            db.session.commit()
            flash("Emprendimiento actualizado correctamente.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/update.html", post=post, categorias=Categorias.ETIQUETAS)


@blog.route("/delete/<int:id>", methods=("POST",))
@login_required
def delete(id):
    """Eliminar emprendimiento.

    Solo acepta POST: un GET no debe tener efectos secundarios (podria
    dispararse desde un <img src>, un prefetch del navegador o un crawler).
    """
    post = Post.query.get_or_404(id)
    if post.author != g.user.id:
        flash("No tenés permiso para eliminar este emprendimiento.")
        return redirect(url_for("blog.my_posts"))

    try:
        db.session.delete(post)
        db.session.commit()
        flash("Emprendimiento eliminado correctamente.")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al eliminar el post %s", id)
        flash("Error al eliminar el emprendimiento.")
    return redirect(url_for("blog.my_posts"))

@blog.route("/<int:id>/review", methods=["POST"])
@login_required
def add_review(id):
    """Agregar una reseña (rating + comentario) a un emprendimiento."""
    post = Post.query.get_or_404(id)

    # No permitir que el autor se reseñe a sí mismo
    if post.author == g.user.id:
        flash("No podés dejar una reseña sobre tu propio emprendimiento.")
        return redirect(url_for("blog.detail", id=id))

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0

    comment = (request.form.get("comment") or "").strip()

    error = None
    if rating < 1 or rating > 5:
        error = "Seleccioná una calificación entre 1 y 5 estrellas."

    if error:
        flash(error)
        return redirect(url_for("blog.detail", id=id))

    # Un usuario tiene una sola resena por emprendimiento (lo garantiza un
    # UniqueConstraint). Si ya dejo una, esta la actualiza en vez de fallar.
    review = Review.query.filter_by(post_id=id, user_id=g.user.id).first()

    try:
        if review is None:
            review = Review(
                post_id=id,
                user_id=g.user.id,
                rating=rating,
                comment=comment
            )
            db.session.add(review)
            mensaje = "¡Gracias por tu reseña!"
        else:
            review.rating = rating
            review.comment = comment
            review.updated_at = utcnow()
            # La respuesta del dueño quedo escrita para el contenido viejo:
            # si no se limpia, parece que responde a algo que la reseña ya
            # no dice. Se borra para forzar que responda de nuevo.
            if review.reply is not None:
                review.reply = None
                review.replied_at = None
            mensaje = "Actualizamos tu reseña."

        db.session.commit()
        flash(mensaje)
    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception("Error al guardar la resena del post %s", id)
        flash("No pudimos guardar tu reseña. Intentá de nuevo.")

    return redirect(url_for("blog.detail", id=id))


@blog.route("/review/<int:review_id>/reply", methods=["POST"])
@login_required
def reply_review(review_id):
    """El dueño del emprendimiento responde publicamente a una reseña."""
    review = Review.query.get_or_404(review_id)

    if review.post.author != g.user.id:
        flash("No tenés permiso para responder esta reseña.")
        return redirect(url_for("blog.detail", id=review.post_id))

    texto = (request.form.get("reply") or "").strip()
    if not texto:
        flash("Escribí una respuesta antes de enviarla.")
        return redirect(url_for("blog.detail", id=review.post_id))

    review.reply = texto
    review.replied_at = utcnow()
    db.session.commit()
    flash("Tu respuesta se publicó correctamente.")

    return redirect(url_for("blog.detail", id=review.post_id))


@blog.route("/review/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    """Eliminar la propia reseña. Editarla ya se resuelve reenviando add_review,
    que actualiza en vez de duplicar (ver el UniqueConstraint de Review)."""
    review = Review.query.get_or_404(review_id)

    if review.user_id != g.user.id:
        flash("No tenés permiso para eliminar esta reseña.")
        return redirect(url_for("blog.detail", id=review.post_id))

    post_id = review.post_id
    db.session.delete(review)
    db.session.commit()
    flash("Tu reseña se eliminó correctamente.")

    return redirect(url_for("blog.detail", id=post_id))


@blog.route("/<int:id>/favorito", methods=["POST"])
@login_required
def toggle_favorite(id):
    """Marca o desmarca un emprendimiento como favorito (toggle)."""
    post = Post.query.get_or_404(id)

    favorito = Favorite.query.filter_by(user_id=g.user.id, post_id=post.id).first()
    if favorito:
        db.session.delete(favorito)
        db.session.commit()
        flash("Se quitó de tus favoritos.")
    else:
        try:
            db.session.add(Favorite(user_id=g.user.id, post_id=post.id))
            db.session.commit()
            flash("Se agregó a tus favoritos.")
        except IntegrityError:
            # Ventana de carrera: dos clicks casi simultaneos en "favorito".
            db.session.rollback()

    destino = request.referrer or url_for("blog.detail", id=post.id)
    return redirect(destino)


@blog.route("/favoritos")
@login_required
def my_favorites():
    """Emprendimientos que el usuario marco como favoritos."""
    paginacion = (
        query_posts_con_rating(Post.query.join(Favorite, Favorite.post_id == Post.id))
        .filter(Favorite.user_id == g.user.id)
        .order_by(Post.created.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["POSTS_POR_PAGINA"],
            error_out=False,
        )
    )
    posts = serializar_con_rating(paginacion.items, favoritos=_ids_favoritos(g.user.id))
    return render_template("blog/favorites.html", posts=posts, paginacion=paginacion)


@blog.route("/reportar/<string:tipo>/<int:target_id>", methods=("GET", "POST"))
@login_required
def report(tipo, target_id):
    """Reportar un emprendimiento o una reseña por contenido inapropiado.

    Alimenta al panel de admin (ver views/admin.py reportes()).
    """
    if tipo not in ("post", "review"):
        abort(404)

    if tipo == "post":
        objetivo = Post.query.get_or_404(target_id)
        if objetivo.author == g.user.id:
            flash("No podés reportar tu propio emprendimiento.")
            return redirect(url_for("blog.detail", id=target_id))
        volver = url_for("blog.detail", id=target_id)
    else:
        objetivo = Review.query.get_or_404(target_id)
        if objetivo.user_id == g.user.id:
            flash("No podés reportar tu propia reseña.")
            return redirect(url_for("blog.detail", id=objetivo.post_id))
        volver = url_for("blog.detail", id=objetivo.post_id)

    if request.method == "POST":
        motivo = (request.form.get("reason") or "").strip()
        if not motivo:
            flash("Contanos el motivo del reporte.")
        else:
            db.session.add(Report(
                reporter_id=g.user.id,
                post_id=target_id if tipo == "post" else None,
                review_id=target_id if tipo == "review" else None,
                reason=motivo,
            ))
            db.session.commit()
            flash("Gracias, revisaremos tu reporte.")
            return redirect(volver)

    return render_template("blog/report.html", tipo=tipo, objetivo=objetivo, volver=volver)