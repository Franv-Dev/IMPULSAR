"""Que dos tandas del rediseño no se pisen las clases en styles.css.

Las ocho tandas comparten un solo `static/css/styles.css` de ~16.700 lineas. Ahi
el orden del archivo decide quien gana, asi que si una tanda nueva bautiza un
componente con un nombre que otra ya usaba, le cambia el dibujo a una pantalla
que nadie volvio a mirar -- y la suite no se entera, porque el HTML sigue igual.

Paso dos veces en la auditoria de cierre del rediseño:

- El interruptor de "sin stock" del panel del vendedor se llamaba `.interruptor`,
  igual que el de los horarios de Cuenta, que ya estaba pusheado. Como va
  despues en el archivo le pisaba cuatro propiedades: la pastilla quedaba 38x22
  en vez de 44x26 y su fondo pasaba a --color-border, que es justo el valor que
  el bloque viejo le pone al estado `:checked`. Resultado: el interruptor de
  horarios se veia gris en los DOS estados y el color dejaba de decir si el dia
  estaba abierto.
- La lista de reseñas de la ficha se llamaba `.resenias`, igual que la grilla de
  dos columnas de "Reseñas recibidas". El `display: flex` de la ficha le ganaba
  al `display: grid`, y el resumen del costado se apilaba abajo a todo el ancho
  en vez de ir en su columna de 300 px.

Estos tests miran los NOMBRES, no el dibujo: es lo unico que se puede afirmar
sin un navegador, y alcanza para que el choque no vuelva sin que nadie lo note.
"""

import re

CSS = "static/css/styles.css"


def _clases_usadas(archivo):
    """Los tokens de clase que un template escribe en sus atributos class."""
    texto = open(archivo, encoding="utf-8").read()
    tokens = set()
    for valor in re.findall(r'class="([^"]*)"', texto):
        tokens.update(valor.split())
    return tokens


def _declaraciones(clase):
    """Cuantos bloques del nivel de arriba declaran exactamente esa clase."""
    css = open(CSS, encoding="utf-8").read()
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    return len(re.findall(r"(?m)^\.%s\s*\{" % re.escape(clase), css))


def test_el_interruptor_de_horarios_y_el_de_stock_no_comparten_el_nombre():
    horarios = _clases_usadas("app/perfil/templates/profile/horarios.html")
    stock = _clases_usadas("templates/products/mios.html")

    assert "interruptor" in horarios
    assert "interruptor-stock" in stock
    assert "interruptor" not in stock, (
        "products/mios.html volvio a usar .interruptor: le pisa la pastilla al "
        "interruptor de horarios, que va antes en styles.css"
    )


def test_las_dos_listas_de_resenias_no_comparten_el_nombre():
    ficha = _clases_usadas("app/blog/templates/blog/detail.html")
    recibidas = _clases_usadas("app/perfil/templates/profile/reviews.html")

    assert "resenias-ficha" in ficha
    assert "resenias" in recibidas
    assert "resenias" not in ficha, (
        "la ficha volvio a usar .resenias: le gana el flex al grid de dos "
        "columnas de 'Reseñas recibidas'"
    )


def test_ninguna_de_las_dos_clases_queda_declarada_dos_veces():
    """Una sola declaracion por clase en el nivel de arriba del archivo.

    Si aparecen dos, alguien volvio a partir el componente en dos bloques y el
    orden del archivo vuelve a decidir cual gana.
    """
    for clase in ("interruptor", "interruptor__pista", "interruptor__texto",
                  "interruptor-stock", "interruptor-stock__pista",
                  "resenias", "resenias-ficha"):
        assert _declaraciones(clase) == 1, (
            ".%s esta declarada %d veces en el nivel de arriba de styles.css"
            % (clase, _declaraciones(clase))
        )
