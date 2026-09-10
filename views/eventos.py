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

from app.panel.consultas import contadores_de as contadores_del_panel
from db import db
from models.event import Event, TiposEvento
from app.blog.modelo_post import Post
from services.eventos import (
    agrupar_por_mes, del_dia, filtrar, hoy_en_argentina, parsear_fecha,
    pasados, proximos, tipo_valido,
)
from services.horarios import formatear as formatear_hora, parsear_hora
from views.auth import login_required

eventos = Blueprint("eventos", __name__, url_prefix="/eventos")


@eventos.route("/")
def index():
    """Cartelera publica, con los tres filtros de la barra y el del calendario.

    Paginada con el mismo criterio que blog.index: traer todo con .all() se
    rompe solo cuando la cartelera crece. El joinedload trae el emprendimiento
    en la misma consulta (y con el su autor, que ya es lazy="joined"), para no
    disparar un SELECT por evento al armar el link al perfil (problema N+1).

    LOS FILTROS SON PARAMETROS DE LA URL Y NO ESTADO DE JAVASCRIPT (?dia=,
    ?tipo=, ?libre=), igual que los del catalogo: una cartelera filtrada se
    comparte por link, vuelve con el boton de atras y anda sin JS. El
    calendario del costado gana asi la funcion que le faltaba -- hasta ahora
    pintaba los dias con eventos y ahi terminaba.

    EL DIA MANDA SOBRE "TODAVIA NO PASO". Elegir una fecha en el calendario
    muestra ESE dia, aunque ya haya pasado: el calendario navega meses para
    atras, y esconder lo vencido dejaria esos meses vacios. Sin dia elegido, la
    cartelera es lo que viene, que es para lo que se entra.
    """
    dia = parsear_fecha(request.args.get("dia"))
    tipo = tipo_valido(request.args.get("tipo"))
    solo_libres = request.args.get("libre") == "1"

    query = filtrar(
        Event.query.options(joinedload(Event.post)), tipo, solo_libres
    )
    query = del_dia(query, dia) if dia else proximos(query)

    paginacion = query.paginate(
        page=request.args.get("page", 1, type=int),
        per_page=current_app.config["POSTS_POR_PAGINA"],
        error_out=False,
    )
    # La base a la que el calendario le pega "dia=AAAA-MM-DD" atras. Se arma
    # aca y no en la plantilla porque hay que saber si url_for ya puso un "?"
    # (lo pone solo si algun filtro sobrevivio), y eso en Jinja seria pegar
    # strings a mano. Lleva los OTROS filtros y no el dia: elegir una fecha no
    # tiene que soltar el tipo que ya estaba puesto.
    base = url_for("eventos.index", tipo=tipo, libre="1" if solo_libres else None)
    enlace_dia = base + ("&" if "?" in base else "?")

    filtrando = bool(dia or tipo or solo_libres)

    # TRES VACIOS Y NO DOS, y el tercero es el que faltaba. Con filtros puestos,
    # "no hay eventos" seria mentira porque los hay mas adelante. Sin filtros y
    # con la base vacia, es cierto. Pero falta el caso del medio: SIN filtros,
    # con eventos cargados y todos ya vencidos, proximos() vuelve vacio y decir
    # "todavia no hay eventos anunciados" tambien es mentira -- hubo, ya
    # pasaron, y el calendario de al lado les sigue pintando el puntito, asi que
    # la pantalla se contradecia sola. Los eventos pasados no se borran nunca
    # (la cartelera solo los esconde), asi que este es el estado normal de una
    # cartelera en temporada baja, no un caso raro.
    #
    # La consulta extra solo se hace con la pagina vacia y sin filtros, que es
    # el unico momento en que su respuesta cambia algo.
    hay_eventos = (
        db.session.query(Event.query.exists()).scalar()
        if not paginacion.items and not filtrando
        else True
    )

    # Agrupados por mes para los encabezados de la cartelera. Se agrupa la
    # pagina y no el total: un mes puede quedar partido entre dos paginas, que
    # es lo mismo que ya pasa con cualquier corte por fecha.
    return render_template(
        "eventos/index.html",
        enlace_dia=enlace_dia,
        paginacion=paginacion,
        meses=agrupar_por_mes(paginacion.items),
        dia=dia,
        tipo=tipo,
        solo_libres=solo_libres,
        filtrando=filtrando,
        hay_eventos=hay_eventos,
        tipos=TiposEvento,
    )


