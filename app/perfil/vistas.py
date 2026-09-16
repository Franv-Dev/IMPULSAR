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

from app.panel.consultas import contadores_de as contadores_del_panel
from app.perfil import consultas, formulario, reglas
from app.perfil.modelo_horario import Horario
from app.perfil.modelo_follow import Follow
# Lo que el usuario tiene en curso como CLIENTE sale de los otros dos dominios:
# el perfil no arma esas consultas de nuevo, las pide donde ya viven.
from app.servicios import consultas as consultas_servicios
from app.turnos import consultas as consultas_turnos
from models.user import Roles
from services.eventos import hoy_en_argentina
from services.geocoding import get_coordinates_from_address
from services.horarios import DIAS, ahora_en_argentina, esta_abierto
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
    es_el_dueño = reglas.es_el_dueño(user, g.user)

    # "Ver como visitante": la app no decia en ningun lado que lo que estas
    # mirando es tu propio perfil ni que ves de mas que el resto. La barra de
    # arriba lo dice y este parametro deja comprobarlo.
    #
    # Apaga lo privado ACA y no con CSS en el template: asi la vista previa no
    # es un dibujo, es exactamente la misma consulta que corre para un
    # visitante (estadisticas, turnos y presupuestos ni se piden). `es_dueño`
    # es el permiso ya mezclado con la vista elegida, que es lo unico que el
    # template tiene que mirar para decidir si algo se dibuja.
    vista_visitante = es_el_dueño and request.args.get("ver") == "visitante"
    es_dueño = es_el_dueño and not vista_visitante

    horarios = consultas.horarios_de(user)

    # El perfil de un cliente es otra pantalla, no la misma con secciones
    # vacias: sin portada de marca, avatar mas chico y sin la grilla de
    # horarios de atencion, que no va a tener nunca. Un negocio se presenta
    # como negocio; alguien que entro a comprar, no.
    #
    # Se pide el rol Y que no haya publicado nada: si un "usuario" tiene
    # emprendimientos, el que esta equivocado es el rol, y quedarse con la
    # forma de negocio es lo que no rompe la pantalla.
    # Los borradores solo para el dueño, y no en "ver como visitante".
    posts = serializar_con_rating(consultas.emprendimientos_con_rating_de(
        user.id, incluir_borradores=es_dueño,
    ))
    perfil_de_cliente = user.rol == Roles.USUARIO and not posts

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
        user.id, reglas.MAX_EVENTOS_PASADOS, incluir_borradores=es_dueño,
    )

    # Turnos y presupuestos son PRIVADOS, con el mismo criterio que las
    # estadisticas: se consultan solo cuando el que mira es el dueño, asi no
    # hay forma de que un error del template los filtre. Y son lo que le da
    # contenido al perfil de alguien que no vende: antes, un usuario sin
    # emprendimientos veia una pantalla vacia con la que no podia hacer nada.
    ahora = ahora_en_argentina()
    turnos_en_curso = []
    presupuestos_en_curso = []
    if es_dueño:
        turnos_en_curso = reglas.turnos_en_curso(
            consultas_turnos.turnos_de_cliente(user.id), ahora.date()
        )
        presupuestos_en_curso = reglas.presupuestos_en_curso(
            consultas_servicios.solicitudes_enviadas_por(user.id)
        )

    # Las reseñas dejan de vivir solo en /perfil/<slug>/resenias y entran como
    # una pestaña mas del perfil: son publicas, son la prueba de que a este
    # emprendimiento ya le compraron, y mandarlas a otra pantalla era pedirle
    # al visitante que se fuera del perfil justo cuando esta decidiendo.
    #
    # Van las ultimas MAX_RESENIAS_EN_EL_PERFIL y no la lista entera: la pagina
    # completa sigue existiendo, paginada, y el bloque termina en un enlace a
    # ella. El resumen (promedio y distribucion) es sobre TODAS, no sobre estas.
    reputacion = consultas.reputacion_de(user.id)
    resenias = []
    resumen_resenias = None
    if reputacion["total"]:
        resumen_resenias = consultas.resumen_de_resenias_recibidas(user.id)
        resenias = consultas.resenias_recibidas_por(
            user.id, page=1, per_page=reglas.MAX_RESENIAS_EN_EL_PERFIL
        ).items

    return render_template(
        "profile.html",
        user=user,
        posts=posts,
        perfil_de_cliente=perfil_de_cliente,
        eventos_proximos=eventos_proximos,
        eventos_pasados=eventos_pasados,
        estadisticas=consultas.estadisticas_de_usuario(user.id) if es_dueño else None,
        # El template no vuelve a preguntar quien mira: `es_dueno` ya viene con
        # la vista previa aplicada, y `es_dueno_real` existe solo para dibujar
        # la barra de arriba (que el dueño tiene que seguir viendo mientras
        # mira su perfil con ojos de visitante, o no tendria como volver).
        es_dueno=es_dueño,
        es_dueno_real=es_el_dueño,
        vista_visitante=vista_visitante,
        resenias=resenias,
        resumen_resenias=resumen_resenias,
        # Publica, a diferencia de estadisticas: el promedio y el total de
        # reseñas ya se ven en cada tarjeta del catalogo y en /resenias.
        reputacion=reputacion,
        lo_sigo=lo_sigo,
        siguiendo=siguiendo,
        turnos_en_curso=turnos_en_curso,
        presupuestos_en_curso=presupuestos_en_curso,
        horarios=horarios,
        # None y no False cuando no hay horarios cargados: el template tiene que
        # poder distinguir "cerrado ahora" de "este usuario no publico horarios".
        abierto_ahora=esta_abierto(horarios) if horarios else None,
        etiquetas_dias=dict(DIAS),
        # Para resaltar la fila de hoy en la grilla de horarios. Sale del reloj
        # de Argentina y no del servidor por lo mismo que esta_abierto: con la
        # hora del servidor, un deploy en otra zona resalta el dia equivocado.
        dia_hoy=ahora.weekday(),
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
    # El menu del panel solo se dibuja para el dueño, asi que sus contadores
    # solo se consultan para el dueño: esta URL es publica y un visitante no
    # tiene por que pagar seis COUNT que no va a ver.
    es_dueno = g.user is not None and g.user.id == user.id
    return render_template(
        "profile/reviews.html",
        user=user,
        paginacion=paginacion,
        resumen=consultas.resumen_de_resenias_recibidas(user.id),
        contadores=(
            contadores_del_panel(user.id, hoy_en_argentina()) if es_dueno else None
        ),
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

    # Para la vista previa: el cartel que estas siete filas encienden en el
    # perfil. Sale de lo GUARDADO y no de lo que hay en el formulario, que es
    # justamente la comparacion que sirve mientras se edita. Mismo criterio que
    # en view_profile: None cuando no hay ni una fila cargada, para poder
    # distinguir "cerrado ahora" de "todavia no cargo horarios".
    guardados = consultas.horarios_de(g.user)
    contexto = {
        "abierto_ahora": esta_abierto(guardados) if guardados else None,
        "dia_hoy": ahora_en_argentina().weekday(),
    }

    if request.method == "GET":
        return render_template(
            "profile/horarios.html",
            filas=formulario.filas_guardadas(existentes),
            **contexto,
        )

    pendientes, error = formulario.leer_horarios()

    if error:
        # Se le devuelve lo que escribio, no lo que hay guardado.
        flash(error)
        return render_template(
            "profile/horarios.html",
            filas=[formulario.fila_de_horario(*fila) for fila in pendientes],
            **contexto,
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
        datos, _sin_error = formulario.leer_perfil_publico()

        # Usamos los datos existentes como fallback
        latitude = g.user.latitude
        longitude = g.user.longitude

        # 1. Actualizamos la biografía
        g.user.biography = datos["biography"] if datos["biography"] else g.user.biography

        # 1.b Foto de perfil (opcional, se conserva la anterior si no se sube otra)
        avatar_filename, avatar_error = save_post_image(
            request.files.get("avatar"), carpeta_uploads("avatars")
        )
        # Subir gana sobre quitar: si mando las dos cosas, lo que quiso es la
        # foto nueva. Quitar deja la columna en None y no borra el archivo, que
        # es como se comporta el resto del proyecto con los uploads viejos.
        if avatar_error:
            flash(avatar_error)
        elif avatar_filename:
            g.user.avatar = avatar_filename
        elif request.form.get("quitar_avatar"):
            g.user.avatar = None

        # 1.b.2 Imagen de portada (misma validacion/compresion que el avatar)
        cover_filename, cover_error = save_post_image(
            request.files.get("cover_image"), carpeta_uploads("covers")
        )
        if cover_error:
            flash(cover_error)
        elif cover_filename:
            g.user.cover_image = cover_filename
        elif request.form.get("quitar_cover"):
            g.user.cover_image = None

        # 1.c Ubicacion textual. Se guarda tal cual, sin geocodificar: no toca
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

    return render_template(
        "profile/edit.html", user=g.user,
        campos=formulario.campos_guardados(g.user),
    )


@profile.route("/edit/contacto", methods=("GET", "POST"))
@login_required
def edit_contacto():
    """Los telefonos y las redes, que antes vivian abajo de la biografía.

    Pantalla propia y no una seccion mas del formulario largo: son cinco campos
    que se cargan una vez y no se vuelven a tocar, y estaban entre la biografía
    y la dirección, que son las dos cosas que sí se editan seguido.
    """
    if request.method == "POST":
        datos, error = formulario.leer_contacto()
        if error:
            # Se corta antes de tocar nada: un telefono mal escrito es texto
            # del mismo formulario, y guardar los otros cuatro campos y no ese
            # dejaria el contacto a medias sin que se note cual falto.
            #
            # Se repinta con lo que la persona escribio y no con lo que hay
            # guardado, igual que el panel de horarios: si se vuelve a pintar
            # desde g.user, corregir el telefono cuesta reescribir los otros
            # cuatro, incluido el WhatsApp que estaba bien.
            flash(error)
            return render_template(
                "profile/contacto.html", user=g.user,
                campos=dict(formulario.campos_guardados(g.user), **datos),
                error=error,
            )

        g.user.phone = datos["phone"] or None
        g.user.whatsapp = datos["whatsapp"] or None
        g.user.instagram_url = datos["instagram_url"] or None
        g.user.facebook_url = datos["facebook_url"] or None
        g.user.twitter_url = datos["twitter_url"] or None

        consultas.guardar()
        flash("Contacto actualizado correctamente.")
        return redirect(url_for("profile.edit_contacto"))

    return render_template(
        "profile/contacto.html", user=g.user,
        campos=formulario.campos_guardados(g.user),
        error=None,
    )


@profile.route("/mi-cuenta")
@login_required
def cuenta():
    """La pantalla "Mi cuenta" del telefono (artboard
    disenio-navegacion/MovilPerfil.dc.html).

    Es el destino de la pestana Perfil de la barra de abajo. En escritorio lo
    mismo esta en el menu que cuelga del avatar, asi que ahi la ruta existe
    igual pero nadie la enlaza: no se esconde ni se redirige porque un link
    compartido tiene que seguir abriendo algo, y lo que muestra es correcto en
    los dos anchos.

    No consulta nada: son links a rutas que ya existen. Los contadores los
    rellena main.js con /mensajes/notificaciones, el mismo endpoint que el
    resto de la navegacion.
    """
    return render_template("profile/cuenta.html", user=g.user)
