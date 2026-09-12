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

from collections import namedtuple

from sqlalchemy import and_, case, func

from db import db
from models.product import Product
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


# --------------------------------------------------- las variantes en la grilla

#: Lo que una tarjeta necesita saber de las variantes de su producto.
#:
#: Es el mismo trio que la ficha saca de las properties de Product
#: (precio_desde, precio_es_rango, disponible_efectivo), pero calculado en la
#: base para TODA la pagina de una vez. Es un namedtuple y no un dict porque
#: los tres campos son fijos y se leen igual en Python y en el template
#: (`fila.variantes.precio_desde`), sin quedar escritos como cadenas sueltas.
ResumenDeVariantes = namedtuple(
    "ResumenDeVariantes",
    "tiene_variantes precio_desde precio_es_rango disponible",
)


def con_resumen_de_variantes(consulta):
    """Le suma a una Query de Product las cinco columnas agregadas de sus variantes.

    ESTA ES LA RAZON DE SER DE LA TANDA. La tarjeta del catalogo tiene que
    decir el precio y la disponibilidad reales, y los dos salen de otra tabla.
    Preguntandoselo a cada producto con las properties del modelo
    (`precio_desde`, `disponible_efectivo`) la pantalla mas visitada del
    proyecto haria dos consultas por tarjeta -- las variantes y las opciones
    son dos relaciones lazy --, o sea veinticuatro consultas extra en una
    grilla de doce. El N+1 que docs/VARIANTES.md dejo anotado como pendiente.

    Dos subconsultas AGRUPADAS con outerjoin, que es el mismo idiom que
    services.ratings.query_posts_con_rating: el GROUP BY vive adentro de cada
    subconsulta y la consulta de afuera no se agrupa. Agrupar afuera seria mas
    corto y esta mal por dos motivos: el joinedload del emprendimiento mete las
    columnas de posts en el SELECT, y con MySQL en ONLY_FULL_GROUP_BY eso es el
    error 1055 (las columnas de posts no dependen funcionalmente de
    products.id); y el paginado cuenta con un COUNT sobre la consulta, que con
    GROUP BY cuenta grupos y no filas.

    POR QUE SON DOS Y NO UNA. La de variantes sola no alcanza para saber si el
    producto usa variantes: un producto con toda la matriz apagada y otro que
    nunca las uso dan los dos "ninguna activa", y el primero esta agotado
    mientras el segundo vale su precio base. Los distingue si hay EJES
    cargados, que es la misma pregunta que contesta Product.tiene_variantes.

    EL PRECIO Y LA DISPONIBILIDAD SALEN DE LA MISMA CONDICION, escrita una sola
    vez (`comprable`): activa Y con stock, que es ProductoVariante.comprable en
    SQL. El minimo se calcula sobre esas mismas filas y no sobre todas las
    activas, para que la tarjeta no prometa un precio que la ficha no puede
    cumplir -- la mas barata sin stock no se puede pedir, asi que su precio no
    es una oferta--. Con dos condiciones separadas (una para el precio y otra
    para el cartel) la tarjeta podria decir "desde $9.000" y "sin stock" al
    mismo tiempo, cada mitad mirando otra cosa.

    El precio de cada combinacion es COALESCE(precio_override, products.precio),
    o sea la traduccion a SQL de ProductoVariante.precio_efectivo: NULL en el
    override significa "hereda", nunca cero.
    """
    precio_efectivo = func.coalesce(ProductoVariante.precio_override, Product.precio)
    activa = ProductoVariante.activo.is_(True)
    comprable = and_(activa, ProductoVariante.stock > 0)

    combinaciones = (
        db.session.query(
            ProductoVariante.product_id.label("product_id"),
            # Las activas se cuentan igual, aunque no sean comprables: es lo
            # que distingue "tiene la matriz cargada y hoy no hay nada" de "no
            # usa variantes", que son dos tarjetas distintas.
            func.sum(case((activa, 1), else_=0)).label("activas"),
            func.sum(case((comprable, 1), else_=0)).label("comprables"),
            func.min(case((comprable, precio_efectivo))).label("precio_min"),
            func.max(case((comprable, precio_efectivo))).label("precio_max"),
        )
        .join(Product, Product.id == ProductoVariante.product_id)
        .group_by(ProductoVariante.product_id)
        .subquery()
    )

    ejes = (
        db.session.query(
            ProductoVarianteOpcion.product_id.label("product_id"),
            func.count(ProductoVarianteOpcion.id).label("opciones"),
        )
        .group_by(ProductoVarianteOpcion.product_id)
        .subquery()
    )

    return (
        consulta
        .outerjoin(combinaciones, combinaciones.c.product_id == Product.id)
        .outerjoin(ejes, ejes.c.product_id == Product.id)
        # Con el prefijo `variantes_` y no con el nombre pelado de la
        # subconsulta: estas columnas viajan al lado de las del producto y de
        # la distancia del catalogo, y un `precio_min` suelto ahi adentro se
        # confunde con el filtro de precio de la barra de busqueda.
        .add_columns(
            ejes.c.opciones.label("variantes_opciones"),
            combinaciones.c.activas.label("variantes_activas"),
            combinaciones.c.comprables.label("variantes_comprables"),
            combinaciones.c.precio_min.label("variantes_precio_min"),
            combinaciones.c.precio_max.label("variantes_precio_max"),
        )
    )


