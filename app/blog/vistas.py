"""Las rutas del dominio: HTTP y nada mas.

Lo que queda aca es lo que solo se puede hacer con un request delante: leer el
formulario, elegir el mensaje, redirigir o renderizar. Las decisiones estan en
reglas.py y las consultas en consultas.py, asi que estas funciones se leen como
el guion de la pantalla.

El chequeo de permiso va en la vista y no solo en el template: esconder un boton
no es un permiso, cualquiera puede mandar el POST a mano.

El blueprint se sigue llamando "blog" y sigue colgando de /blog: los url_for de
todos los templates lo nombran asi, y renombrarlo es otra tanda. Trae su propio
template_folder, con lo cual las plantillas del dominio viajan con el codigo del
dominio (base.html y los partials siguen saliendo de la carpeta global de la
app).

_guardar_galeria() no es una ruta y tampoco entra limpia en ninguna de las
otras tres capas: escribe archivos en disco y ademas deja filas pendientes en
la sesion (cuelga PostImage de post.imagenes, y el autoflush las empuja en la
primera consulta que venga despues, por eso los dos branches de error llaman a
consultas.descartar()). Esta aca por ser el unico lugar desde donde se la
llama; el comentario largo esta sobre la funcion.
"""

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request,
    url_for
)
from sqlalchemy.exc import IntegrityError

from app.blog import consultas, formulario, reglas
from app.blog.modelo_favorito import Favorite
from app.blog.modelo_imagen import PostImage
from app.blog.modelo_post import MAX_IMAGENES_POR_POST, Categorias, Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from db import utcnow
from services.geocoding import get_coordinates_from_address
from services.horarios import ETIQUETAS_DIAS, esta_abierto
from services.ratings import serializar_con_rating
from services.uploads import borrar_de_disco, carpeta_uploads, save_post_image
from views.auth import login_required

blog = Blueprint("blog", __name__, url_prefix="/blog", template_folder="templates")


def get_post(id, check_author=True):
    """Obtener post por ID y validar autor si corresponde.

    Devuelve el post, o el redirect ya armado si el usuario no es el autor.
    Sigue viviendo en la vista, y no en consultas.py, justamente porque puede
    devolver una respuesta HTTP en vez de una fila.
    """
    post = consultas.post_por_id(id)
    if post is None:
        abort(404, f"id {id} de la publicación no existe.")
    if check_author and not reglas.es_el_autor(post, g.user.id):
        flash("No tenés permiso para acceder a este emprendimiento.")
        return redirect(url_for("blog.my_posts"))
    return post


def _post_propio(id, accion):
    """El post con ese id si el usuario actual puede tocarlo.

    Devuelve (post, None) si puede, o (None, respuesta) con el redirect ya
    armado si no. `accion` es el verbo que va en el mensaje ("editar",
    "eliminar"), que es lo unico que cambiaba entre las copias de este chequeo.
    """
    post = consultas.post_por_id_o_404(id)
    if not reglas.es_el_autor(post, g.user.id):
        flash(f"No tenés permiso para {accion} este emprendimiento.")
        return None, redirect(url_for("blog.my_posts"))
    return post, None


def _guardar_galeria(post, archivos, upload_dir, ya_ocupados):
    """Guarda las fotos adicionales de un emprendimiento.

    Reusa save_post_image, o sea que cada foto pasa por la misma validacion,
    compresion y nombre con uuid que la principal. Devuelve un mensaje de error
    si alguna no se pudo guardar, o None.

    `ya_ocupados` es cuantos lugares gasta lo que ya tiene el post (la foto
    principal y las que subio antes).
    """
    archivos = [f for f in archivos if f and f.filename]
    if not archivos:
        return None

    if not reglas.entran_las_fotos(len(archivos), ya_ocupados):
        return (
            f"Podés subir hasta {MAX_IMAGENES_POR_POST} fotos por emprendimiento "
            f"(te quedan {reglas.lugares_libres(ya_ocupados)})."
        )

    # save_post_image valida y escribe en el mismo paso, asi que no se puede
    # validar todo primero. Se lleva registro de lo escrito en ESTE intento
    # para poder borrarlo si una foto posterior falla: sin eso, subir cinco
    # fotos con la tercera rota dejaba las dos primeras en disco para siempre,
    # sin ninguna fila que las referenciara (el rollback solo deshace la base).
    escritos = []
    for numero, archivo in enumerate(archivos, start=ya_ocupados):
        filename, error = save_post_image(archivo, upload_dir)
        if error:
            borrar_de_disco(upload_dir, escritos)
            return error
        if filename:
            escritos.append(filename)
            post.imagenes.append(PostImage(filename=filename, posicion=numero))
    return None


