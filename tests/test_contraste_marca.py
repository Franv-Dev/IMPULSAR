"""Que los bloques de marca no pinten con un token que cambia entre temas.

El mismo bug apareció tres veces, y las tres en el mismo punto ciego:

- B3 (auditoría general): `.cartelera__cta` y `.rubro--todos` ponían
  `--color-on-primary` sobre `--color-primary-deep`.
- H3 (auditoría de las tandas): `.cartelera__cta-boton` hacía lo mismo pero
  como `background-color`, así que buscar la tinta no lo encontraba.
- Y al arreglar H3 apareció una cuarta: `.perfil-vender .btn--primary:hover`
  con `--color-primary-soft`, o sea el mismo bug por otro token.

La causa es siempre la misma. `--color-primary-deep` NO cambia con el tema: es
un color de marca, fijo en claro y en oscuro a propósito. Casi todos los demás
tokens sí cambian. Pareado uno con otro, el resultado es texto (o una
superficie) casi negro sobre índigo: 1,30:1 medido, y 1,03:1 en el peor de los
hover.

Un medidor de contraste de TEXTO no alcanza para encontrarlos: el botón de H3
daba 8,84:1 contra su propio fondo. Lo que falla es el borde del control contra
lo que tiene detrás, que es WCAG 1.4.11 y se mide entre superficies.

Este test no mide contraste -- eso necesita un navegador, y se hizo a mano con
el toggle real de la app. Lo que hace es cerrar el punto ciego: encuentra los
bloques que se pintan con el índigo fijo y exige que ellos y sus descendientes
usen colores fijos. Es el mismo criterio que ya siguen `.perfil-vender`,
`.perfil-panel` y `.bloque-marca`, que escriben `#fff` derecho.
"""

import re

CSS = "static/css/styles.css"

# El color de marca que no sigue al tema, y que es el que arma la trampa.
FIJO = "--color-primary-deep"


def _css_sin_comentarios():
    return re.sub(r"/\*.*?\*/", " ", open(CSS, encoding="utf-8").read(), flags=re.S)


def _reglas():
    """[(selector, cuerpo)] de cada bloque del nivel de arriba, en orden."""
    css = _css_sin_comentarios()
    # El ":" y el "[" del inicio no son opcionales: sin ellos no matchean
    # ":root" ni '[data-theme="dark"]', _tokens_que_cambian() vuelve vacia y el
    # test principal pasa SIN PROBAR NADA. Paso al escribirlo, las dos veces, y
    # lo agarro el tercer test de este archivo.
    return re.findall(r"(?m)^([.#:\[a-zA-Z][^{}\n]*?)\s*\{([^{}]*)\}", css)


def _tokens_por_tema():
    """Los tokens definidos en el tema claro y en el oscuro, por separado.

    El bloque oscuro es el que abre con `[data-theme="dark"]` o con el
    prefers-color-scheme; alcanza con juntar todo lo que se define despues del
    primer `:root` y compararlo con el propio `:root`.
    """
    css = _css_sin_comentarios()
    claro, oscuro = {}, {}
    for selector, cuerpo in _reglas():
        destino = None
        if selector.strip() == ":root":
            destino = claro
        elif "dark" in selector:
            destino = oscuro
        if destino is None:
            continue
        for nombre, valor in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", cuerpo):
            destino.setdefault(nombre, valor.strip())
    return claro, oscuro


def _tokens_que_cambian():
    """Los tokens que valen distinto en claro y en oscuro."""
    claro, oscuro = _tokens_por_tema()
    return {
        nombre
        for nombre, valor in oscuro.items()
        if nombre in claro and claro[nombre] != valor
    }


def _raices_de_marca():
    """Los selectores que se pintan de fondo con el índigo fijo."""
    raices = set()
    for selector, cuerpo in _reglas():
        fondo = re.findall(r"background(?:-color|-image)?\s*:\s*([^;]+);", cuerpo)
        if any(FIJO in valor for valor in fondo):
            # El primer token del selector es la clase del bloque; alcanza para
            # emparentar a sus descendientes, que en este CSS son BEM
            # (.cartelera__cta -> .cartelera__cta-boton).
            raices.add(selector.split()[0].split(":")[0].strip())
    return raices


def test_hay_bloques_de_marca_que_encontrar():
    """Si el barrido no encuentra ninguno, el resto del archivo no prueba nada."""
    raices = _raices_de_marca()

    assert len(raices) >= 3, raices


# El token de la estrella cambia entre temas y ESTÁ BIEN que lo use un bloque de
# marca: los dos valores son ámbar claro (#E8A33D y #FBBF24), que sobre el
# índigo dan 6,47:1 y 8,36:1. Lo que rompe no es que un token cambie, es que
# cambie hacia un color oscuro; medir eso es trabajo de un navegador, así que la
# excepción va escrita con su medición al lado.
TOKENS_QUE_CAMBIAN_PERO_SIRVEN = {"--color-star"}


def test_ningun_bloque_de_marca_pinta_con_un_token_que_cambia():
    """Ni el bloque ni sus descendientes: es donde vivían B3, H3 y los otros dos."""
    cambian = _tokens_que_cambian() - TOKENS_QUE_CAMBIAN_PERO_SIRVEN
    raices = _raices_de_marca()
    culpables = []

    # Solo la ULTIMA regla de cada selector, que es la que gana: styles.css
    # tiene el .cartelera__cta de agosto y el del rediseño, y el viejo queda
    # pisado entero. Sin esto el test acusa codigo que el navegador nunca
    # aplica, que es ruido y encima esconde lo que si importa.
    ultima_de = {}
    for indice, (selector, cuerpo) in enumerate(_reglas()):
        ultima_de[selector.strip()] = indice

    for indice, (selector, cuerpo) in enumerate(_reglas()):
        if ultima_de[selector.strip()] != indice:
            continue
        if not any(selector.startswith(raiz) for raiz in raices):
            continue
        for propiedad, valor in re.findall(
            r"(color|background-color|background-image)\s*:\s*([^;]+);", cuerpo
        ):
            for token in re.findall(r"var\((--[\w-]+)", valor):
                if token in cambian:
                    culpables.append(f"{selector.strip()} -> {propiedad}: {token}")

    assert not culpables, (
        "estos bloques van sobre el índigo fijo y pintan con un token que "
        "cambia entre temas, que es como quedó 1,30:1 en oscuro; escribí el "
        "color derecho (#fff) o usá uno que no cambie: " + ", ".join(culpables)
    )


def test_el_token_de_marca_sigue_valiendo_lo_mismo_en_los_dos_temas():
    """Todo lo de arriba se apoya en esto: si dejara de ser fijo, cambia el criterio."""
    claro, oscuro = _tokens_por_tema()

    assert claro[FIJO] == oscuro[FIJO] == "#2A2068"
