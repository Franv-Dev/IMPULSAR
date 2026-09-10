"""La ruta del panel: HTTP y nada mas.

Una sola pantalla, la portada. Las otras seis del panel siguen viviendo en su
dominio (emprendimientos en app/blog/, catalogo en views/products.py, etc.): lo
que esta tanda les puso en comun es el menu lateral, no el codigo.
"""

from flask import Blueprint, g, render_template

from app.blog.consultas import metricas_de_posts, tiene_horarios_cargados
from app.panel import consultas
from app.perfil.consultas import estadisticas_de_usuario
from app.servicios.consultas import emprendimientos_de
from services.eventos import hoy_en_argentina
from views.auth import login_required

panel = Blueprint(
    "panel", __name__, url_prefix="/panel", template_folder="templates"
)


def _aviso_de(contenido, metricas, sin_horarios):
    """Que le falta a ese emprendimiento para que lo encuentren.

    Devuelve uno solo, el primero que aplique, y no la lista entera: son tres
    huecos que casi siempre vienen juntos (el emprendimiento recien creado no
    tiene nada), y tres avisos apilados en una fila la convierten en un reto.

    El de los horarios va ultimo aunque sea el mas caro de arreglar: cuelga del
    USUARIO y no del emprendimiento (ver app/perfil/modelo_horario.py), asi que
    con dos emprendimientos aparece en los dos, y decirlo primero taparia lo
    que si es de ese emprendimiento.
    """
    if not contenido["fotos"]:
        return "Sin fotos, tu ficha aparece vacía en los listados"
    if not (metricas["productos"] or metricas["servicios"]):
        return "Todavía no cargaste productos ni servicios"
    if sin_horarios:
        return "Sin horarios no aparecés en «abierto ahora»"
    return None


@panel.route("/")
@login_required
def inicio():
    """La portada del panel: primero lo pendiente, despues los numeros.

    Ese orden es la decision de la tanda (disenio-panel/Main.dc.html): quien
    entra al panel viene a resolver algo, no a mirar cuanto creció. Las filas
    en cero ni se dibujan -- eso lo decide la plantilla, que recibe los cuatro
    valores igual.

    Los numeros son los cinco que la base sabe contar, sin variaciones ni
    graficos: estadisticas_de_usuario devuelve el total de hoy y no hay
    historico, asi que un "+18%" o una linea de tendencia serian inventados.
    """
    hoy = hoy_en_argentina()
    posts = emprendimientos_de(g.user.id)
    ids = [post.id for post in posts]

    metricas = metricas_de_posts(ids)
    contenido = consultas.contenido_de_posts(ids, hoy)
    sin_horarios = not tiene_horarios_cargados(g.user.id)

    emprendimientos = [
        {
            "post": post,
            "metricas": metricas[post.id],
            "contenido": contenido[post.id],
            "aviso": _aviso_de(
                contenido[post.id], metricas[post.id], sin_horarios
            ),
        }
        for post in posts
    ]

    return render_template(
        "panel/inicio.html",
        emprendimientos=emprendimientos,
        pendientes=consultas.pendientes_de(g.user.id, hoy),
        estadisticas=estadisticas_de_usuario(g.user.id),
        contadores=consultas.contadores_de(g.user.id, hoy),
        hoy=hoy,
    )
