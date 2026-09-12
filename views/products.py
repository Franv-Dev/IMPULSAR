"""Catalogo de productos de los emprendimientos.

Dos mitades que comparten blueprint y modelo:

    /productos           el catalogo PUBLICO, con busqueda, filtros y orden
    /productos/<id>      el detalle de un producto
    /productos/mios      el panel del dueño, y de ahi cuelga su ABM

Hasta el rediseño de esta tanda (disenio-productos/) el prefijo entero era
privado: /productos era el panel, y un producto solo se veia incrustado adentro
de la ficha de su emprendimiento. Eso dejaba sin URL a lo unico que un visitante
quiere linkear y compartir, asi que el catalogo se quedo con la URL corta y el
panel se corrio a /productos/mios. El endpoint del panel se llama `mios` por lo
mismo (antes era `index`).

El ABM quedo aca y no adentro del blog por lo mismo que el de eventos: es su
propia entidad, con su propio formulario y su propio panel, y meterlo adentro
de la vista del blog solo hacia mas grande un archivo que ya era el mas grande
del proyecto (hoy ese dominio vive en app/blog/).

Un producto pertenece a un emprendimiento (Post), no a un usuario, asi que el
permiso siempre se resuelve mirando el dueño de ese emprendimiento. El chequeo
va en la vista y no solo en el template: esconder un boton no es un permiso,
cualquiera puede mandar el POST a mano.

NO ES UNA TIENDA, y el catalogo publico lo respeta: no hay stock, ni variantes,
ni carrito, ni pago (ver el docstring de models/product.py). La accion de una
tarjeta es consultar, y termina en el chat interno con el nombre del producto
ya escrito.
"""

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request,
    url_for
)
from sqlalchemy import distinct, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from db import db
from app.blog.consultas import (
    abierto_ahora_sql, distancia_km_sql, metricas_de_posts,
)
from app.blog.modelo_post import Categorias, Post
from app.blog.reglas import RADIOS_KM, categoria_valida, radio_valido
from app.panel.consultas import contadores_de as contadores_del_panel
from models.product import (
    MAX_PRODUCTOS_POR_POST, UMBRAL_AVISO_LIMITE, Product,
)
from models.product_favorite import ProductFavorite
from models.producto_variante import (
    MAX_OPCIONES_POR_EJE, ProductoVariante, TiposDeOpcion,
)
from services.eventos import hoy_en_argentina
from services.geocoding import get_coordinates_from_address
from services.horarios import esta_abierto, hora_de_cierre
from services.precios import parsear_precio, texto_para_formulario
from services import variantes as reglas_variantes
from services.uploads import borrar_de_disco, carpeta_uploads, save_post_image
from services.validation import largo_de, validar_largo
from views.auth import login_required

products = Blueprint("products", __name__, url_prefix="/productos")

# Los largos salen de las columnas (ver services/validation.py): el maxlength
# del HTML no valida nada, se saltea mandando el POST a mano.
MAX_NOMBRE = largo_de(Product.nombre)
MAX_DESCRIPCION = largo_de(Product.descripcion)


class Ordenes:
    """Como se puede ordenar el catalogo publico.

    Una clase de constantes con su tupla y su dict de etiquetas, igual que
    Categorias y que blog.reglas.OrdenesFavoritos: los strings viven en un solo
    lugar y el control del template se arma del mismo lado del que se valida lo
    que llega, asi que no se pueden despegar.

    NUEVOS es el default y ordena por Product.created_at: lo ultimo que
    cargaron los emprendimientos es lo que todavia nadie vio.

    Los dos de PRECIO existen porque las dos preguntas son reales y opuestas
    ("lo mas barato que haya" y "que hay de lo bueno"), y el catalogo muestra
    el precio como primer dato de cada tarjeta justamente para comparar.

    CERCANIA solo aparece cuando hay coordenadas: sin ellas no hay desde donde
    medir. Lo decide la vista, que es la que sabe si se pudo ubicar al
    visitante; aca es un valor mas.
    """

    NUEVOS = "nuevos"
    PRECIO_MENOR = "precio"
    PRECIO_MAYOR = "precio_desc"
    CERCANIA = "cercania"

    TODOS = (NUEVOS, PRECIO_MENOR, PRECIO_MAYOR, CERCANIA)

    ETIQUETAS = {
        NUEVOS: "Más nuevos",
        PRECIO_MENOR: "Precio: menor a mayor",
        PRECIO_MAYOR: "Precio: mayor a menor",
        CERCANIA: "Cercanía",
    }


def orden_valido(orden):
    """Si es uno de los ordenes que ofrece el catalogo.

    Se valida por lo mismo que la categoria: llega de un control de la pantalla
    pero viaja en la URL, y cualquiera puede escribir ahi otra cosa. Que hacer
    con lo invalido lo decide la vista, y aca es caer al default: el orden no
    es un filtro, es una preferencia de como mirar lo mismo, y no hay nada que
    avisarle a nadie.
    """
    return orden in Ordenes.TODOS


def _upload_dir():
    return carpeta_uploads()