# ------------------------------------------------------------ rutas publicas

@blog.route("/")
def index():
    """Lista pública de emprendimientos, paginada, con busqueda y filtro por categoria."""
    busqueda = formulario.leer_busqueda()
    categoria = formulario.leer_categoria_de_filtro()
    cerca_de, lat, lon = formulario.leer_cercania()

    # Geocodificar es una llamada a MapTiler: se hace solo si el usuario mando
    # una direccion en texto y no las coordenadas ya resueltas.
    if cerca_de and lat is None and lon is None:
        lat, lon = get_coordinates_from_address(
            cerca_de, current_app.config["MAPTILER_KEY"]
        )
        if lat is None:
            flash("No pudimos ubicar esa dirección en el mapa. Probá con otro formato, o dejá el campo vacío.")

    paginacion, ordenado_por_distancia = consultas.buscar_posts(
        busqueda=busqueda,
        # Una categoria que no existe no filtra nada, pero se le devuelve igual
        # al template para repintar el <select> con lo que el usuario tenia.
        categoria=categoria if reglas.categoria_valida(categoria) else None,
        lat=lat,
        lon=lon,
        pagina=formulario.leer_pagina(),
        por_pagina=current_app.config["POSTS_POR_PAGINA"],
    )

    favoritos = consultas.ids_favoritos(g.user.id) if g.user else frozenset()
    if ordenado_por_distancia:
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
        ordenado_por_distancia=ordenado_por_distancia,
        # Los numeros que van al lado de cada rubro en la columna de filtros.
        # Son de toda la plataforma y no de la busqueda actual, a proposito:
        # dicen cuanto hay si te movés a ese rubro, que es para lo que se
        # miran.
        conteo_por_categoria=consultas.conteo_por_categoria(),
    )


@blog.route("/<int:id>")
def detail(id):
    """Detalle de un emprendimiento + reseñas."""
    post = consultas.post_por_id_o_404(id)
    es_dueño = bool(g.user and reglas.es_el_autor(post, g.user.id))

    # No cuenta las vistas del propio dueño revisando su publicacion.
    if not es_dueño:
        post.views_count += 1
        consultas.guardar()

    return render_template(
        "blog/detail.html",
        post=post,
        author=post.author_user,
        reviews=consultas.resenias_de(id),
        avg_rating=consultas.promedio_de_rating(id),
        # La reseña propia (si existe) se usa para precargar el formulario en
        # modo edicion, en vez de mostrar siempre el formulario vacio de "dejar
        # una reseña" aunque el usuario ya haya dejado la suya.
        mi_review=consultas.resenia_de(id, g.user.id) if g.user else None,
        is_favorite=(
            g.user is not None
            and consultas.favorito_de(g.user.id, id) is not None
        ),
        productos=consultas.productos_de(id, solo_disponibles=not es_dueño),
        servicios=consultas.servicios_de(id, solo_disponibles=not es_dueño),
        es_dueño=es_dueño,
        # Los horarios son del emprendedor, no del emprendimiento (viven en
        # User): la columna lateral del rediseño los muestra junto con si esta
        # abierto ahora, que lo calcula services/horarios con el reloj de
        # Argentina y no con el del visitante.
        horarios=sorted(post.author_user.horarios, key=lambda h: h.dia_semana),
        abierto=esta_abierto(post.author_user.horarios),
        etiquetas_dias=ETIQUETAS_DIAS,
        MAPTILER_KEY=current_app.config["MAPTILER_KEY"],
    )


# --------------------------------------------- rutas privadas (con sesion)

