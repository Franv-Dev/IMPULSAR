import os

from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from sqlalchemy.orm import joinedload

from models.horario import Horario
from models.post import Post
from models.review import Review
from models.user import User
from views.auth import login_required
from db import db
from services.geocoding import get_coordinates_from_address
from services.horarios import DIAS, esta_abierto, formatear as formatear_hora, parsear_hora
from services.ratings import query_posts_con_rating, serializar_con_rating
from services.stats import estadisticas_de_usuario
from services.uploads import save_post_image

profile = Blueprint("profile", __name__, url_prefix="/perfil")


# Las rutas por <slug> son las canonicas; las /<int:user_id> de mas abajo
# quedan solo como redirect 301 para no romper los links viejos. Werkzeug
# prueba primero la regla con el converter int, asi que /perfil/123 cae en el
# redirect y /perfil/panaderia en el perfil, sin ambiguedad.
@profile.route("/<slug>")
def view_profile(slug):
    user = User.query.filter_by(slug=slug).first_or_404()
    filas = (
        query_posts_con_rating(Post.query.filter_by(author=user.id))
        .order_by(Post.created.desc())
        .all()
    )
    # Mismo criterio de privacidad que views_count: las metricas son del dueño,
    # asi que ni siquiera se calculan cuando mira otro (una consulta menos y
    # ningun dato que se pueda filtrar por error en el template).
    es_dueño = bool(g.user and g.user.id == user.id)
    horarios = sorted(user.horarios, key=lambda h: h.dia_semana)
    return render_template(
        "profile.html",
        user=user,
        posts=serializar_con_rating(filas),
        estadisticas=estadisticas_de_usuario(user.id) if es_dueño else None,
        horarios=horarios,
        # None y no False cuando no hay horarios cargados: el template tiene que
        # poder distinguir "cerrado ahora" de "este usuario no publico horarios".
        abierto_ahora=esta_abierto(horarios) if horarios else None,
        etiquetas_dias=dict(DIAS),
        MAPTILER_KEY=current_app.config["MAPTILER_KEY"]
    )


@profile.route("/<slug>/resenias")
def reviews(slug):
    """Todas las reseñas recibidas en los emprendimientos del usuario, paginadas.

    A diferencia del detalle de un post (que solo muestra las reseñas de ESE
    emprendimiento), esto junta las de todos los emprendimientos del usuario
    en un solo listado.
    """
    user = User.query.filter_by(slug=slug).first_or_404()
    paginacion = (
        Review.query
        .join(Post, Post.id == Review.post_id)
        .options(joinedload(Review.post), joinedload(Review.user))
        .filter(Post.author == user.id)
        .order_by(Review.created.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["POSTS_POR_PAGINA"],
            error_out=False,
        )
    )
    return render_template("profile/reviews.html", user=user, paginacion=paginacion)


# --- 1.b RUTAS VIEJAS POR ID (redirect permanente al slug)

def _redirect_301_al_slug(endpoint, slug):
    """Redirige a la URL por slug conservando el query string.

    Sin esto, /perfil/5/resenias?page=2 caia en la pagina 1: el redirect
    reconstruye la URL desde cero con url_for y los parametros se pierden.
    """
    destino = url_for(endpoint, slug=slug)
    if request.query_string:
        destino = f"{destino}?{request.query_string.decode()}"
    return redirect(destino, code=301)


@profile.route("/<int:user_id>")
def view_profile_por_id(user_id):
    """301 y no 302: la URL por id dejo de ser la canonica para siempre, y el
    301 hace que buscadores y clientes se queden con la version por slug."""
    user = User.query.get_or_404(user_id)
    return _redirect_301_al_slug("profile.view_profile", user.slug)


@profile.route("/<int:user_id>/resenias")
def reviews_por_id(user_id):
    user = User.query.get_or_404(user_id)
    return _redirect_301_al_slug("profile.reviews", user.slug)


# --- 1.c HORARIOS DE ATENCION