def _producto_propio(id):
    """El producto con ese id si es de un emprendimiento del usuario actual.

    Devuelve (producto, None) si puede tocarlo, o (None, respuesta) con el
    redirect ya armado si no. Mismo criterio que eventos._evento_propio: flash
    y vuelta al panel, no un 403 crudo.
    """
    producto = Product.query.get_or_404(id)
    if producto.post.author != g.user.id:
        flash("No tenés permiso para modificar este producto.")
        return None, redirect(url_for("products.mios"))
    return producto, None


def _mis_emprendimientos():
    return Post.query.filter_by(author=g.user.id).order_by(Post.title).all()


def _leer_formulario():
    """Los campos del producto tal como los mando el usuario, ya parseados.

    La validacion es a mano (con flash y una variable `error`) porque asi
    valida todo el proyecto: Flask-WTF esta instalado pero solo se usa para el
    CSRF.
    """
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    precio_texto = (request.form.get("precio") or "").strip()
    # Un checkbox que no se marca directamente no viaja en el POST.
    disponible = request.form.get("disponible") is not None

    precio, error_precio = parsear_precio(precio_texto)

    # El primero de los dos textos que no entra en su columna, si hay alguno.
    muy_largo = (
        validar_largo(nombre, MAX_NOMBRE, "El nombre")
        or validar_largo(descripcion, MAX_DESCRIPCION, "La descripción")
    )

    error = None
    if not nombre:
        error = "Se requiere un nombre para el producto."
    elif muy_largo:
        error = muy_largo
    elif error_precio:
        error = error_precio

    # Se devuelve el texto crudo del precio y no el Decimal: si estaba mal
    # escrito, el formulario tiene que volver con lo que puso el usuario.
    datos = {
        "nombre": nombre, "descripcion": descripcion,
        "precio": precio_texto, "disponible": disponible,
    }
    return datos, nombre, descripcion, precio, disponible, error


# ------------------------------------------------------------ rutas publicas

def _leer_filtros():
    """Lo que el visitante pidio, leido de la URL y ya normalizado.

    Todos los filtros del catalogo viajan como parametros de la URL y no como
    un formulario que se postea, por el mismo criterio que ya usan el listado
    de emprendimientos y la busqueda de servicios: la busqueda se comparte, se
    guarda en favoritos del navegador, vuelve con el boton de atras y funciona
    sin JavaScript.

    Lo que se valida aca y lo que no sigue la misma linea que el listado:

    * El RUBRO vuelve crudo. Uno que no existe no filtra nada (lo decide
      categoria_valida en la vista), pero el template igual necesita repintar
      el control con lo que el usuario tenia en la URL.
    * El RADIO se valida contra reglas.RADIOS_KM. Va al WHERE como una cuenta
      de trigonometria sobre toda la tabla, asi que aceptar cualquier numero de
      la URL es dejar pedir consultas arbitrarias.
    * El PRECIO se parsea con el mismo parsear_precio del formulario de carga,
      asi que "1.500,50" y "1500.50" se entienden igual en los dos lados. Un
      precio mal escrito vuelve como None (no acota) pero el TEXTO crudo se
      devuelve igual, para que el campo no se vacie solo mientras alguien
      escribe.
    * DISPONIBLES viene encendido y se apaga con disponibles=0, al reves que
      los checkboxes de si/no del listado. Un catalogo que arranca mostrando lo
      que no hay hace perder tiempo, asi que el default tiene que ser el filtro
      puesto; y como el default es "puesto", lo que hay que poder escribir en
      la URL es el apagado.
    """
    precio_min_texto = (request.args.get("precio_min") or "").strip()
    precio_max_texto = (request.args.get("precio_max") or "").strip()
    precio_min, _ = parsear_precio(precio_min_texto, obligatorio=False)
    precio_max, _ = parsear_precio(precio_max_texto, obligatorio=False)

    radio = request.args.get("radio", type=int)

    return {
        "busqueda": (request.args.get("q") or "").strip(),
        "categoria": (request.args.get("category") or "").strip(),
        "precio_min": precio_min,
        "precio_max": precio_max,
        "precio_min_texto": precio_min_texto,
        "precio_max_texto": precio_max_texto,
        "solo_disponibles": request.args.get("disponibles") != "0",
        "abierto_ahora": request.args.get("abierto_ahora") is not None,
        "cerca_de": (request.args.get("near") or "").strip(),
        "lat": request.args.get("lat", type=float),
        "lon": request.args.get("lon", type=float),
        "radio_km": radio if radio_valido(radio) else None,
        "orden": (request.args.get("orden") or "").strip(),
        "pagina": request.args.get("page", 1, type=int),
    }


