"""Las rutas de la busqueda de personal: HTTP y nada mas.

Tres pantallas y tres acciones. Las decisiones viven en reglas.py y las
consultas en consultas.py; aca solo se traduce request -> dominio -> template.

PERMISOS, 100% DEL LADO DEL SERVIDOR. Cada vista del dueño vuelve a preguntar
reglas.es_dueño_de(...) con la fila que acaba de traer de la base. No alcanza
con no dibujar el boton: la URL se escribe a mano, y esconder el HTML no es un
permiso (es lo que se arreglo en B4).
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for,
)
from sqlalchemy.exc import IntegrityError

from app.blog.consultas import post_por_id_o_404
from app.panel.consultas import contadores_de as contadores_del_panel
from app.personal import consultas, formulario, reglas
from app.personal.modelo_busqueda import BusquedaPersonal, Modalidades
from app.personal.modelo_postulacion import Postulacion
from db import utcnow
from services.eventos import hoy_en_argentina
from views.auth import login_required

personal = Blueprint(
    "personal", __name__, url_prefix="/personal", template_folder="templates"
)


# ------------------------------------------------------------------ el dueño

@personal.route("/emprendimiento/<int:post_id>/buscar", methods=("GET", "POST"))
@login_required
def activar(post_id):
    """Prende el toggle: crea la busqueda activa de ese emprendimiento."""
    post = post_por_id_o_404(post_id)
    if not reglas.es_dueño_de(post, g.user.id):
        flash("Ese emprendimiento no es tuyo.")
        return redirect(url_for("blog.detail", id=post.id))

    ya_activa = consultas.busqueda_activa_de(post.id)
    if ya_activa:
        # Para dar un mensaje claro y llevarlo a la que ya tiene. NO es lo que
        # garantiza la regla: entre este SELECT y el INSERT hay una ventana por
        # la que pasan dos requests simultaneos, y lo que de verdad la cierra
        # es el UNIQUE de la base (ver modelo_busqueda.py).
        flash("Ya tenés una búsqueda activa en ese emprendimiento.")
        return redirect(url_for("personal.postulantes", id=ya_activa.id))

    if request.method == "POST":
        datos, error = formulario.leer_busqueda()
        if error:
            flash(error)
            return render_template(
                "personal/activar.html", post=post, datos=datos,
                modalidades=Modalidades,
            )

        busqueda = BusquedaPersonal(
            post_id=post.id, puesto=datos["puesto"],
            modalidad=datos["modalidad"], descripcion=datos["descripcion"],
            activa=True,
        )
        try:
            consultas.guardar(busqueda)
        except IntegrityError as choque:
            consultas.descartar()
            if not reglas.es_activa_duplicada(choque):
                # Cualquier otra violacion de integridad no es este caso y no
                # se disfraza de este caso: sube y se ve como el error que es.
                raise
            # Perdio la carrera: otro request identico llego junto con este y
            # el UNIQUE lo rechazo. Para el usuario es el mismo caso que atajo
            # el chequeo de arriba, asi que termina igual.
            flash("Ya tenés una búsqueda activa en ese emprendimiento.")
            ya_activa = consultas.busqueda_activa_de(post.id)
            if ya_activa:
                return redirect(url_for("personal.postulantes", id=ya_activa.id))
            return redirect(url_for("blog.detail", id=post.id))

        flash("Listo, tu búsqueda ya aparece en la ficha del emprendimiento.")
        return redirect(url_for("personal.postulantes", id=busqueda.id))

    return render_template(
        "personal/activar.html", post=post,
        datos={"puesto": "", "modalidad": "", "descripcion": ""},
        modalidades=Modalidades,
    )


@personal.route("/<int:id>/cerrar", methods=("POST",))
@login_required
def cerrar(id):
    """Apaga el toggle. Las postulaciones recibidas NO se tocan.

    Cerrar sella cerrada_at y ahi termina la vida de esa fila. Volver a buscar
    personal crea una fila NUEVA y nunca reactiva esta: si se reactivara, todo
    el que se postulo a esta busqueda quedaria bloqueado por el UNIQUE de
    postulaciones frente a un aviso que nunca vio (ver modelo_busqueda.py).
    """
    busqueda = consultas.busqueda_por_id_o_404(id)
    if not reglas.es_dueño_de_la_busqueda(busqueda, g.user.id):
        flash("Esa búsqueda no es tuya.")
        return redirect(url_for("blog.detail", id=busqueda.post_id))

    if busqueda.activa:
        busqueda.activa = False
        busqueda.cerrada_at = utcnow()
        consultas.guardar()
        flash("Cerraste la búsqueda. Las postulaciones que recibiste siguen acá.")
    return redirect(url_for("personal.postulantes", id=busqueda.id))


@personal.route("/<int:id>/postulantes")
@login_required
def postulantes(id):
    """La bandeja de una busqueda: quienes se postularon.

    Solo el dueño del emprendimiento. Se vuelve a preguntar aca con la fila de
    la base, no se confia en que el enlace solo aparezca en su panel.
    """
    busqueda = consultas.busqueda_por_id_o_404(id)
    if not reglas.es_dueño_de_la_busqueda(busqueda, g.user.id):
        flash("Esa búsqueda no es tuya.")
        return redirect(url_for("blog.detail", id=busqueda.post_id))

    return render_template(
        "personal/postulantes.html",
        busqueda=busqueda,
        postulaciones=consultas.postulaciones_de(busqueda.id),
        # Los del menu lateral del panel, igual que la pantalla de Presupuestos.
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )


@personal.route("/postulantes")
@login_required
def bandeja():
    """Todas las busquedas del usuario, con cuantos se postularon a cada una.

    El conteo sale de UNA consulta agrupada y no de un COUNT por fila: con
    varios emprendimientos y sus busquedas viejas, lo segundo es el N+1 de
    esta pantalla.
    """
    busquedas = consultas.busquedas_de_usuario(g.user.id)
    return render_template(
        "personal/bandeja.html",
        busquedas=busquedas,
        conteo=consultas.conteo_de_postulaciones([b.id for b in busquedas]),
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )


# ------------------------------------------------------------- el postulante

@personal.route("/<int:id>/postular", methods=("GET", "POST"))
@login_required
def postular(id):
    """El formulario estructurado de postulacion.

    Tres frenos antes de dejar escribir, y los tres del lado del servidor: que
    la busqueda este abierta y no sea propia, que el perfil tenga lo minimo, y
    que no se haya postulado ya.
    """
    busqueda = consultas.busqueda_por_id_o_404(id)

    if not reglas.puede_postularse(busqueda, g.user.id):
        # Cubre las dos: la busqueda cerrada (el link se escribe a mano o quedo
        # abierto en una pestaña) y el dueño postulandose a su propio aviso.
        flash("Esa búsqueda no está recibiendo postulaciones.")
        return redirect(url_for("blog.detail", id=busqueda.post_id))

    if not reglas.perfil_completo(g.user):
        # No es un peaje decorativo: sin telefono ni ubicacion el emprendedor
        # no puede contestarle ni saber si le sirve por distancia. Se dice QUE
        # falta, no "completá tu perfil" a secas.
        falta = reglas.falta_de_perfil(g.user)
        flash(
            "Antes de postularte completá " + " y ".join(falta) +
            " en tu perfil, así te pueden contestar."
        )
        return redirect(url_for("profile.edit_contacto"))

    ya = consultas.postulacion_de(busqueda.id, g.user.id)
    if ya:
        # Mensaje claro, no garantia: la garantia es el UNIQUE, abajo.
        flash("Ya te postulaste a esta búsqueda.")
        return redirect(url_for("blog.detail", id=busqueda.post_id))

    if request.method == "POST":
        datos, error = formulario.leer_postulacion()
        if error:
            flash(error)
            return render_template(
                "personal/postular.html", busqueda=busqueda, datos=datos,
            )

        postulacion = Postulacion(
            busqueda_id=busqueda.id, postulante_id=g.user.id,
            nombre=datos["nombre"], contacto=datos["contacto"],
            experiencia=datos["experiencia"],
            disponibilidad=datos["disponibilidad"],
        )
        try:
            consultas.guardar(postulacion)
        except IntegrityError as choque:
            consultas.descartar()
            if not reglas.es_postulacion_duplicada(choque):
                raise
            flash("Ya te postulaste a esta búsqueda.")
            return redirect(url_for("blog.detail", id=busqueda.post_id))

        flash("Listo, mandamos tu postulación. Si le interesa, te escribe por acá.")
        return redirect(url_for("blog.detail", id=busqueda.post_id))

    # Prellenado desde el perfil: se le ahorra escribir lo que ya cargo. Lo que
    # se GUARDA es lo que mande, no lo que diga el perfil hoy (es un snapshot,
    # ver modelo_postulacion.py).
    return render_template(
        "personal/postular.html", busqueda=busqueda,
        datos={
            "nombre": g.user.username or "",
            "contacto": (g.user.phone or "").strip(),
            "experiencia": "", "disponibilidad": "",
        },
    )


@personal.route("/<int:id>/no-me-interesa", methods=("POST",))
@login_required
def no_me_interesa(id):
    """Cierra el aviso sin postularse, y deja la señal debil.

    PIDE SESION Y NO GUARDA QUIEN. Las dos mitades importan y no se
    contradicen: sin sesion el numero es ruido puro (un bot, o el propio
    emprendedor mirando su ficha, lo inflan sin costo), y alimentar las
    metricas de crecimiento con un numero inflable es peor que no tenerlo,
    porque se toman decisiones creyendo que hubo interes real. Exigir sesion no
    lo hace perfecto -- alguien logueado puede hacer diez clicks --, pero sube
    el costo lo suficiente, y el rate limit que ya corre en el proyecto acota
    el resto.

    Lo que NO se guarda es quien: no hay fila con nombre, solo el +1.
    """
    busqueda = consultas.busqueda_por_id_o_404(id)
    if busqueda.activa:
        # Una busqueda cerrada no suma: el numero habla del interes mientras el
        # aviso estuvo publicado.
        consultas.contar_vista_sin_postulacion(busqueda.id)
    return redirect(url_for("blog.detail", id=busqueda.post_id))
