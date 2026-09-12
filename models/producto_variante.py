"""Variantes de un producto: la combinacion talle x color, con su stock.

EL DISEÑO ENTERO, EN UN LUGAR, para que el que audite despues no tenga que
reconstruirlo leyendo el diff (el mismo resumen esta en docs/VARIANTES.md):

    producto_variante_opciones   que talles y que colores maneja ESE producto
    producto_variantes           una fila por combinacion realmente generada

El vendedor carga dos listas (los talles y los colores que maneja) y el sistema
genera la matriz completa como filas editables. Cada fila tiene stock propio,
precio propio opcional y un interruptor para las combinaciones que en la
practica no existen.

LAS VARIANTES SON OPCIONALES Y NADA DE ESTO TOCA AL PRODUCTO QUE NO LAS USA. Un
producto sin filas en estas dos tablas se comporta exactamente como antes de
esta tanda: su precio es products.precio y su disponibilidad es
products.disponible, el booleano de siempre. No se agrego ninguna columna a
products, justamente para que el camino viejo no cambie.
"""

from db import db, utcnow

# El largo de un talle ("XXL", "42", "Único") y de un color ("Verde militar").
# Cortos a proposito: son etiquetas de una grilla, no descripciones.
MAX_VALOR_OPCION = 40

# Cuantas opciones por eje admite un producto. El tope real es el producto de
# los dos (la matriz), asi que 20 x 20 = 400 filas es el peor caso, que ya es
# muchisimo mas de lo que maneja un emprendimiento de feria. Existe para que un
# POST armado a mano no genere cien mil filas de una.
MAX_OPCIONES_POR_EJE = 20

# Cuando un producto usa un solo eje (talles y ningun color, o al reves), el
# otro se guarda como cadena VACIA y nunca como NULL. Ver el docstring de
# ProductoVariante: es lo que hace que el UNIQUE sirva.
SIN_VALOR = ""


class TiposDeOpcion:
    """Los dos ejes de la matriz.

    String con una clase de constantes y no un sa.Enum, que es como resuelve
    esto todo el proyecto (ver Roles, Categorias, Rubros, Modalidades,
    EstadosOportunidad): un Enum de verdad obliga a un ALTER TYPE para agregar
    un valor.
    """

    TALLE = "talle"
    COLOR = "color"

    TODOS = (TALLE, COLOR)

    ETIQUETAS = {TALLE: "Talle", COLOR: "Color"}
    # En plural, para los titulos de las dos listas del formulario.
    PLURALES = {TALLE: "Talles", COLOR: "Colores"}