@eventos.route("/mios")
@login_required
def mios():
    """Los eventos de los emprendimientos propios, para el panel del vendedor.

    Es la pantalla que le faltaba al item "Eventos y ferias" del menu del
    panel, y por eso quedo afuera de la tanda anterior: hasta ahora un evento
    se cargaba y se editaba desde la ficha de cada emprendimiento, y /eventos
    es la cartelera publica de todos. Quien tiene tres emprendimientos no tenia
    ningun lado donde ver sus fechas juntas.

    Proximos y pasados, como en "mis turnos" y por lo mismo: lo que hay que
    mirar es lo que viene, y el historial se repasa. Los dos ordenes ya los
    resuelven proximos() y pasados() -- creciente uno, decreciente el otro --
    asi que aca no se da vuelta nada.
    """
    hoy = hoy_en_argentina()
    de_sus_posts = Event.query.join(Post, Post.id == Event.post_id).filter(
        Post.author == g.user.id
    ).options(joinedload(Event.post))

    return render_template(
        "eventos/mios.html",
        proximos=proximos(de_sus_posts, hoy).all(),
        pasados=pasados(de_sus_posts, hoy).all(),
        contadores=contadores_del_panel(g.user.id, hoy),
        tipos=TiposEvento,
    )


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
    lugar = (request.form.get("lugar") or "").strip()
    fecha_texto = (request.form.get("fecha") or "").strip()
    hora_texto = (request.form.get("hora") or "").strip()
    tipo_texto = (request.form.get("tipo") or "").strip()
    entrada_libre = request.form.get("entrada_libre") == "1"

    fecha = parsear_fecha(fecha_texto)
    hora = parsear_hora(hora_texto)
    tipo = tipo_valido(tipo_texto)

    error = None
    if not titulo:
        error = "Se requiere un título para el evento."
    # EL TIPO SE EXIGE EN EL FORMULARIO aunque la columna sea nullable, y las
    # dos cosas son ciertas a la vez: NULL existe para los eventos que se
    # cargaron antes de que la columna existiera, no para los nuevos. Si no se
    # exigiera, el NULL nunca se agotaria y el filtro por tipo dejaria de
    # servir.
    elif tipo is None:
        error = "Elegí qué tipo de evento es."
    elif not fecha_texto:
        error = "Se requiere una fecha."
    elif fecha is None:
        error = "La fecha no es válida."
    elif hora_texto and hora is None:
        error = "La hora no es válida. Usá el formato HH:MM."

    # Se devuelve lo que escribio el usuario (los textos crudos) y no lo
    # parseado: si la fecha estaba mal, el formulario tiene que volver con lo
    # que puso, no vacio. El tipo es la excepcion y va ya validado: un valor
    # que no es ninguno de los cuatro no se puede repintar en un segmentado de
    # cuatro botones, asi que vuelve sin nada elegido.
    datos = {
        "titulo": titulo, "descripcion": descripcion, "lugar": lugar,
        "fecha": fecha_texto, "hora": hora_texto,
        "tipo": tipo, "entrada_libre": entrada_libre,
    }
    return (datos, titulo, descripcion, lugar, fecha, hora, tipo,
            entrada_libre, error)


@eventos.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Publicar un evento en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder publicar eventos.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        (datos, titulo, descripcion, lugar, fecha, hora, tipo,
         entrada_libre, error) = _leer_formulario()
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
                "eventos/form.html", posts=posts, datos=datos, evento=None,
                tipos=TiposEvento,
            )

        db.session.add(Event(
            post_id=post_id, titulo=titulo,
            descripcion=descripcion or None, lugar=lugar or None,
            fecha=fecha, hora=hora, tipo=tipo, entrada_libre=entrada_libre,
        ))
        db.session.commit()
        flash("Evento publicado correctamente.")
        return redirect(url_for("eventos.mios"))

    datos = {
        "titulo": "", "descripcion": "", "lugar": "",
        "fecha": "", "hora": "", "post_id": None,
        # Sin tipo elegido: los cuatro son igual de probables y elegir uno por
        # el usuario lo haria publicar ferias sin darse cuenta.
        "tipo": None, "entrada_libre": False,
    }
    return render_template("eventos/form.html", posts=posts, datos=datos,
                           evento=None, tipos=TiposEvento)


@eventos.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un evento propio."""
    evento, rechazo = _evento_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        (datos, titulo, descripcion, lugar, fecha, hora, tipo,
         entrada_libre, error) = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error:
            flash(error)
            return render_template(
                "eventos/form.html", posts=posts, datos=datos, evento=evento,
                tipos=TiposEvento,
            )

        evento.post_id = post_id
        evento.titulo = titulo
        evento.descripcion = descripcion or None
        evento.lugar = lugar or None
        evento.fecha = fecha
        evento.hora = hora
        evento.tipo = tipo
        evento.entrada_libre = entrada_libre
        db.session.commit()
        flash("Evento actualizado correctamente.")
        return redirect(url_for("eventos.mios"))

    datos = {
        "titulo": evento.titulo,
        "descripcion": evento.descripcion or "",
        "lugar": evento.lugar or "",
        "fecha": evento.fecha.isoformat(),
        "hora": formatear_hora(evento.hora),
        "post_id": evento.post_id,
        "tipo": evento.tipo,
        "entrada_libre": evento.entrada_libre,
    }
    return render_template("eventos/form.html", posts=posts, datos=datos,
                           evento=evento, tipos=TiposEvento)


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
    return redirect(url_for("eventos.mios"))