def _filtrar_catalogo(consulta, busqueda, categoria, precio_min, precio_max,
                      solo_disponibles, abierto_ahora, distancia, radio_km):
    """Los filtros del catalogo publico, en un solo lugar.

    Lo usan la busqueda y el conteo de emprendimientos que va en el encabezado
    ("18 productos de 11 emprendimientos"): ese numero tiene que contar
    EXACTAMENTE lo mismo que la grilla esta mostrando. Con los filtros escritos
    dos veces, cualquier cambio en uno deja al otro mintiendo, que es peor que
    no tener el dato. Es el mismo motivo por el que servicios tiene su
    _filtrar_busqueda.

    Tres filtros son del EMPRENDIMIENTO y no del producto, porque el producto
    no tiene con que contestarlos: el rubro (Product no tiene categoria propia,
    ver el docstring del modelo), "abierto ahora" (los horarios son del
    emprendedor) y la distancia (las coordenadas son del emprendimiento). Por
    eso los tres se resuelven sobre Post, con las mismas piezas que el listado.

    `distancia` es la expresion SQL de los km, o None cuando no hay desde donde
    medir. Se pasa ya armada y no se calcula aca porque quien busca la necesita
    ademas como columna y como orden, y armarla dos veces seria dos veces la
    misma trigonometria en el mismo SELECT.
    """
    if solo_disponibles:
        # .is_(True) y no == True por lo mismo que en el resto del proyecto: la
        # columna es NOT NULL con default True, y el operador de identidad es
        # el que genera el SQL correcto en los dos motores.
        consulta = consulta.filter(Product.disponible.is_(True))

    if busqueda:
        # Nombre y descripcion del PRODUCTO, no del emprendimiento: el que
        # busca "dulce de leche" en el catalogo esta buscando la cosa. Para
        # encontrar el negocio esta el listado, que ademas ya mira adentro del
        # catalogo (ver _coincide_en_catalogo_sql).
        patron = f"%{busqueda}%"
        consulta = consulta.filter(or_(
            Product.nombre.ilike(patron),
            Product.descripcion.ilike(patron),
        ))

    if categoria:
        consulta = consulta.filter(Post.category == categoria)

    # Rango exacto y no aproximado: Product.precio es Numeric(10,2), asi que la
    # comparacion es sobre decimales de verdad y no sobre floats que redondean.
    if precio_min is not None:
        consulta = consulta.filter(Product.precio >= precio_min)
    if precio_max is not None:
        consulta = consulta.filter(Product.precio <= precio_max)

    if abierto_ahora:
        consulta = consulta.filter(abierto_ahora_sql())

    if distancia is not None:
        # Sin coordenadas propias, un emprendimiento no tiene con que calcular
        # la distancia: se excluye en vez de mostrarlo con un orden arbitrario.
        # Mismo criterio que buscar_posts.
        consulta = consulta.filter(
            Post.latitude.isnot(None), Post.longitude.isnot(None)
        )
        if radio_km is not None:
            # Va la expresion entera y no la etiqueta "distance_km": MySQL no
            # deja usar un alias del SELECT adentro del WHERE.
            consulta = consulta.filter(distancia <= radio_km)

    return consulta


def _buscar_en_catalogo(busqueda, categoria, precio_min, precio_max,
                        solo_disponibles, abierto_ahora, lat, lon, radio_km,
                        orden, pagina, por_pagina):
    """El catalogo publico, ya paginado.

    Devuelve (paginacion, ordenado_por_distancia). Cuando hay coordenadas cada
    fila trae una columna extra con los km, asi que quien lo consume tiene que
    saber en cual de los dos modos vino; por eso el bool va en el retorno y no
    lo tiene que deducir el template mirando lat y lon otra vez. Es la misma
    forma que devuelve consultas.buscar_posts.

    JOIN A POSTS SIEMPRE, no solo cuando hay filtros del emprendimiento: cada
    tarjeta muestra de quien es el producto, y el joinedload trae esa fila en
    la misma consulta para no disparar un SELECT por tarjeta (problema N+1).

    El desempate por id no es decorativo: sin el, dos productos con el mismo
    precio -- o cargados en el mismo segundo, que en MySQL empatan porque la
    columna es DATETIME(0) -- salen en distinto orden en cada consulta, y en
    una lista paginada eso significa una tarjeta repetida en dos paginas o una
    que no aparece en ninguna.
    """
    hay_coordenadas = lat is not None and lon is not None
    distancia = distancia_km_sql(lat, lon) if hay_coordenadas else None

    consulta = _filtrar_catalogo(
        Product.query
        .join(Post, Post.id == Product.post_id)
        .options(joinedload(Product.post)),
        busqueda=busqueda, categoria=categoria,
        precio_min=precio_min, precio_max=precio_max,
        solo_disponibles=solo_disponibles, abierto_ahora=abierto_ahora,
        distancia=distancia, radio_km=radio_km,
    )

    if hay_coordenadas:
        consulta = consulta.add_columns(distancia.label("distance_km"))

    if orden == Ordenes.CERCANIA and hay_coordenadas:
        orden_sql = (distancia.asc(), Product.id.asc())
    elif orden == Ordenes.PRECIO_MENOR:
        orden_sql = (Product.precio.asc(), Product.id.asc())
    elif orden == Ordenes.PRECIO_MAYOR:
        orden_sql = (Product.precio.desc(), Product.id.desc())
    else:
        orden_sql = (Product.created_at.desc(), Product.id.desc())

    paginacion = consulta.order_by(*orden_sql).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )
    return paginacion, hay_coordenadas


