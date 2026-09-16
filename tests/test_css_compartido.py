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


# --- selectores que se quedaron sin llaves


def _selectores_sin_comentarios(texto):
    """Los trozos de selector del archivo, con los comentarios ya sacados.

    Un selector es lo que va entre el `}` de la regla anterior (o el principio
    del archivo) y el `{` de la que arranca. Sacar los comentarios primero es
    justo lo que hace el navegador al parsear, y es lo que hace visible el bug
    que este test persigue.
    """
    limpio = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return re.findall(r"(?:^|\})([^{}]*)\{", limpio, flags=re.S)


def test_ningun_selector_se_quedo_sin_su_bloque():
    """Un selector sin llaves se come la regla siguiente, entera y en silencio.

    Paso de verdad: `.back-link:hover` habia quedado escrito sin bloque cuando
    el rediseno borro `.back-link` del HTML. El navegador entonces lee
    `.back-link:hover .perfil { ... }` -- el comentario del medio no lo corta --
    y la regla base de `.perfil` no se aplica nunca. El perfil perdia su
    `max-width: 1120px` y su padding: la portada, de 200px de alto fijo, se
    estiraba a todo el ancho de la ventana (9,5:1 en 1920) en vez de quedarse en
    los 1070px del resto de la app. Nada en el HTML cambia, asi que la suite no
    se enteraba.

    La firma del bug es que el selector resultante se traga una linea en blanco:
    ningun selector de verdad tiene una adentro.
    """
    texto = open(CSS, encoding="utf-8").read()

    #  Se recorta el chunk antes de mirarlo: entre dos reglas siempre hay un
    #  renglon en blanco, y eso es formato, no un huerfano. Lo que no puede
    #  haber es un renglon en blanco ADENTRO del selector ya recortado: ahi hay
    #  dos selectores pegados donde tendria que haber uno solo.
    huerfanos = [
        " ".join(sel.split())[:80]
        for sel in _selectores_sin_comentarios(texto)
        if re.search(r"\n\s*\n", sel.strip())
    ]

    assert not huerfanos, (
        "estos selectores se comieron la regla que venia despues: " f"{huerfanos}"
    )