@blog.route("/mis-emprendimientos")
@login_required
def my_posts():
    """Listado de emprendimientos del usuario actual, paginado."""
    paginacion = consultas.posts_de(
        g.user.id,
        pagina=formulario.leer_pagina(),
        por_pagina=current_app.config["POSTS_POR_PAGINA"],
    )

    # Las tres metricas que el rediseño muestra en cada fila. Se arman aca y no
    # en el template para que la plantilla no dispare consultas mientras
    # renderiza: son las relaciones del post, una pagina por vez.
    #
    # Se piden de una sola vez para TODA la pagina (una consulta agrupada, no
    # una por fila): leerlas de cada post en el bucle -- post.reviews.count(),
    # len(post.productos), len(post.servicios) -- eran cuatro consultas por
    # emprendimiento. Las vistas no salen de ahi porque views_count es una
    # columna del propio post, que ya vino en el listado.
    metricas = consultas.metricas_de_posts([post.id for post in paginacion.items])
    posts = [
        {
            "post": post,
            "vistas": post.views_count,
            **metricas[post.id],
        }
        for post in paginacion.items
    ]

    return render_template(
        "blog/my_posts.html", posts=posts, paginacion=paginacion
    )


@blog.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Registrar un nuevo emprendimiento."""
    if request.method == "POST":
        valores, archivos, error = formulario.leer_post()
        filename = None

        # El limite se chequea antes de tocar el disco: si se pasa, no tiene
        # sentido haber guardado y comprimido las fotos para despues descartarlas.
        if error is None and not reglas.entran_las_fotos(
            formulario.contar_fotos(archivos)
        ):
            error = f"Podés subir hasta {MAX_IMAGENES_POR_POST} fotos por emprendimiento."

        if error is None:
            upload_dir = carpeta_uploads()
            filename, error = save_post_image(archivos["imagen"], upload_dir)

        if error:
            flash(error)
        else:
            latitude, longitude = _geocodificar(valores["address_street"])

            post = Post(
                author=g.user.id,
                title=valores["title"],
                body=valores["body"],
                image=filename,
                latitude=latitude,
                longitude=longitude,
                address_street=valores["address_street"] or None,
                category=valores["category"],
            )

            galeria_error = _guardar_galeria(
                post, archivos["galeria"], upload_dir,
                ya_ocupados=1 if filename else 0,
            )
            if galeria_error:
                consultas.descartar()
                # La galeria ya borro lo suyo; falta la principal, que se
                # escribio antes y se queda sin post que la referencie.
                borrar_de_disco(upload_dir, [filename])
                flash(galeria_error)
                return render_template("blog/create.html", categorias=Categorias.ETIQUETAS)

            consultas.guardar(post)
            flash("Emprendimiento registrado correctamente.")
            return redirect(url_for("blog.my_posts"))

    return render_template("blog/create.html", categorias=Categorias.ETIQUETAS)


def _geocodificar(direccion):
    """Las coordenadas de esa direccion, o (None, None) si no se pudo.

    Avisa por flash cuando falla: el alta sigue adelante sin ubicacion, que es
    mejor que perder todo lo que el usuario cargo por una direccion mal escrita.
    """
    if not direccion:
        return None, None

    latitude, longitude = get_coordinates_from_address(
        direccion, current_app.config["MAPTILER_KEY"]
    )
    if not latitude:
        flash("No se pudo encontrar la dirección en el mapa, pero el post se guardó sin ubicación. Revisá el formato de la dirección.")
    return latitude, longitude


@blog.route("/update/<int:id>", methods=("GET", "POST"))
@login_required
def update(id):
    """Actualizar emprendimiento existente."""
    post, denegado = _post_propio(id, "editar")
    if denegado:
        return denegado

    if request.method == "POST":
        # pedir_descripcion=False: la edicion nunca valido la descripcion.
        valores, archivos, error = formulario.leer_post(pedir_descripcion=False)
        latitude, longitude = post.latitude, post.longitude
        # Arranca en None para poder consultarla en el branch de error aunque
        # la validacion haya cortado antes de llegar a guardar la imagen.
        filename = None
        upload_dir = carpeta_uploads()

        # Imagen nueva (si no se sube ninguna, se conserva la que ya tenia)
        if error is None:
            filename, error = save_post_image(archivos["imagen"], upload_dir)
            if error is None and filename:
                post.image = filename

        # Las fotos que ya tenia siguen contando para el limite: se suman a las
        # nuevas en vez de reemplazarlas.
        if error is None:
            error = _guardar_galeria(
                post, archivos["galeria"], upload_dir,
                ya_ocupados=len(post.galeria),
            )

        if error:
            # Descarta lo que quedo pendiente en la sesion (la imagen principal
            # nueva, las fotos de galeria ya agregadas). Sin esto un autoflush
            # posterior puede terminar guardando una edicion que se rechazo.
            consultas.descartar()
            # Y lo que ya se habia escrito en disco: la edicion no se guardo,
            # asi que la imagen principal nueva no la referencia nadie.
            borrar_de_disco(upload_dir, [filename])
            flash(error)
        else:
            # Solo geocodificamos si la direccion cambio.
            if valores["address_street"] != post.address_street:
                if valores["address_street"]:
                    latitude, longitude = get_coordinates_from_address(
                        valores["address_street"], current_app.config["MAPTILER_KEY"]
                    )
                    if not latitude:
                        flash("No se pudo encontrar la nueva dirección, se mantuvo la anterior.")
                        latitude, longitude = post.latitude, post.longitude
                else:
                    # El usuario borró la dirección
                    latitude, longitude = None, None

            post.title = valores["title"]
            post.body = valores["body"]
            post.latitude = latitude
            post.longitude = longitude
            post.address_street = valores["address_street"] or None
            if reglas.categoria_valida(valores["category"]):
                post.category = valores["category"]

            consultas.guardar()
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
    post, denegado = _post_propio(id, "eliminar")
    if denegado:
        return denegado

    try:
        consultas.borrar(post)
        flash("Emprendimiento eliminado correctamente.")
    except Exception:
        consultas.descartar()
        current_app.logger.exception("Error al eliminar el post %s", id)
        flash("Error al eliminar el emprendimiento.")
    return redirect(url_for("blog.my_posts"))


# ------------------------------------------------------------------ resenias

@blog.route("/<int:id>/review", methods=["POST"])
@login_required
def add_review(id):
    """Agregar una reseña (rating + comentario) a un emprendimiento."""
    post = consultas.post_por_id_o_404(id)

    if not reglas.puede_resenar(post, g.user.id):
        flash("No podés dejar una reseña sobre tu propio emprendimiento.")
        return redirect(url_for("blog.detail", id=id))

    rating, comentario, error = formulario.leer_resenia()
    if error:
        flash(error)
        return redirect(url_for("blog.detail", id=id))

    # Un usuario tiene una sola resena por emprendimiento (lo garantiza un
    # UniqueConstraint). Si ya dejo una, esta la actualiza en vez de fallar.
    review = consultas.resenia_de(id, g.user.id)

    try:
        if review is None:
            review = Review(
                post_id=id, user_id=g.user.id, rating=rating, comment=comentario
            )
            consultas.guardar(review)
            flash("¡Gracias por tu reseña!")
        else:
            review.rating = rating
            review.comment = comentario
            review.updated_at = utcnow()
            # La respuesta del dueño quedo escrita para el contenido viejo:
            # si no se limpia, parece que responde a algo que la reseña ya
            # no dice. Se borra para forzar que responda de nuevo.
            if review.reply is not None:
                review.reply = None
                review.replied_at = None
            consultas.guardar()
            flash("Actualizamos tu reseña.")
    except IntegrityError:
        consultas.descartar()
        current_app.logger.exception("Error al guardar la resena del post %s", id)
        flash("No pudimos guardar tu reseña. Intentá de nuevo.")

    return redirect(url_for("blog.detail", id=id))


@blog.route("/review/<int:review_id>/reply", methods=["POST"])
@login_required
def reply_review(review_id):
    """El dueño del emprendimiento responde publicamente a una reseña."""
    review = consultas.resenia_por_id_o_404(review_id)

    if not reglas.puede_responder_la_resenia(review, g.user.id):
        flash("No tenés permiso para responder esta reseña.")
        return redirect(url_for("blog.detail", id=review.post_id))

    texto, error = formulario.leer_respuesta_a_resenia()
    if error:
        flash(error)
        return redirect(url_for("blog.detail", id=review.post_id))

    review.reply = texto
    review.replied_at = utcnow()
    consultas.guardar()
    flash("Tu respuesta se publicó correctamente.")

    return redirect(url_for("blog.detail", id=review.post_id))


@blog.route("/review/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    """Eliminar la propia reseña. Editarla ya se resuelve reenviando add_review,
    que actualiza en vez de duplicar (ver el UniqueConstraint de Review)."""
    review = consultas.resenia_por_id_o_404(review_id)

    if not reglas.es_el_autor_de_la_resenia(review, g.user.id):
        flash("No tenés permiso para eliminar esta reseña.")
        return redirect(url_for("blog.detail", id=review.post_id))

    post_id = review.post_id
    consultas.borrar(review)
    flash("Tu reseña se eliminó correctamente.")

    return redirect(url_for("blog.detail", id=post_id))


# ----------------------------------------------------------------- favoritos

@blog.route("/<int:id>/favorito", methods=["POST"])
@login_required
def toggle_favorite(id):
    """Marca o desmarca un emprendimiento como favorito (toggle)."""
    post = consultas.post_por_id_o_404(id)

    favorito = consultas.favorito_de(g.user.id, post.id)
    if favorito:
        consultas.borrar(favorito)
        flash("Se quitó de tus favoritos.")
    else:
        try:
            consultas.guardar(Favorite(user_id=g.user.id, post_id=post.id))
            flash("Se agregó a tus favoritos.")
        except IntegrityError:
            # Ventana de carrera: dos clicks casi simultaneos en "favorito".
            consultas.descartar()

    return redirect(request.referrer or url_for("blog.detail", id=post.id))


@blog.route("/favoritos")
@login_required
def my_favorites():
    """Emprendimientos que el usuario marco como favoritos."""
    paginacion = consultas.favoritos_de(
        g.user.id,
        pagina=formulario.leer_pagina(),
        por_pagina=current_app.config["POSTS_POR_PAGINA"],
    )
    posts = serializar_con_rating(
        paginacion.items, favoritos=consultas.ids_favoritos(g.user.id)
    )
    return render_template("blog/favorites.html", posts=posts, paginacion=paginacion)


# ------------------------------------------------------------------ reportes

@blog.route("/reportar/<string:tipo>/<int:target_id>", methods=("GET", "POST"))
@login_required
def report(tipo, target_id):
    """Reportar un emprendimiento o una reseña por contenido inapropiado.

    Alimenta al panel de admin (ver views/admin.py reportes()).
    """
    if not reglas.tipo_reportable(tipo):
        abort(404)

    if tipo == "post":
        objetivo = consultas.post_por_id_o_404(target_id)
        volver = url_for("blog.detail", id=target_id)
        mensaje_propio = "No podés reportar tu propio emprendimiento."
    else:
        objetivo = consultas.resenia_por_id_o_404(target_id)
        volver = url_for("blog.detail", id=objetivo.post_id)
        mensaje_propio = "No podés reportar tu propia reseña."

    if not reglas.puede_reportar(objetivo, tipo, g.user.id):
        flash(mensaje_propio)
        return redirect(volver)

    # Un solo reporte pendiente por usuario y objetivo. OJO: este chequeo es
    # para pintar el formulario y dar un mensaje claro, no es el que garantiza
    # la regla: entre este SELECT y el INSERT de mas abajo hay una ventana por
    # la que pasan dos requests simultaneos. Lo que de verdad lo impide es el
    # UNIQUE de la base (ver modelo_reporte.py), y su IntegrityError se maneja
    # abajo.
    ya_reportado = consultas.hay_reporte_pendiente(g.user.id, tipo, target_id)

    if request.method == "POST":
        if ya_reportado:
            flash("Ya tenés un reporte pendiente sobre esto. El equipo lo va a revisar.")
            return redirect(volver)

        motivo, error = formulario.leer_motivo_de_reporte()
        if error:
            flash(error)
        else:
            try:
                consultas.guardar(Report(
                    reporter_id=g.user.id,
                    post_id=target_id if tipo == "post" else None,
                    review_id=target_id if tipo == "review" else None,
                    reason=motivo,
                ))
            except IntegrityError as choque:
                consultas.descartar()
                if not reglas.es_reporte_duplicado(choque):
                    # Cualquier otra violacion de integridad no es este caso y
                    # no se disfraza de este caso: sube y se ve como el error
                    # que es.
                    raise
                # Perdio la carrera: otro envio identico llego junto con este y
                # el UNIQUE de la base lo rechazo. Para el usuario es el mismo
                # caso que atajo el chequeo de arriba, asi que termina igual.
                flash("Ya tenés un reporte pendiente sobre esto. El equipo lo va a revisar.")
                return redirect(volver)

            flash("Gracias, revisaremos tu reporte.")
            return redirect(volver)

    return render_template(
        "blog/report.html", tipo=tipo, objetivo=objetivo, volver=volver,
        ya_reportado=ya_reportado,
    )