def _cuantos_emprendimientos(busqueda, categoria, precio_min, precio_max,
                             solo_disponibles, abierto_ahora, lat, lon, radio_km):
    """De cuantos emprendimientos distintos salen los productos encontrados.

    Es la segunda mitad del encabezado ("18 productos de 11 emprendimientos"),
    y es el dato que dice si la busqueda encontro variedad o el catalogo entero
    de un solo negocio -- que en un catalogo sin marcas es justamente lo que
    hay que saber antes de mirar precios.

    Un COUNT(DISTINCT post_id) y no traer las filas para contarlas en Python:
    la grilla trae doce por pagina y el numero es de TODA la busqueda, no de la
    pagina. Pasa por _filtrar_catalogo, que es lo que garantiza que cuente
    exactamente lo mismo que la grilla muestra.
    """
    distancia = distancia_km_sql(lat, lon) if lat is not None and lon is not None else None

    return _filtrar_catalogo(
        db.session.query(func.count(distinct(Product.post_id)))
        .join(Post, Post.id == Product.post_id),
        busqueda=busqueda, categoria=categoria,
        precio_min=precio_min, precio_max=precio_max,
        solo_disponibles=solo_disponibles, abierto_ahora=abierto_ahora,
        distancia=distancia, radio_km=radio_km,
    ).scalar() or 0


def _ids_favoritos(user_id, productos):
    """De esos productos, cuales tiene marcados ese usuario. Una sola consulta.

    Se pregunta por los ids de LA PAGINA y no por todos los favoritos del
    usuario: la respuesta es del mismo tamaño que lo que se va a pintar, y no
    crece con los años de uso de la persona.

    Sin ids no consulta nada: un `IN ()` vacio es SQL invalido en algunos
    motores y una pasada al pedo en el resto.
    """
    if not user_id or not productos:
        return frozenset()

    filas = (
        db.session.query(ProductFavorite.product_id)
        .filter(
            ProductFavorite.user_id == user_id,
            ProductFavorite.product_id.in_([p.id for p in productos]),
        )
        .all()
    )
    return {product_id for (product_id,) in filas}


@products.route("/")
def catalogo():
    """El catalogo publico: todos los productos de la plataforma, filtrables.

    Es la pantalla que no existia: hasta ahora un producto solo se veia adentro
    de la ficha de su emprendimiento, o sea que para encontrarlo habia que
    saber antes quien lo vende.

    Geocodificar es una llamada a MapTiler, o sea trabajo con red de por medio:
    se hace solo si el visitante mando una direccion en texto y no las
    coordenadas ya resueltas, igual que en el listado.

    El orden por defecto cambia si hay ubicacion: sin coordenadas manda "mas
    nuevos", con coordenadas manda "cercania". Quien se tomo el trabajo de
    decir donde esta quiere lo de al lado primero, y el control igual queda
    marcado en la opcion que se aplico, asi que no es un orden secreto.
    """
    filtros = _leer_filtros()
    lat, lon = filtros["lat"], filtros["lon"]

    if filtros["cerca_de"] and lat is None and lon is None:
        lat, lon = get_coordinates_from_address(
            filtros["cerca_de"], current_app.config["MAPTILER_KEY"]
        )
        if lat is None:
            flash("No pudimos ubicar esa dirección en el mapa. Probá con otro formato, o dejá el campo vacío.")

    hay_coordenadas = lat is not None and lon is not None
    orden = filtros["orden"]
    if not orden_valido(orden) or (orden == Ordenes.CERCANIA and not hay_coordenadas):
        orden = Ordenes.CERCANIA if hay_coordenadas else Ordenes.NUEVOS

    # Lo que la busqueda y el contador tienen que ver IGUAL. Se arma una sola
    # vez por lo mismo que existe _filtrar_catalogo: si el contador recibiera
    # otros argumentos, el "de N emprendimientos" del encabezado hablaria de una
    # busqueda distinta de la que se esta mostrando.
    lo_pedido = {
        "busqueda": filtros["busqueda"],
        # Un rubro que no existe no filtra nada, pero se le devuelve igual al
        # template para repintar el control con lo que el usuario tenia.
        "categoria": (
            filtros["categoria"] if categoria_valida(filtros["categoria"]) else None
        ),
        "precio_min": filtros["precio_min"],
        "precio_max": filtros["precio_max"],
        "solo_disponibles": filtros["solo_disponibles"],
        "abierto_ahora": filtros["abierto_ahora"],
        "lat": lat,
        "lon": lon,
        "radio_km": filtros["radio_km"],
    }

    paginacion, ordenado_por_distancia = _buscar_en_catalogo(
        orden=orden,
        pagina=filtros["pagina"],
        por_pagina=current_app.config["PRODUCTOS_POR_PAGINA"],
        **lo_pedido,
    )

    if ordenado_por_distancia:
        filas = [
            {"producto": producto, "distance_km": round(km, 1) if km is not None else None}
            for producto, km in paginacion.items
        ]
    else:
        filas = [{"producto": producto, "distance_km": None} for producto in paginacion.items]

    favoritos = _ids_favoritos(
        g.user.id if g.user else None, [f["producto"] for f in filas]
    )
    for fila in filas:
        fila["es_favorito"] = fila["producto"].id in favoritos

    return render_template(
        "products/catalogo.html",
        filas=filas,
        paginacion=paginacion,
        cuantos_emprendimientos=_cuantos_emprendimientos(**lo_pedido),
        categorias=Categorias.ETIQUETAS,
        categoria_actual=filtros["categoria"],
        busqueda_actual=filtros["busqueda"],
        precio_min_actual=filtros["precio_min_texto"],
        precio_max_actual=filtros["precio_max_texto"],
        solo_disponibles_actual=filtros["solo_disponibles"],
        abierto_ahora_actual=filtros["abierto_ahora"],
        cerca_de_actual=filtros["cerca_de"],
        # Ya validado: es uno de reglas.RADIOS_KM o None ("sin limite"). El
        # template lo usa solo para marcar la opcion que corresponde.
        radio_actual=filtros["radio_km"],
        radios_km=RADIOS_KM,
        ordenado_por_distancia=ordenado_por_distancia,
        ordenes=Ordenes.ETIQUETAS,
        # Ya normalizado a uno valido y aplicable, para que el control siempre
        # tenga una opcion marcada aunque la URL traiga cualquier cosa.
        orden_actual=orden,
        orden_cercania=Ordenes.CERCANIA,
    )