@profile.route("/horarios", methods=("GET", "POST"))
@login_required
def horarios():
    """Panel donde el dueño carga su horario de atencion, un rango por dia."""
    existentes = {h.dia_semana: h for h in g.user.horarios}

    def fila(dia, etiqueta, cerrado, abre, cierra):
        """Una linea del formulario, con las horas ya como texto "HH:MM"."""
        return {
            "dia": dia, "etiqueta": etiqueta, "cerrado": cerrado,
            "abre": formatear_hora(abre), "cierra": formatear_hora(cierra),
        }

    if request.method == "GET":
        filas = [
            fila(dia, etiqueta,
                 existentes[dia].cerrado if dia in existentes else False,
                 existentes[dia].abre if dia in existentes else None,
                 existentes[dia].cierra if dia in existentes else None)
            for dia, etiqueta in DIAS
        ]
        return render_template("profile/horarios.html", filas=filas)

    error = None
    pendientes = []
    for dia, etiqueta in DIAS:
        cerrado = request.form.get(f"cerrado_{dia}") == "on"
        abre = parsear_hora(request.form.get(f"abre_{dia}"))
        cierra = parsear_hora(request.form.get(f"cierra_{dia}"))

        if not cerrado and (abre is None) != (cierra is None):
            error = f"{etiqueta}: cargá la hora de apertura y la de cierre, o marcá el día como cerrado."
        elif not cerrado and abre and cierra and abre == cierra:
            error = f"{etiqueta}: la hora de apertura y la de cierre no pueden ser iguales."

        pendientes.append((dia, etiqueta, cerrado, abre, cierra))

    if error:
        # Se le devuelve lo que escribio, no lo que hay guardado: perder el
        # formulario entero por un dia mal cargado obliga a rehacer los siete.
        flash(error)
        return render_template(
            "profile/horarios.html",
            filas=[fila(d, e, c, a, ci) for d, e, c, a, ci in pendientes],
        )

    for dia, _etiqueta, cerrado, abre, cierra in pendientes:
        horario = existentes.get(dia)
        if horario is None:
            horario = Horario(user_id=g.user.id, dia_semana=dia)
            db.session.add(horario)
        # Un dia sin horas cargadas se guarda como cerrado: deja la fila
        # completa en vez de a medias, y el indicador lo lee igual.
        horario.cerrado = cerrado or not (abre and cierra)
        horario.abre = None if horario.cerrado else abre
        horario.cierra = None if horario.cerrado else cierra

    db.session.commit()
    flash("Horarios actualizados correctamente.")
    return redirect(url_for("profile.view_profile", slug=g.user.slug))


# --- 2. RUTA DE BIOGRAFÍA

@profile.route("/create_bio", methods=("GET", "POST"))
@login_required
def create():
    """Permite al usuario logueado crear o actualizar solo su biografía."""
    if request.method == "POST":
        biography = request.form.get("body", "").strip()
        if not biography:
            flash("Se requiere una biografía.")
        else:
            g.user.biography = biography
            db.session.commit()
            flash("Biografía actualizada con éxito.")
            return redirect(url_for("profile.view_profile", slug=g.user.slug))

    
    
    return render_template("profile/create_bio.html")


#  3. RUTA PERFIL 
@profile.route("/edit", methods=("GET", "POST"))
@login_required
def edit():
    """Permite al usuario logueado editar su perfil: foto, bio, contacto y dirección."""

    if request.method == "POST":
        # Obtenemos los datos del formulario
        biography = request.form.get("biography", "").strip()
        # Ojo: son dos campos distintos. location es texto libre que solo se
        # muestra; address_street es la direccion que se geocodifica mas abajo.
        location = request.form.get("location", "").strip()
        address_street = request.form.get("address_street", "").strip()
        phone = request.form.get("phone", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        instagram_url = request.form.get("instagram_url", "").strip()
        facebook_url = request.form.get("facebook_url", "").strip()
        twitter_url = request.form.get("twitter_url", "").strip()

        # Usamos los datos existentes como fallback
        latitude = g.user.latitude
        longitude = g.user.longitude

        # 1. Actualizamos la biografía
        g.user.biography = biography if biography else g.user.biography

        # 1.b Foto de perfil (opcional, se conserva la anterior si no se sube otra)
        avatar_file = request.files.get("avatar")
        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "avatars")
        avatar_filename, avatar_error = save_post_image(avatar_file, upload_dir)
        if avatar_error:
            flash(avatar_error)
        elif avatar_filename:
            g.user.avatar = avatar_filename

        # 1.b.2 Imagen de portada (misma validacion/compresion que el avatar)
        cover_file = request.files.get("cover_image")
        cover_dir = os.path.join(current_app.root_path, "static", "uploads", "covers")
        cover_filename, cover_error = save_post_image(cover_file, cover_dir)
        if cover_error:
            flash(cover_error)
        elif cover_filename:
            g.user.cover_image = cover_filename

        # 1.c Datos de contacto
        g.user.phone = phone or None
        g.user.whatsapp = whatsapp or None
        g.user.instagram_url = instagram_url or None
        g.user.facebook_url = facebook_url or None
        g.user.twitter_url = twitter_url or None

        # 1.d Ubicacion textual. Se guarda tal cual, sin geocodificar: no toca
        # latitude/longitude ni address_street.
        g.user.location = location or None

        # 2. Geocodificación y ubicación
        # Solo geocodificamos SI la dirección cambió o se eliminó
        if address_street != g.user.address_street:
            if address_street:
                api_key = current_app.config["MAPTILER_KEY"]
                latitude, longitude = get_coordinates_from_address(address_street, api_key)
                if not latitude:
                    # Si la geocodificación falla, mostramos un error pero guardamos el resto
                    flash("No se pudo encontrar la dirección en el mapa. Por favor, intentá con un formato más específico.")
                    latitude = g.user.latitude 
                    longitude = g.user.longitude
            else:
                # El usuario borró la dirección de texto
                latitude = None
                longitude = None
        
        # 3. Guarda todos los cambios en el usuario logueado
        g.user.latitude = latitude
        g.user.longitude = longitude
        g.user.address_street = address_street if address_street else None
        
        db.session.commit()
        flash("Perfil actualizado correctamente.")
        return redirect(url_for("profile.view_profile", slug=g.user.slug))

    return render_template("profile/edit.html", user=g.user)