class ProductoVarianteOpcion(db.Model):
    """Un talle o un color habilitado para un producto.

    UNA SOLA TABLA CON UN CAMPO `tipo`, Y NO DOS TABLAS CHICAS. La decision
    tiene una razon concreta y no es "queda mas corto": las dos cosas tienen
    exactamente la misma forma -- una etiqueta corta que pertenece a un
    producto y que se ordena -- y se usan en el mismo lugar, en el mismo
    momento y de la misma manera (las dos son un eje de la matriz). Dos tablas
    serian el mismo modelo, la misma FK, el mismo UNIQUE, el mismo endpoint y
    los mismos tests escritos dos veces, y el dia que haya que agregar un
    tercer eje (material, sabor) serian tres.

    Es al reves que el caso de product_favorites, que SI es tabla aparte de
    favorites: alla las dos cosas se guardan igual pero se MIRAN distinto (una
    es "esta gente me interesa" y la otra "esta cosa a este precio"). Aca no:
    un talle y un color se miran igual, son el valor de un eje.

    El precio de la decision es que el `tipo` hay que validarlo, porque la
    columna sola aceptaria cualquier cosa. Eso lo sostiene el CHECK de abajo, y
    no la buena memoria de cada vista.

    NO HAY CATALOGO GLOBAL DE TALLES NI DE COLORES, y se evaluo: seria una
    tabla compartida entre productos con su ABM, su normalizacion ("Rojo" vs
    "rojo" vs "ROJO") y su pantalla de administracion. A cambio no daria nada
    hoy -- no existe ningun filtro del catalogo por color ni por talle, que es
    lo unico que justificaria compartir el vocabulario. Cada producto guarda
    sus valores como texto, que ademas es lo que el vendedor escribe. El dia
    que se quiera filtrar "todo lo que hay en rojo", eso es una tabla nueva y
    una migracion de datos, no un rediseño de esta.
    """

    __tablename__ = "producto_variante_opciones"

    __table_args__ = (
        # El mismo talle dos veces en el mismo producto no es un dato, es un
        # doble click: generaria una columna repetida en la matriz. Lo corta la
        # base y no la vista, que es lo unico que cierra la ventana entre el
        # SELECT y el INSERT.
        db.UniqueConstraint(
            "product_id", "tipo", "valor", name="uq_producto_variante_opciones_valor",
        ),
        # La red de abajo del `tipo`. El formulario ya valida contra
        # TiposDeOpcion.TODOS, pero el formulario no es el unico camino a la
        # tabla: estan el seed, un script suelto y la consola de la base. Una
        # fila con tipo "talel" no se nota hasta que falta media matriz.
        db.CheckConstraint(
            "tipo IN ('talle', 'color')",
            name="ck_producto_variante_opciones_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, que desde b2b97d078fb2 es la
    # regla del proyecto: borrar el producto se lleva sus opciones y (por la
    # otra FK) sus variantes.
    product_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "products.id", ondelete="CASCADE",
            name="fk_producto_variante_opciones_product_id_products",
        ),
        nullable=False, index=True,
    )
    tipo = db.Column(db.String(10), nullable=False)
    valor = db.Column(db.String(MAX_VALOR_OPCION), nullable=False)
    # En que orden los escribio el vendedor. Sin esto la grilla saldria por id,
    # que es lo mismo hasta la primera vez que agrega un talle en el medio: "S,
    # M, L, XL" con el XS agregado despues quedaria "S, M, L, XL, XS".
    orden = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # cascade="all, delete-orphan" del lado del producto: la FK ya borra en la
    # base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # product_id en NULL cuando se borra un Product desde la sesion, y la
    # columna es NOT NULL. Mismo caso que imagenes, eventos y propuestas.
    producto = db.relationship(
        "Product",
        backref=db.backref("opciones_de_variante", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        return (
            f"<ProductoVarianteOpcion product_id={self.product_id} "
            f"{self.tipo}={self.valor!r}>"
        )

    def serialize(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "tipo": self.tipo,
            "valor": self.valor,
            "orden": self.orden,
        }


class ProductoVariante(db.Model):
    """Una combinacion talle+color de un producto, con su stock y su precio.

    Es una fila de la matriz que genera services/variantes.py a partir de las
    opciones de arriba. Se genera completa (todos los talles x todos los
    colores) porque es lo unico que el sistema puede saber; que combinaciones
    existen DE VERDAD lo sabe el vendedor y lo dice apagando `activo` en las
    que no. Es curacion manual sobre la matriz y no una regla automatica: no
    hay forma de deducir que el XXL no se fabrico en verde.

    EL EJE QUE NO SE USA SE GUARDA COMO CADENA VACIA Y NUNCA COMO NULL, y esto
    no es cosmetico. El UNIQUE es (product_id, talle, color), y en los dos
    motores un UNIQUE IGNORA las filas que tienen un NULL en alguna de sus
    columnas -- es la misma propiedad que el proyecto usa a favor en
    cupo_pendiente, cupo_activa y cupo_aceptada. Si un producto con talles y
    sin colores guardara color = NULL, el UNIQUE dejaria de aplicar justo en
    ese caso y se podrian cargar dos filas "M" sin que la base dijera nada. Con
    la cadena vacia el UNIQUE vale siempre.

    PRECIO: `precio_override` en NULL significa "usa el precio del producto", y
    no "gratis". Por eso es nullable y el cero es un precio valido y distinto
    (ver el CHECK, que es >= 0 igual que el de products.precio: un producto
    gratis es una oferta real). Quien quiera el precio que se le cobra al
    cliente no mira esta columna sino `precio_efectivo`.

    STOCK: entero y no negativo, garantizado por la base. Es el unico stock
    numerico del proyecto -- el producto sin variantes sigue teniendo el
    booleano `disponible` y ninguna columna nueva, a proposito.
    """

    __tablename__ = "producto_variantes"

    __table_args__ = (
        # LA COMBINACION ES UNICA POR PRODUCTO. Constraint de base y no
        # validacion en Python: la generacion de la matriz chequea antes que
        # existe para no duplicar, pero entre ese SELECT y el INSERT hay una
        # ventana por la que pasan dos requests simultaneos (el doble click que
        # manda dos POST, o dos pestañas del mismo formulario).
        db.UniqueConstraint(
            "product_id", "talle", "color", name="uq_producto_variantes_combinacion",
        ),
        db.CheckConstraint("stock >= 0", name="ck_producto_variantes_stock_no_negativo"),
        # Mismo criterio y mismo signo que ck_products_precio_no_negativo: la
        # base corta lo que no tiene sentido en ningun caso, y que el
        # formulario acepte o no el cero se decide en services/precios.py, que
        # se cambia sin migracion.
        db.CheckConstraint(
            "precio_override IS NULL OR precio_override >= 0",
            name="ck_producto_variantes_precio_no_negativo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "products.id", ondelete="CASCADE",
            name="fk_producto_variantes_product_id_products",
        ),
        nullable=False, index=True,
    )

    # NOT NULL con default "": ver "EL EJE QUE NO SE USA" en el docstring. No
    # son FK a un catalogo, tambien a proposito (ver ProductoVarianteOpcion).
    talle = db.Column(
        db.String(MAX_VALOR_OPCION), nullable=False, default=SIN_VALOR,
        server_default="",
    )
    color = db.Column(
        db.String(MAX_VALOR_OPCION), nullable=False, default=SIN_VALOR,
        server_default="",
    )

    stock = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # NULL = hereda el precio del producto. Ver "PRECIO" en el docstring.
    precio_override = db.Column(db.Numeric(10, 2), nullable=True)
    # Para la combinacion que no existe de verdad. Se apaga, no se borra: la
    # fila puede tener historia (un stock que se vendio) y borrarla seria
    # perderla, ademas de que la matriz la volveria a generar en el proximo
    # guardado de opciones.
    activo = db.Column(
        db.Boolean, nullable=False, default=True, server_default="1", index=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    producto = db.relationship(
        "Product",
        backref=db.backref("variantes", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        combinacion = " / ".join(v for v in (self.talle, self.color) if v) or "única"
        estado = "activa" if self.activo else "apagada"
        return (
            f"<ProductoVariante product_id={self.product_id} {combinacion} "
            f"stock={self.stock} {estado}>"
        )

    @property
    def etiqueta(self):
        """Como se nombra la combinacion en pantalla: "M / Negro", "M", "Única"."""
        partes = [valor for valor in (self.talle, self.color) if valor]
        return " / ".join(partes) if partes else "Única"

    @property
    def precio_efectivo(self):
        """El precio que se le cobra al cliente por ESTA combinacion.

        El override si lo hay, y si no el del producto. Es una property y no
        una columna calculada a proposito: si se copiara el precio base en cada
        fila al generarla, subir el precio del producto no se reflejaria en las
        variantes que nunca se tocaron, que es justo lo que "hereda" tiene que
        significar.

        Lo usa todo el que muestre un precio; nadie deberia leer
        precio_override directo salvo el formulario de edicion, que necesita
        distinguir "vacio" de "cargado".
        """
        if self.precio_override is not None:
            return self.precio_override
        return self.producto.precio if self.producto is not None else None

    @property
    def hereda_precio(self):
        return self.precio_override is None

    @property
    def comprable(self):
        """Si esta combinacion se puede elegir para consultar.

        Las dos condiciones juntas: encendida y con stock. Vive en el modelo
        porque la preguntan la ficha, el selector y la validacion del servidor,
        y tres copias de `activo and stock > 0` se despegan en cuanto aparezca
        una tercera condicion.
        """
        return bool(self.activo) and self.stock > 0

    def serialize(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "talle": self.talle,
            "color": self.color,
            "etiqueta": self.etiqueta,
            "stock": self.stock,
            # str y no float, por lo mismo que el resto de los precios del
            # proyecto: un Decimal pasado por float vuelve con centavos de
            # diferencia.
            "precio_override": (
                str(self.precio_override) if self.precio_override is not None else None
            ),
            "precio_efectivo": (
                str(self.precio_efectivo) if self.precio_efectivo is not None else None
            ),
            "activo": self.activo,
            "comprable": self.comprable,
        }
