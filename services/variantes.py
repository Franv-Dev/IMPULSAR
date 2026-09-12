"""Las reglas de las variantes de producto, sin saber que existe HTTP.

Nada de aca toca request ni flash: son decisiones que se contestan con lo que ya
se trajo de la base, para que se puedan probar sueltas. Escribe en la sesion
(generar_matriz agrega filas) pero no commitea: eso lo decide la vista, que es
la que sabe si el request entero salio bien.

Vive en services/ y no en un paquete app/ porque las variantes no son un dominio
nuevo: son una parte del producto, y el producto vive en models/product.py con
sus vistas en views/products.py. Partirlo en app/variantes/ dejaria la misma
cosa en dos lugares. Lo que si se respeta es la separacion de siempre -- las
decisiones aca, el HTTP en la vista.
"""

from models.producto_variante import (
    MAX_OPCIONES_POR_EJE,
    MAX_VALOR_OPCION,
    SIN_VALOR,
    ProductoVariante,
    ProductoVarianteOpcion,
    TiposDeOpcion,
)


def normalizar_lista(texto):
    """Lo que el vendedor escribio en un campo, convertido en lista de valores.

    Acepta el texto separado por comas o por saltos de linea, que son las dos
    formas en que alguien escribe una lista sin pensarlo.

    Limpia de verdad, y cada cosa por un motivo:

      - recorta los espacios de los costados, porque " M" y "M" son el mismo
        talle y si no la matriz tendria dos columnas identicas;
      - descarta los vacios, que salen solos de escribir "S, M, " o de una
        linea de mas;
      - saca los repetidos SIN reordenar, conservando la primera aparicion: el
        orden es el que eligio el vendedor y es lo que va a ver en la grilla.

    NO normaliza mayusculas ni acentos a proposito: "Negro" es como el vendedor
    quiere que se lea, y bajarlo a "negro" para comparar obligaria a guardar
    dos formas o a devolverle el texto cambiado. El costo es que "Negro" y
    "negro" conviven como dos colores; es un problema visible y de una sola
    persona, al reves que el de un catalogo global (ver docs/VARIANTES.md).
    """
    if not texto:
        return []

    crudos = []
    for linea in str(texto).replace("\r", "\n").split("\n"):
        crudos.extend(linea.split(","))

    limpios = []
    for valor in crudos:
        valor = valor.strip()
        if not valor or valor in limpios:
            continue
        limpios.append(valor)
    return limpios


def validar_lista(valores, etiqueta):
    """Devuelve el mensaje de error si la lista no entra, o None.

    Los dos topes son los del modelo y no numeros escritos aca: son el mismo
    limite y dos copias se despegan.
    """
    if len(valores) > MAX_OPCIONES_POR_EJE:
        return (
            f"{etiqueta}: no podés cargar más de {MAX_OPCIONES_POR_EJE} "
            f"(escribiste {len(valores)})."
        )
    for valor in valores:
        if len(valor) > MAX_VALOR_OPCION:
            return (
                f"{etiqueta}: «{valor[:20]}…» es muy largo, el máximo es "
                f"{MAX_VALOR_OPCION} caracteres."
            )
    return None


def opciones_de(producto, tipo):
    """Los valores de un eje de ese producto, en el orden que eligio el vendedor."""
    return [
        opcion.valor
        for opcion in sorted(
            (o for o in producto.opciones_de_variante if o.tipo == tipo),
            key=lambda o: (o.orden, o.id or 0),
        )
    ]


def guardar_opciones(producto, talles, colores):
    """Deja las dos listas del producto como dicen `talles` y `colores`.

    Agrega las opciones nuevas, actualiza el orden de las que siguen y borra
    las que el vendedor saco. Borrar la OPCION no borra las variantes que la
    usaban: de eso se ocupa generar_matriz, que las apaga (ver su docstring).

    Devuelve la lista de valores que se sacaron, por eje: {"talle": [...],
    "color": [...]}.
    """
    sacadas = {}
    for tipo, valores in ((TiposDeOpcion.TALLE, talles), (TiposDeOpcion.COLOR, colores)):
        existentes = {
            opcion.valor: opcion
            for opcion in producto.opciones_de_variante
            if opcion.tipo == tipo
        }

        for orden, valor in enumerate(valores):
            opcion = existentes.pop(valor, None)
            if opcion is None:
                producto.opciones_de_variante.append(
                    ProductoVarianteOpcion(
                        product_id=producto.id, tipo=tipo, valor=valor, orden=orden,
                    )
                )
            else:
                # Ya estaba: solo puede haber cambiado de lugar en la lista.
                opcion.orden = orden

        # Lo que quedo en `existentes` es lo que el vendedor saco.
        sacadas[tipo] = sorted(existentes)
        for opcion in existentes.values():
            producto.opciones_de_variante.remove(opcion)

    return sacadas


def combinaciones(talles, colores):
    """La matriz completa como pares (talle, color).

    El eje que el producto no usa viaja como cadena vacia y nunca como None:
    es lo que hace que el UNIQUE de la base sirva (ver el docstring de
    ProductoVariante). Un producto sin ninguna de las dos listas no tiene
    matriz -- no es "una combinacion unica", es que no usa variantes --, asi
    que devuelve vacio.
    """
    if not talles and not colores:
        return []
    filas = talles or [SIN_VALOR]
    columnas = colores or [SIN_VALOR]
    return [(talle, color) for talle in filas for color in columnas]


