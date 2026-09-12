"""Las rutas de las oportunidades: HTTP y nada mas.

Las decisiones viven en reglas.py y las consultas en consultas.py; aca solo se
traduce request -> dominio -> template.

PERMISOS, 100% DEL LADO DEL SERVIDOR. Cada vista vuelve a preguntarle a
reglas.* con la fila que acaba de traer de la base. No alcanza con no dibujar
el boton: la URL se escribe a mano, y esconder el HTML no es un permiso (es lo
que se arreglo en B4).

Dos formas de negar, con el mismo criterio que app/servicios/vistas.py:

  - abort(403) para las acciones del autor (aceptar, reabrir, finalizar). No es
    "volvé a tu panel": es alguien pidiendo una accion sobre algo ajeno.
  - abort(404) para una oportunidad finalizada que no es propia. Para el resto
    del mundo dejo de existir, y un 403 confirmaria que existe.
"""

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for,
)
from sqlalchemy.exc import IntegrityError

from app.blog.consultas import post_por_id_o_404
from app.oportunidades import consultas, formulario, reglas
from app.oportunidades.modelo_oportunidad import EstadosOportunidad, Oportunidad
from app.oportunidades.modelo_propuesta import Propuesta
from app.panel.consultas import contadores_de as contadores_del_panel
from db import utcnow
from services.eventos import hoy_en_argentina
from views.auth import login_required

oportunidades = Blueprint(
    "oportunidades", __name__, url_prefix="/oportunidades",
    template_folder="templates",
)


# --------------------------------------------------------------- lo publico

@oportunidades.route("/")
def index():
    """El listado publico: todo lo que esta abierto, sin filtro de rubro.

    Una lista unica y no categorizada, a proposito en esta version. El conteo
    de propuestas sale de UNA consulta agrupada y no de un COUNT por fila.

    Sin @login_required: la lista se ve sin sesion, como la cartelera. Publicar
    y proponer si la piden.
    """
    abiertas = consultas.abiertas()
    return render_template(
        "oportunidades/index.html",
        oportunidades=abiertas,
        conteo=consultas.conteo_de_propuestas([o.id for o in abiertas]),
    )


@oportunidades.route("/<int:id>")
def detalle(id):
    """La ficha de una oportunidad.

    Quien la publico ve las propuestas recibidas y los botones de decidir;
    cualquier otro ve la oportunidad y, si es emprendedor, el formulario para
    proponer.
    """
    oportunidad = consultas.oportunidad_por_id_o_404(id)

    user_id = g.user.id if g.user else None
    if not reglas.puede_ver(oportunidad, user_id):
        # Finalizada y ajena: para el que la mira dejo de existir.
        abort(404)

    es_autor = reglas.es_autor_de(oportunidad, user_id)
    return render_template(
        "oportunidades/detalle.html",
        oportunidad=oportunidad,
        es_autor=es_autor,
        # Las propuestas las ve solo quien publico. Es la decision de negocio y
        # ademas la de privacidad: un emprendedor no ve lo que cotizaron los
        # demas, que si no cotizar seria mirar el precio del otro.
        grupos=consultas.propuestas_de(oportunidad.id) if es_autor else [],
        # Desde que emprendimiento podria proponer, si tiene alguno. Vacio
        # significa que no es emprendedor, que es la mitad asimetrica del
        # dominio (ver reglas.py).
        mis_posts=consultas.posts_de(user_id) if user_id and not es_autor else [],
        datos={"precio": "", "plazo_dias": "", "mensaje": ""},
    )


# ------------------------------------------------------------ el publicador