def resumen_de_fila(producto, fila):
    """Traduce una fila de con_resumen_de_variantes() a lo que pinta la tarjeta.

    `fila` es el Row que devolvio la consulta; sus columnas se leen por nombre
    (`variantes_...`) y no por posicion, porque la consulta del catalogo agrega
    ademas la distancia y el orden de las columnas no es asunto de esta
    funcion.

    Las tres reglas, que son las mismas que ya aplica la ficha:

      - SIN VARIANTES no cambia nada: el precio base y el booleano `disponible`
        de siempre. Es la regresion que esta tanda no puede romper.
      - CON VARIANTES el precio es el minimo entre las COMPRABLES -- las
        encendidas y con stock, igual que Product.precio_desde --, y lleva
        "desde" solo si no valen todas lo mismo.
      - SIN NINGUNA COMPRABLE es agotado, no un error ni una vuelta al precio
        base: el vendedor tiene la matriz cargada y hoy no hay nada que pedir.

    "Hay algo comprable" se pregunta UNA vez y de ahi salen las dos mitades de
    la tarjeta: el cartel de "sin stock" y si hay un "desde" que calcular. Son
    la misma pregunta, asi que no pueden contestarse distinto.
    """
    opciones = fila.variantes_opciones or 0
    activas = fila.variantes_activas or 0

    tiene_variantes = bool(opciones) or bool(activas)
    if not tiene_variantes:
        return ResumenDeVariantes(
            tiene_variantes=False,
            precio_desde=producto.precio,
            precio_es_rango=False,
            disponible=bool(producto.disponible),
        )

    hay_comprables = bool(fila.variantes_comprables)
    if not hay_comprables:
        # No hay minimo que mostrar y el precio base es lo unico que queda: no
        # es lo que se cobra, pero la tarjeta ya dice agotado y un hueco donde
        # va el precio se lee como un error de la pagina.
        return ResumenDeVariantes(
            tiene_variantes=True,
            precio_desde=producto.precio,
            precio_es_rango=False,
            disponible=False,
        )

    precio_min = fila.variantes_precio_min
    precio_max = fila.variantes_precio_max
    return ResumenDeVariantes(
        tiene_variantes=True,
        precio_desde=precio_min,
        # > y no != para no depender de como vuelve el Decimal de cada motor.
        precio_es_rango=precio_max is not None and precio_max > precio_min,
        disponible=bool(producto.disponible),
    )