@products.route("/<int:id>")
def detalle(id):
    """El detalle de un producto.

    Contesta DOS preguntas y no una: que es (foto, precio, si esta disponible,
    descripcion) y QUIEN LO VENDE (rubro, puntaje, si esta abierto ahora, el
    emprendimiento). La segunda pesa tanto como la primera: en una plataforma
    sin pagos ni proteccion al comprador, lo que termina de decidir es la
    confianza en la persona, no la ficha tecnica.

    Una sola foto y no una galeria: Product.foto es una columna (ver el modelo).

    Las metricas del emprendimiento salen de metricas_de_posts, que trae en UNA
    consulta el promedio, la cantidad de reseñas y cuantos productos tiene --
    los tres datos que la pantalla muestra, incluido el "Ver los N productos"
    del bloque de abajo.
    """
    producto = (
        Product.query
        .options(joinedload(Product.post))
        .filter(Product.id == id)
        .first()
    )
    if producto is None:
        abort(404)

    post = producto.post
    autor = post.author_user
    metricas = metricas_de_posts([post.id]).get(post.id, {})

    # Los demas productos del mismo emprendimiento, sin repetir el que se esta
    # mirando. Se traen cinco para poder mostrar cuatro aunque uno de los cinco
    # sea este mismo, en vez de pedir un COUNT aparte para saber cuantos saltar.
    hermanos = [
        otro for otro in (
            Product.query
            .filter(Product.post_id == post.id, Product.disponible.is_(True))
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(5)
            .all()
        )
        if otro.id != producto.id
    ][:4]

    return render_template(
        "products/detalle.html",
        producto=producto,
        post=post,
        autor=autor,
        avg_rating=metricas.get("promedio"),
        review_count=metricas.get("resenias", 0),
        total_productos=metricas.get("productos", 0),
        hermanos=hermanos,
        es_dueño=bool(g.user and g.user.id == post.author),
        es_favorito=bool(
            g.user
            and ProductFavorite.query.filter_by(
                user_id=g.user.id, product_id=producto.id
            ).first()
        ),
        # Los horarios son del emprendedor y no del emprendimiento (viven en
        # User), igual que en la ficha: el "abierto ahora" lo calcula
        # services/horarios con el reloj de Argentina y no con el del visitante.
        abierto=esta_abierto(autor.horarios),
        cierra=hora_de_cierre(autor.horarios),
    )


# ----------------------------------------------------- favoritos de productos

@products.route("/<int:id>/favorito", methods=("POST",))
@login_required
def toggle_favorito(id):
    """Marca o desmarca un producto como favorito (toggle).

    Mismo patron que blog.toggle_favorite, incluida la ventana de carrera: el
    SELECT de "ya lo tiene?" y el INSERT no son atomicos, asi que dos clicks
    casi simultaneos pasan los dos. Lo que de verdad lo impide es el UNIQUE de
    la tabla; atrapar el IntegrityError es para que el segundo click no le
    muestre un 500 a nadie.
    """
    producto = Product.query.get_or_404(id)

    favorito = ProductFavorite.query.filter_by(
        user_id=g.user.id, product_id=producto.id
    ).first()
    if favorito:
        db.session.delete(favorito)
        db.session.commit()
        flash("Se quitó de tus productos guardados.")
    else:
        try:
            db.session.add(
                ProductFavorite(user_id=g.user.id, product_id=producto.id)
            )
            db.session.commit()
            flash("Se guardó en tus productos.")
        except IntegrityError:
            db.session.rollback()

    return redirect(request.referrer or url_for("products.detalle", id=producto.id))