@oportunidades.route("/publicar", methods=("GET", "POST"))
@login_required
def publicar():
    """Publica una oportunidad nueva.

    CUALQUIER USUARIO CON EL PERFIL COMPLETO, sin necesidad de tener un
    emprendimiento: el que pide un servicio no tiene por que ofrecer ninguno.
    Es la mitad asimetrica del dominio, y la otra mitad (proponer) si exige un
    Post.
    """
    if not reglas.puede_publicar(g.user):
        # No es un peaje decorativo: sin telefono ni ubicacion, el emprendedor
        # que quiera tomar el trabajo no puede contestar ni saber si le queda
        # cerca. Se dice QUE falta, no "completá tu perfil" a secas.
        falta = reglas.falta_de_perfil(g.user)
        flash(
            "Antes de publicar completá " + " y ".join(falta) +
            " en tu perfil, así te pueden responder."
        )
        return redirect(url_for("profile.edit_contacto"))

    vacio = {"titulo": "", "descripcion": "", "presupuesto": "", "fecha_limite": ""}

    if request.method == "POST":
        datos, error, presupuesto, fecha_limite = formulario.leer_oportunidad(
            hoy_en_argentina()
        )
        if error:
            flash(error)
            return render_template("oportunidades/publicar.html", datos=datos)

        oportunidad = Oportunidad(
            autor_id=g.user.id,
            titulo=datos["titulo"],
            descripcion=datos["descripcion"],
            presupuesto=presupuesto,
            fecha_limite=fecha_limite,
            estado=EstadosOportunidad.ABIERTA,
        )
        consultas.guardar(oportunidad)
        flash("Listo, tu necesidad ya está publicada.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    return render_template("oportunidades/publicar.html", datos=vacio)


@oportunidades.route("/mias")
@login_required
def mias():
    """El historial de quien publica: abiertas, cerradas y finalizadas.

    La finalizada salio del listado publico pero no se borro, y aca la sigue
    viendo. El conteo de propuestas sale de UNA consulta agrupada.
    """
    propias = consultas.de_usuario(g.user.id)
    return render_template(
        "oportunidades/mias.html",
        oportunidades=propias,
        conteo=consultas.conteo_de_propuestas([o.id for o in propias]),
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )


@oportunidades.route("/<int:id>/aceptar/<int:propuesta_id>", methods=("POST",))
@login_required
def aceptar(id, propuesta_id):
    """Acepta una propuesta: la oportunidad pasa a cerrada y se abre el chat.

    Tres cosas en la misma transaccion: la propuesta queda aceptada, la
    oportunidad pasa a cerrada y se sella cerrada_at. Si algo falla, no queda
    ni media.

    EL CHAT NO SE CREA, SE ABRE. La conversacion ya se identifica por
    (post_id, client_id) en messages, asi que aceptar redirige a
    messages.conversation y el hilo aparece cuando alguien escribe. No se
    inserta ningun Message: un mensaje automatico seria texto que nadie
    escribio.
    """
    oportunidad = consultas.oportunidad_por_id_o_404(id)
    propuesta = consultas.propuesta_por_id_o_404(propuesta_id)

    if not reglas.puede_aceptar(oportunidad, propuesta, g.user.id):
        if not reglas.es_autor_de(oportunidad, g.user.id):
            abort(403)
        # Es suya pero no se puede: o ya cerro, o el id de la propuesta es de
        # otra oportunidad. Las dos se cuentan, no se disfrazan de un 403.
        flash("Esa propuesta no se puede aceptar.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    propuesta.aceptada = True
    oportunidad.estado = EstadosOportunidad.CERRADA
    oportunidad.cerrada_at = utcnow()
    try:
        consultas.guardar()
    except IntegrityError as choque:
        consultas.descartar()
        if not reglas.es_aceptada_duplicada(choque):
            # Cualquier otra violacion de integridad no es este caso y no se
            # disfraza de este caso: sube y se ve como el error que es.
            raise
        # Perdio la carrera: otro POST identico (el doble click) llego junto
        # con este y el UNIQUE lo rechazo. Para el usuario el resultado es el
        # mismo que queria, asi que termina igual.
        flash("Ya habías aceptado una propuesta.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    flash("Aceptaste la propuesta. Escribile para coordinar.")
    return redirect(url_for(
        "messages.conversation",
        post_id=propuesta.post_id, client_id=oportunidad.autor_id,
    ))


@oportunidades.route("/<int:id>/reabrir", methods=("POST",))
@login_required
def reabrir(id):
    """Vuelve a abrir una oportunidad cerrada.

    LAS PROPUESTAS NO SE TOCAN: siguen todas, y siguen elegibles. Lo unico que
    se desmarca es cual estaba aceptada, y cerrada_at vuelve a NULL porque
    describe el cierre actual y no la historia.

    Es al reves que BusquedaPersonal, donde reabrir crea una fila nueva, y la
    diferencia no es un capricho: alla el UNIQUE era (busqueda_id,
    postulante_id), asi que reactivar la fila vieja dejaba bloqueado a todo el
    que ya se habia postulado. Aca no hay ningun unique por emprendimiento, asi
    que reusar la misma fila no bloquea a nadie.
    """
    oportunidad = consultas.oportunidad_por_id_o_404(id)
    if not reglas.es_autor_de(oportunidad, g.user.id):
        abort(403)
    if not reglas.puede_reabrir(oportunidad, g.user.id):
        # Abierta ya esta, y finalizada no vuelve: es la diferencia entre los
        # dos estados y la unica puerta que no tiene vuelta.
        flash("Esa oportunidad no se puede reabrir.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    aceptada = consultas.propuesta_aceptada_de(oportunidad.id)
    if aceptada:
        aceptada.aceptada = False
    oportunidad.estado = EstadosOportunidad.ABIERTA
    oportunidad.cerrada_at = None
    consultas.guardar()

    flash("La reabriste. Las propuestas que recibiste siguen acá.")
    return redirect(url_for("oportunidades.detalle", id=oportunidad.id))


@oportunidades.route("/<int:id>/finalizar", methods=("POST",))
@login_required
def finalizar(id):
    """Da por terminada una oportunidad. No tiene vuelta.

    Sale del listado publico y del alcance de cualquiera que no sea su autor,
    pero no se borra: quien la publico la sigue viendo en su historial, con las
    propuestas que recibio.

    Se puede finalizar desde abierta o desde cerrada: se da por terminado tanto
    lo que se resolvio como lo que nunca encontro a nadie.
    """
    oportunidad = consultas.oportunidad_por_id_o_404(id)
    if not reglas.es_autor_de(oportunidad, g.user.id):
        abort(403)
    if not reglas.puede_finalizar(oportunidad, g.user.id):
        flash("Esa oportunidad ya estaba finalizada.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    oportunidad.estado = EstadosOportunidad.FINALIZADA
    oportunidad.finalizada_at = utcnow()
    consultas.guardar()

    flash("La diste por terminada. Queda en tu historial.")
    return redirect(url_for("oportunidades.mias"))


# ------------------------------------------------------------ el emprendedor

@oportunidades.route("/<int:id>/proponer", methods=("POST",))
@login_required
def proponer(id):
    """Manda una propuesta sobre una oportunidad, desde un emprendimiento.

    SOLO UN EMPRENDEDOR, y desde un post suyo: el post_id llega del formulario
    y se vuelve a chequear contra la base (reglas.puede_proponer). Esa es la
    mitad asimetrica del dominio -- publicar no pide emprendimiento, proponer
    si.

    Se permiten VARIAS del mismo emprendimiento, a proposito: "hablamos y te
    bajo el precio" es el caso real, y la segunda es informacion nueva. La
    pantalla del publicador las agrupa para que insistir no infle la presencia
    (ver consultas.propuestas_de).
    """
    oportunidad = consultas.oportunidad_por_id_o_404(id)
    post = post_por_id_o_404(request.form.get("post_id", type=int) or 0)

    if not reglas.puede_proponer(oportunidad, post, g.user.id):
        if not reglas.es_dueño_de(post, g.user.id):
            # Un emprendimiento ajeno: no es "esto esta cerrado", es alguien
            # proponiendo en nombre de otro.
            abort(403)
        flash("Esa oportunidad no está recibiendo propuestas.")
        return redirect(url_for("oportunidades.detalle", id=oportunidad.id))

    datos, error, precio, plazo_dias = formulario.leer_propuesta()
    if error:
        flash(error)
        return render_template(
            "oportunidades/detalle.html",
            oportunidad=oportunidad, es_autor=False, grupos=[],
            mis_posts=consultas.posts_de(g.user.id), datos=datos,
        )

    propuesta = Propuesta(
        oportunidad_id=oportunidad.id, post_id=post.id,
        precio=precio, plazo_dias=plazo_dias, mensaje=datos["mensaje"],
    )
    consultas.guardar(propuesta)

    flash("Mandamos tu propuesta. Si le interesa, te escribe por acá.")
    return redirect(url_for("oportunidades.detalle", id=oportunidad.id))


@oportunidades.route("/mis-propuestas")
@login_required
def mis_propuestas():
    """Lo que ofrecieron los emprendimientos de esa persona, y en que quedo."""
    return render_template(
        "oportunidades/mis_propuestas.html",
        propuestas=consultas.propuestas_de_usuario(g.user.id),
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )
