"""Las rutas del dominio: HTTP y nada mas.

Lo que queda aca es lo que solo se puede hacer con un request delante: leer el
formulario, elegir el mensaje, redirigir o renderizar. Las decisiones estan en
reglas.py y las consultas en consultas.py.

El blueprint se sigue llamando "profile" y sigue colgando de /perfil: los
url_for de todos los templates lo nombran asi, y renombrarlo es otra tanda.
Trae su propio template_folder, con lo cual profile.html y profile/*.html
viajan con el codigo del dominio (base.html y los partials siguen saliendo de
la carpeta global de la app).
"""

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.exc import IntegrityError

from app.perfil import consultas, formulario, reglas
from app.perfil.modelo_horario import Horario
from app.perfil.modelo_follow import Follow
from services.geocoding import get_coordinates_from_address
from services.horarios import DIAS, esta_abierto
from services.ratings import serializar_con_rating
from services.uploads import carpeta_uploads, save_post_image
from views.auth import login_required

profile = Blueprint(
    "profile", __name__, url_prefix="/perfil", template_folder="templates"
)


# Las rutas por <slug> son las canonicas; las /<int:user_id> de mas abajo
# quedan solo como redirect 301 para no romper los links viejos. Werkzeug
# prueba primero la regla con el converter int, asi que /perfil/123 cae en el
# redirect y /perfil/panaderia en el perfil, sin ambiguedad.
@profile.route("/<slug>")
def view_profile(slug):
    user = consultas.usuario_por_slug_o_404(slug)
    es_dueño = reglas.es_el_dueño(user, g.user)
    horarios = consultas.horarios_de(user)

    # Quien sigue a quien es dato privado, con el mismo criterio que
    # views_count: al visitante solo se le dice si lo sigue EL (su propia
    # relacion), nunca quien mas lo sigue. La lista "Sigo a" y la cantidad de
    # seguidores son del dueño y no se calculan si mira otro.
    lo_sigo = bool(
        g.user
        and not es_dueño
        and consultas.seguimiento_entre(g.user.id, user.id)
    )
    siguiendo = consultas.a_quienes_sigue(user.id) if es_dueño else []

    # Los eventos son publicos, a diferencia de estadisticas y "Sigo a": un
    # evento es un anuncio, no una metrica del dueño. Se calculan siempre, mire
    # quien mire.
    eventos_proximos, eventos_pasados = consultas.eventos_del_perfil(
        user.id, reglas.MAX_EVENTOS_PASADOS
    )

    return render_template(
        "profile.html",
        user=user,
        posts=serializar_con_rating(consultas.emprendimientos_con_rating_de(user.id)),
        eventos_proximos=eventos_proximos,
        eventos_pasados=eventos_pasados,
        estadisticas=consultas.estadisticas_de_usuario(user.id) if es_dueño else None,
        lo_sigo=lo_sigo,
        siguiendo=siguiendo,
        horarios=horarios,
        # None y no False cuando no hay horarios cargados: el template tiene que
        # poder distinguir "cerrado ahora" de "este usuario no publico horarios".
        abierto_ahora=esta_abierto(horarios) if horarios else None,
        etiquetas_dias=dict(DIAS),
        MAPTILER_KEY=current_app.config["MAPTILER_KEY"]
    )


@profile.route("/<slug>/resenias")
def reviews(slug):
    """Todas las reseñas recibidas en los emprendimientos del usuario, paginadas."""
    user = consultas.usuario_por_slug_o_404(slug)
    paginacion = consultas.resenias_recibidas_por(
        user.id,
        page=request.args.get("page", 1, type=int),
        per_page=current_app.config["POSTS_POR_PAGINA"],
    )
    return render_template(
        "profile/reviews.html",
        user=user,
        paginacion=paginacion,
        resumen=consultas.resumen_de_resenias_recibidas(user.id),
    )


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
    user = consultas.usuario_por_id_o_404(user_id)
    return _redirect_301_al_slug("profile.view_profile", user.slug)


@profile.route("/<int:user_id>/resenias")
def reviews_por_id(user_id):
    user = consultas.usuario_por_id_o_404(user_id)
    return _redirect_301_al_slug("profile.reviews", user.slug)


# --- 1.d SEGUIR / DEJAR DE SEGUIR