@products.route("/guardados")
@login_required
def guardados():
    """Los productos que el usuario marco, la otra pestaña de "Mis favoritos".

    Vive aca y no en blog/ porque lo que lista son productos: la pantalla de
    favoritos pasa a tener dos solapas (Emprendimientos y Productos) y cada una
    la sirve el dominio al que pertenece lo que muestra.

    El joinedload trae el emprendimiento de cada producto en la misma consulta:
    la tarjeta lo nombra, y sin eso es un SELECT por fila (problema N+1).

    El desempate por id, igual que en "Mis favoritos": en MySQL la columna es
    DATETIME(0), asi que todo lo que se marca dentro del mismo segundo empata,
    y empatado el orden es arbitrario e inestable entre consultas.
    """
    paginacion = (
        Product.query
        .join(ProductFavorite, ProductFavorite.product_id == Product.id)
        .options(joinedload(Product.post))
        .filter(ProductFavorite.user_id == g.user.id)
        .order_by(ProductFavorite.created.desc(), ProductFavorite.id.desc())
        .paginate(
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["PRODUCTOS_POR_PAGINA"],
            error_out=False,
        )
    )
    return render_template(
        "products/guardados.html",
        productos=paginacion.items,
        paginacion=paginacion,
    )


# ---------------------------------------------- rutas privadas (del dueño)

@products.route("/mios")
@login_required
def mios():
    """El panel: los productos de los emprendimientos propios, agrupados.

    Vive en /productos/mios y no en /productos desde la tanda del catalogo: la
    URL corta es la publica, que es la unica que alguien linkea (ver el
    docstring del modulo).

    Agrupados por emprendimiento y no en una grilla suelta porque el tope es
    por emprendimiento (MAX_PRODUCTOS_POR_POST): un contador global no diria
    nada sobre el limite que se puede chocar.

    Los grupos se arman desde los EMPRENDIMIENTOS y no desde los productos: el
    que no cargo ninguno tambien tiene que aparecer, con la accion de cargar el
    primero al lado. Antes se recorrian los productos y un emprendimiento
    vacio simplemente no existia en la pantalla.

    joinedload trae el emprendimiento en la misma consulta (y con el su autor,
    que ya es lazy="joined"), para no disparar un SELECT por producto al
    mostrar de cual es: es el mismo problema N+1 que la cartelera de eventos.
    El reparto se hace en memoria sobre esas mismas filas, sin una consulta por
    emprendimiento.
    """
    posts = _mis_emprendimientos()
    productos = (
        Product.query
        .join(Post, Post.id == Product.post_id)
        .options(joinedload(Product.post))
        .filter(Post.author == g.user.id)
        .order_by(Product.nombre)
        .all()
    )

    grupos = []
    por_post = {}
    for post in posts:
        grupo = {"post": post, "productos": []}
        grupos.append(grupo)
        por_post[post.id] = grupo

    for producto in productos:
        por_post[producto.post_id]["productos"].append(producto)

    for grupo in grupos:
        total = len(grupo["productos"])
        grupo["total"] = total
        grupo["sin_stock"] = sum(
            1 for producto in grupo["productos"] if not producto.disponible
        )
        # El limite se muestra solo cerca del tope (ver UMBRAL_AVISO_LIMITE):
        # el contador va siempre, el techo recien cuando falta poco.
        grupo["cerca_del_limite"] = total >= UMBRAL_AVISO_LIMITE
        grupo["completo"] = total >= MAX_PRODUCTOS_POR_POST

    return render_template(
        "products/mios.html",
        grupos=grupos,
        posts=posts,
        maximo=MAX_PRODUCTOS_POR_POST,
        umbral=UMBRAL_AVISO_LIMITE,
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )


@products.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Cargar un producto en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder cargar productos.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, nombre, descripcion, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un producto del emprendimiento de
        # otro mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error is None and _cuantos_tiene(post_id) >= MAX_PRODUCTOS_POR_POST:
            error = (
                f"Ese emprendimiento ya tiene {MAX_PRODUCTOS_POR_POST} productos, "
                "que es el máximo. Borrá alguno para cargar uno nuevo."
            )

        foto = None
        if error is None:
            # La foto se guarda al final: si algo de arriba fallaba, no tiene
            # sentido escribir un archivo que despues nadie va a referenciar.
            foto, error = save_post_image(request.files.get("foto"), _upload_dir())

        if error:
            flash(error)
            return render_template(
                "products/form.html", posts=posts, datos=datos, producto=None
            )

        db.session.add(Product(
            post_id=post_id, nombre=nombre, descripcion=descripcion or None,
            precio=precio, foto=foto, disponible=disponible,
        ))
        db.session.commit()
        flash("Producto agregado correctamente.")
        return redirect(url_for("products.mios"))

    datos = {
        "nombre": "", "descripcion": "", "precio": "",
        "disponible": True, "post_id": None,
    }
    return render_template("products/form.html", posts=posts, datos=datos, producto=None)