def generar_matriz(producto, talles, colores):
    """Crea las filas que faltan de la matriz. NO pisa las que ya estaban.

    Es lo mas importante de este modulo y la razon por la que se puede volver a
    tocar las listas sin miedo: el stock, el precio y el `activo` que el
    vendedor venia editando SOBREVIVEN. Lo unico que hace con una combinacion
    existente es dejarla como esta.

    Llamarla dos veces seguidas con la misma lista no crea nada la segunda vez,
    que es lo que la vuelve segura frente al doble click. La garantia dura de
    que no haya duplicados igual no es esta funcion sino el UNIQUE de la base:
    entre el chequeo de aca y el INSERT hay una ventana.

    LO QUE SE SACO DE LA LISTA SE APAGA Y NO SE BORRA. Si el vendedor saca el
    talle XXL, sus combinaciones dejan de poder venderse (nadie deberia poder
    pedir un talle que el vendedor dice que ya no maneja) pero las filas quedan,
    con su stock y su precio, por lo mismo que no se borran las que el apaga a
    mano: pueden tener historia. Volver a agregar el talle NO las reenciende
    solo -- para eso habria que guardar si se apagaron solas o a mano, que es
    una columna mas para una diferencia que el vendedor resuelve con un click.

    Devuelve (creadas, apagadas): cuantas filas nuevas y cuantas se apagaron.
    """
    ya_estan = {
        (variante.talle, variante.color): variante for variante in producto.variantes
    }

    creadas = 0
    de_la_matriz = set()
    for talle, color in combinaciones(talles, colores):
        de_la_matriz.add((talle, color))
        if (talle, color) in ya_estan:
            continue
        producto.variantes.append(
            ProductoVariante(
                product_id=producto.id, talle=talle, color=color,
                stock=0, precio_override=None, activo=True,
            )
        )
        creadas += 1

    apagadas = 0
    for clave, variante in ya_estan.items():
        if clave not in de_la_matriz and variante.activo:
            variante.activo = False
            apagadas += 1

    return creadas, apagadas


def orden_de(producto):
    """Una funcion de orden que pone las combinaciones como las escribio el vendedor.

    Devuelve una clave para `sorted`: primero el lugar del talle en la lista de
    talles y despues el del color en la de colores.

    EXISTE PORQUE ORDENAR ALFABETICAMENTE ES UN BUG, no una preferencia. Con
    "S, M, L, XL" el alfabetico da "L, M, S, XL", que no es ningun orden de
    talles: es exactamente el caso que justifica la columna `orden` de
    ProductoVarianteOpcion. La grilla del panel ya lo respetaba y el selector de
    la ficha no, asi que el vendedor veia una cosa y el comprador otra.

    Lo que ya no esta en las listas va al final (por eso el indice grande) y
    entre ellos alfabetico, que para un resto sin orden propio es lo unico
    honesto.
    """
    talles = opciones_de(producto, TiposDeOpcion.TALLE)
    colores = opciones_de(producto, TiposDeOpcion.COLOR)

    def clave(variante):
        try:
            lugar_talle = talles.index(variante.talle)
        except ValueError:
            lugar_talle = len(talles)
        try:
            lugar_color = colores.index(variante.color)
        except ValueError:
            lugar_color = len(colores)
        return (lugar_talle, lugar_color, variante.talle, variante.color)

    return clave


def comprables_ordenadas(producto):
    """Las combinaciones que se pueden pedir, en el orden en que se escribieron.

    Es lo que consume el selector de la ficha. Va aca y no armado en la vista
    para que el orden sea uno solo: el de la grilla del panel y el del selector
    salen de la misma lista de opciones.
    """
    return sorted(producto.variantes_comprables, key=orden_de(producto))


def grilla(producto):
    """La matriz ordenada como se dibuja: filas de talle, columnas de color.

    Devuelve una lista de filas, cada una:

        {"talle": "M", "variantes": [ProductoVariante, ...]}

    Se arma en Python sobre las variantes que ya se trajeron, sin una consulta
    por celda: con cinco talles y cuatro colores eso serian veinte consultas
    para dibujar una tabla.

    Respeta el orden de las OPCIONES y no el de las variantes: el vendedor
    escribio "S, M, L" y esa es la unica secuencia que significa algo (por id
    saldrian en el orden en que se generaron, y alfabeticamente "L, M, S", que
    es peor todavia).

    Las filas que ya no estan en las listas (las que quedaron de una lista
    anterior) van al final, agrupadas aparte: siguen existiendo y el vendedor
    tiene que poder verlas, pero no son parte de la matriz de hoy.
    """
    talles = opciones_de(producto, TiposDeOpcion.TALLE) or [SIN_VALOR]
    colores = opciones_de(producto, TiposDeOpcion.COLOR) or [SIN_VALOR]

    por_clave = {
        (variante.talle, variante.color): variante for variante in producto.variantes
    }

    filas = []
    usadas = set()
    for talle in talles:
        celdas = []
        for color in colores:
            variante = por_clave.get((talle, color))
            if variante is not None:
                celdas.append(variante)
                usadas.add((talle, color))
        if celdas:
            filas.append({"talle": talle, "variantes": celdas})

    sobrantes = [
        variante for clave, variante in por_clave.items() if clave not in usadas
    ]
    sobrantes.sort(key=lambda v: (v.talle, v.color))
    if sobrantes:
        filas.append({"talle": None, "variantes": sobrantes})

    return filas