@profile.route("/<slug>/seguir", methods=("POST",))
@login_required
def toggle_follow(slug):
    """Empieza o deja de seguir a un emprendedor (toggle, como favoritos)."""
    user = consultas.usuario_por_slug_o_404(slug)

    if not reglas.puede_seguir(user, g.user):
        flash("No podés seguirte a vos mismo.")
        return redirect(url_for("profile.view_profile", slug=user.slug))

    seguimiento = consultas.seguimiento_entre(g.user.id, user.id)

    if seguimiento:
        consultas.borrar(seguimiento)
        flash(f"Dejaste de seguir a {user.username}.")
    else:
        try:
            consultas.guardar(Follow(follower_id=g.user.id, followed_id=user.id))
            flash(f"Ahora seguís a {user.username}.")
        except IntegrityError:
            # Ventana de carrera: dos clicks casi simultaneos en "Seguir".
            consultas.descartar()

    return redirect(url_for("profile.view_profile", slug=user.slug))


# --- 1.c HORARIOS DE ATENCION

@profile.route("/horarios", methods=("GET", "POST"))
@login_required
def horarios():
    """Panel donde el dueño carga su horario de atencion, un rango por dia."""
    existentes = consultas.horarios_por_dia_de(g.user)

    if request.method == "GET":
        return render_template(
            "profile/horarios.html", filas=formulario.filas_guardadas(existentes)
        )

    pendientes, error = formulario.leer_horarios()

    if error:
        # Se le devuelve lo que escribio, no lo que hay guardado.
        flash(error)
        return render_template(
            "profile/horarios.html",
            filas=[formulario.fila_de_horario(*fila) for fila in pendientes],
        )

    for dia, _etiqueta, cerrado, abre, cierra in pendientes:
        horario = existentes.get(dia)
        if horario is None:
            horario = Horario(user_id=g.user.id, dia_semana=dia)
            consultas.agregar(horario)
        horario.cerrado, horario.abre, horario.cierra = reglas.horario_del_dia(
            cerrado, abre, cierra
        )

    consultas.guardar()
    flash("Horarios actualizados correctamente.")
    return redirect(url_for("profile.view_profile", slug=g.user.slug))


# --- 2. RUTA DE BIOGRAFÍA

@profile.route("/create_bio", methods=("GET", "POST"))
@login_required
def create():
    """Permite al usuario logueado crear o actualizar solo su biografía."""
    if request.method == "POST":
        biografia, error = formulario.leer_bio()
        if error:
            flash(error)
        else:
            g.user.biography = biografia
            consultas.guardar()
            flash("Biografía actualizada con éxito.")
            return redirect(url_for("profile.view_profile", slug=g.user.slug))

    return render_template("profile/create_bio.html")


#  3. RUTA PERFIL
@profile.route("/edit", methods=("GET", "POST"))
@login_required
def edit():
    """Permite al usuario logueado editar su perfil: foto, bio, contacto y dirección."""

    if request.method == "POST":
        datos = formulario.leer_perfil()

        # Usamos los datos existentes como fallback
        latitude = g.user.latitude
        longitude = g.user.longitude

        # 1. Actualizamos la biografía
        g.user.biography = datos["biography"] if datos["biography"] else g.user.biography

        # 1.b Foto de perfil (opcional, se conserva la anterior si no se sube otra)
        avatar_filename, avatar_error = save_post_image(
            request.files.get("avatar"), carpeta_uploads("avatars")
        )
        if avatar_error:
            flash(avatar_error)
        elif avatar_filename:
            g.user.avatar = avatar_filename

        # 1.b.2 Imagen de portada (misma validacion/compresion que el avatar)
        cover_filename, cover_error = save_post_image(
            request.files.get("cover_image"), carpeta_uploads("covers")
        )
        if cover_error:
            flash(cover_error)
        elif cover_filename:
            g.user.cover_image = cover_filename

        # 1.c Datos de contacto
        g.user.phone = datos["phone"] or None
        g.user.whatsapp = datos["whatsapp"] or None
        g.user.instagram_url = datos["instagram_url"] or None
        g.user.facebook_url = datos["facebook_url"] or None
        g.user.twitter_url = datos["twitter_url"] or None

        # 1.d Ubicacion textual. Se guarda tal cual, sin geocodificar: no toca
        # latitude/longitude ni address_street.
        g.user.location = datos["location"] or None

        # 2. Geocodificación y ubicación
        # Solo geocodificamos SI la dirección cambió o se eliminó
        address_street = datos["address_street"]
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

        consultas.guardar()
        flash("Perfil actualizado correctamente.")
        return redirect(url_for("profile.view_profile", slug=g.user.slug))

    return render_template("profile/edit.html", user=g.user)