@products.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un producto propio."""
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        datos, nombre, descripcion, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        # El tope solo aplica si el producto se esta MUDANDO a otro
        # emprendimiento: si se queda donde estaba, ya esta contado.
        if (
            error is None
            and post_id != producto.post_id
            and _cuantos_tiene(post_id) >= MAX_PRODUCTOS_POR_POST
        ):
            error = (
                f"Ese emprendimiento ya tiene {MAX_PRODUCTOS_POR_POST} productos, "
                "que es el máximo."
            )

        foto_nueva = None
        if error is None:
            foto_nueva, error = save_post_image(request.files.get("foto"), _upload_dir())

        if error:
            # Si la foto nueva llego a escribirse pero algo posterior fallo,
            # se borra: si no, queda en disco sin ninguna fila que la use.
            borrar_de_disco(_upload_dir(), [foto_nueva])
            flash(error)
            return render_template(
                "products/form.html", posts=posts, datos=datos, producto=producto
            )

        foto_vieja = producto.foto
        producto.post_id = post_id
        producto.nombre = nombre
        producto.descripcion = descripcion or None
        producto.precio = precio
        producto.disponible = disponible
        if foto_nueva:
            producto.foto = foto_nueva
        db.session.commit()

        # Recien despues del commit: si la base fallaba, la fila seguiria
        # apuntando a la foto vieja y borrarla antes la dejaria rota.
        if foto_nueva:
            borrar_de_disco(_upload_dir(), [foto_vieja])

        flash("Producto actualizado correctamente.")
        return redirect(url_for("products.mios"))

    datos = {
        "nombre": producto.nombre,
        "descripcion": producto.descripcion or "",
        "precio": texto_para_formulario(producto.precio),
        "disponible": producto.disponible,
        "post_id": producto.post_id,
    }
    return render_template(
        "products/form.html", posts=posts, datos=datos, producto=producto
    )


@products.route("/<int:id>/disponible", methods=("POST",))
@login_required
def alternar_disponible(id):
    """Marcar un producto sin stock, o volver a ponerlo, desde el panel.

    Es el unico backend nuevo de la tanda del panel y es el mismo movimiento
    que servicios.alternar_disponible: hasta ahora apagar un producto obligaba
    a abrir el formulario de cinco campos, releerlos y volver a guardarlos, con
    el riesgo de pisar de paso algo que no se queria tocar.

    POST y no GET aunque toque una sola columna: cambia lo que ve el catalogo
    publico, y con GET lo dispararia cualquier cosa que precargue enlaces.

    Un form de un boton y no un checkbox con JavaScript, por el mismo criterio
    que los filtros del catalogo: tiene que andar sin JS.
    """
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    producto.disponible = not producto.disponible
    db.session.commit()
    flash(
        f'"{producto.nombre}" vuelve a estar disponible.'
        if producto.disponible
        else f'"{producto.nombre}" quedó sin stock: sale de tu ficha y del '
             "catálogo hasta que lo vuelvas a prender."
    )
    return redirect(url_for("products.mios"))


@products.route("/<int:id>/eliminar", methods=("POST",))
@login_required
def eliminar(id):
    """Eliminar un producto propio.

    Solo POST, con la misma razon que blog.delete: un GET no debe tener
    efectos secundarios (lo puede disparar un prefetch del navegador o un
    crawler).
    """
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    foto = producto.foto
    db.session.delete(producto)
    db.session.commit()

    # Despues del commit y no antes: si el borrado en la base falla, el
    # producto sigue existiendo y tiene que seguir teniendo su foto.
    borrar_de_disco(_upload_dir(), [foto])

    flash("Producto eliminado correctamente.")
    return redirect(url_for("products.mios"))


# --------------------------------------------------------------- variantes
#
# La matriz talle x color de un producto. Son OPCIONALES: un producto que nunca
# entra aca se comporta exactamente como antes de esta tanda (ver
# docs/VARIANTES.md). Todo este bloque es del dueño; lo que ve el visitante
# vive en detalle().


@products.route("/<int:id>/variantes")
@login_required
def variantes(id):
    """La pantalla de variantes de un producto: las dos listas y la matriz."""
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    return render_template(
        "products/variantes.html",
        producto=producto,
        talles=reglas_variantes.opciones_de(producto, TiposDeOpcion.TALLE),
        colores=reglas_variantes.opciones_de(producto, TiposDeOpcion.COLOR),
        grilla=reglas_variantes.grilla(producto),
        tipos=TiposDeOpcion,
        max_opciones=MAX_OPCIONES_POR_EJE,
        contadores=contadores_del_panel(g.user.id, hoy_en_argentina()),
    )


@products.route("/<int:id>/variantes/opciones", methods=("POST",))
@login_required
def guardar_opciones_de_variante(id):
    """Guarda que talles y que colores maneja el producto, y genera la matriz.

    GENERAR NO PISA LO EDITADO: las combinaciones que ya existian se quedan con
    su stock, su precio y su `activo`: solo se agregan las que faltan. Es lo que
    permite volver a tocar las listas sin perder el trabajo, y esta explicado en
    services/variantes.generar_matriz.

    Llamarlo dos veces con la misma lista no crea nada la segunda vez. La
    garantia dura contra el duplicado igual no es esa (entre el chequeo y el
    INSERT hay una ventana) sino el UNIQUE de la base, y por eso el
    IntegrityError se atrapa en vez de subir como un 500.
    """
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    talles = reglas_variantes.normalizar_lista(request.form.get("talles"))
    colores = reglas_variantes.normalizar_lista(request.form.get("colores"))

    error = (
        reglas_variantes.validar_lista(talles, "Talles")
        or reglas_variantes.validar_lista(colores, "Colores")
    )
    if error:
        flash(error)
        return redirect(url_for("products.variantes", id=producto.id))

    reglas_variantes.guardar_opciones(producto, talles, colores)
    creadas, apagadas = reglas_variantes.generar_matriz(producto, talles, colores)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # Perdio la carrera contra otro POST identico: el UNIQUE lo rechazo y
        # lo que el vendedor queria ya esta hecho.
        flash("Ya habías guardado esos talles y colores.")
        return redirect(url_for("products.variantes", id=producto.id))

    if not talles and not colores:
        flash(
            "Sacaste todos los talles y colores: el producto vuelve a venderse "
            "sin variantes."
        )
    else:
        partes = []
        if creadas:
            partes.append(
                f"{creadas} combinación nueva" if creadas == 1
                else f"{creadas} combinaciones nuevas"
            )
        if apagadas:
            partes.append(
                f"{apagadas} quedó apagada" if apagadas == 1
                else f"{apagadas} quedaron apagadas"
            )
        flash(
            "Listo: " + " y ".join(partes) + "." if partes
            else "Listo, no hubo cambios en la matriz."
        )
    return redirect(url_for("products.variantes", id=producto.id))


def _leer_variante():
    """Lo que manda el formulario de una fila de la matriz.

    Devuelve (datos, error). Los tres campos se validan ACA, del lado del
    servidor, y no solo con el `min="0"` del input ni con el CHECK de la base:
    el atributo HTML se saltea mandando el POST a mano, y el CHECK devuelve un
    error de motor que el vendedor veria como un 500 en vez de como un error
    del formulario. Ademas en MySQL un CHECK violado llega como
    OperationalError y no como IntegrityError, asi que ni siquiera se podria
    atrapar con el mismo except que el resto.

    El precio VACIO no es un error: significa "usá el del producto" y se guarda
    como NULL (ver models/producto_variante.py). Es la unica forma de volver a
    heredar despues de haber puesto un precio propio, asi que borrar el campo
    tiene que funcionar.
    """
    stock_texto = (request.form.get("stock") or "").strip()
    precio_texto = (request.form.get("precio") or "").strip()

    stock = None
    error = None
    if not stock_texto:
        error = "Poné el stock de esa combinación (0 si no te queda)."
    else:
        try:
            stock = int(stock_texto)
        except ValueError:
            error = "El stock tiene que ser un número entero."
        else:
            if stock < 0:
                error = "El stock no puede ser negativo."

    precio = None
    if not error and precio_texto:
        # obligatorio=True porque si escribio algo, ese algo tiene que ser un
        # precio: el "sin precio" se dice dejando el campo vacio, no con basura.
        precio, error_precio = parsear_precio(precio_texto, obligatorio=True)
        if error_precio:
            error = error_precio

    datos = {
        "stock": stock,
        "precio_override": precio,
        # Un checkbox que no viene es un checkbox destildado: no hay forma de
        # distinguirlo de "no lo mandaron", y no hace falta -- este formulario
        # manda la fila entera.
        "activo": request.form.get("activo") is not None,
    }
    return datos, error


@products.route("/<int:id>/variantes/<int:variante_id>", methods=("POST",))
@login_required
def editar_variante(id, variante_id):
    """Edita el stock, el precio y el interruptor de UNA combinacion.

    Los dos ids llegan por la URL y nada obliga a que vayan juntos, asi que se
    chequea que la variante sea de ESE producto. Sin eso, el dueño de un
    producto podria editar la variante de otro escribiendo la URL: el permiso
    de _producto_propio mira el producto, no la fila.
    """
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    variante = ProductoVariante.query.get_or_404(variante_id)
    if variante.product_id != producto.id:
        abort(404)

    datos, error = _leer_variante()
    if error:
        flash(f"{variante.etiqueta}: {error}")
        return redirect(url_for("products.variantes", id=producto.id))

    variante.stock = datos["stock"]
    variante.precio_override = datos["precio_override"]
    variante.activo = datos["activo"]
    db.session.commit()

    flash(f"Guardado: {variante.etiqueta}.")
    return redirect(url_for("products.variantes", id=producto.id))


def _cuantos_tiene(post_id):
    """Cuantos productos tiene ya ese emprendimiento.

    Un COUNT y no len(post.productos): trae un numero en vez de todas las
    filas solo para contarlas.
    """
    return Product.query.filter_by(post_id=post_id).count()
