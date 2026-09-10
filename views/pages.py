"""Paginas estaticas de contenido (sobre, contacto, terminos, privacidad).

Antes eran cuatro blueprints separados (about.py, contact.py, terms.py,
privacy.py), cada uno con un Blueprint, una ruta "/" y un render_template
casi identicos. Al no tener ninguna logica propia (ni formularios, ni
modelos), no habia razon para mantenerlos en cuatro archivos: se unifican en
uno solo y cada pagina es una ruta con su propio path completo, para no
cambiar las URLs existentes.

Contacto SIGUE SIN FORMULARIO a proposito: no hay tabla de consultas ni envio
de mail, y un formulario dibujado que en realidad no manda nada es peor que un
mailto honesto. Si algun dia se agrega, deja de ser una ruta sin logica.
"""

from flask import Blueprint, render_template, url_for

pages = Blueprint("pages", __name__)

# Cuando se actualizo por ultima vez cada texto legal.
#
# ESTAN EN None PORQUE NO SE SABEN, y no es un dato que se pueda inventar: la
# fecha es lo unico que permite saber que version de los terminos acepto cada
# usuario, asi que una inventada es peor que ninguna. El artboard de la tanda
# lo marca como [COMPLETAR] por lo mismo.
#
# Mientras sean None, la pastilla de "Ultima actualizacion" no se dibuja (ver
# templates/legal_base.html). Se completan con el texto tal como se quiere leer
# ("14 de agosto de 2026") y aparece sola. Son strings y no `date` a proposito:
# lo unico que se hace con esto es escribirlo, y un date obligaria a formatearlo
# en castellano en el template.
ACTUALIZADA_PRIVACIDAD = None
ACTUALIZADA_TERMINOS = None


@pages.route("/sobre/")
def about():
    return render_template("about.html")


@pages.route("/contacto/")
def contact():
    return render_template("contact.html")


@pages.route("/terminos/")
def terms():
    """Terminos y Condiciones.

    `legal_otra_*` son el enlace cruzado del indice lateral: quien viene a leer
    una de las dos legales casi siempre termina buscando la otra, y con dos
    pantallas no hace falta nada mas elaborado que pasarse el par.
    """
    return render_template(
        "terms.html",
        actualizada_el=ACTUALIZADA_TERMINOS,
        legal_otra_url=url_for("pages.privacy"),
        legal_otra_texto="Política de Privacidad",
    )


@pages.route("/privacidad/")
def privacy():
    return render_template(
        "privacy.html",
        actualizada_el=ACTUALIZADA_PRIVACIDAD,
        legal_otra_url=url_for("pages.terms"),
        legal_otra_texto="Términos y Condiciones",
    )
