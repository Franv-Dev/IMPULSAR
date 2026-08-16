from db import db, utcnow


class Rubros:
    """Rubros validos para un servicio.

    Catalogo fijo y no texto libre, al reves que zona_cobertura. La diferencia
    es que sobre el rubro se va a buscar: con texto libre, "plomeria",
    "Plomería" y "plomero" son tres rubros distintos y el filtro de la proxima
    tanda tendria que normalizar a mano lo que ya se cargo. La zona no tiene
    catalogo posible todavia (son barrios, distritos y "toda la ciudad"), asi
    que ahi si va texto libre.

    Mismo formato que Categorias en models/post.py y Roles en models/user.py:
    los strings viven en un solo lugar y las etiquetas para mostrar tambien.
    """

    PLOMERIA = "plomeria"
    ELECTRICIDAD = "electricidad"
    GAS = "gas"
    ALBANILERIA = "albanileria"
    PINTURA = "pintura"
    CARPINTERIA = "carpinteria"
    HERRERIA = "herreria"
    REFRIGERACION = "refrigeracion"
    JARDINERIA = "jardineria"
    LIMPIEZA = "limpieza"
    FLETES = "fletes"
    INFORMATICA = "informatica"
    OTROS = "otros"

    TODOS = (
        PLOMERIA, ELECTRICIDAD, GAS, ALBANILERIA, PINTURA, CARPINTERIA,
        HERRERIA, REFRIGERACION, JARDINERIA, LIMPIEZA, FLETES, INFORMATICA,
        OTROS,
    )

    ETIQUETAS = {
        PLOMERIA: "Plomería",
        ELECTRICIDAD: "Electricidad",
        GAS: "Gas",
        ALBANILERIA: "Albañilería",
        PINTURA: "Pintura",
        CARPINTERIA: "Carpintería",
        HERRERIA: "Herrería",
        REFRIGERACION: "Refrigeración",
        JARDINERIA: "Jardinería",
        LIMPIEZA: "Limpieza",
        FLETES: "Fletes y mudanzas",
        INFORMATICA: "Informática",
        OTROS: "Otros",
    }


# Cuantos servicios puede cargar un emprendimiento. El mismo numero y el mismo
# criterio que MAX_PRODUCTOS_POR_POST: un tope fijo y chico que no molesta al
# uso real (un plomero tiene cinco o seis servicios, no cincuenta) y corta el
# abuso. Un numero distinto solo agregaria otra constante que justificar.
MAX_SERVICIOS_POR_POST = 50


class Service(db.Model):
    """Un servicio que ofrece un emprendimiento: un trabajo a presupuestar.

    Se separa de Product a proposito, y la diferencia no es cosmetica:

    - un producto tiene precio y se compra tal cual; un servicio se cotiza
      contra el caso de cada cliente, asi que precio_estimado es opcional
      ("a presupuestar") mientras que Product.precio es NOT NULL,
    - un servicio se presta en una zona, un producto no,
    - un servicio se pide con una solicitud de presupuesto (ver
      models/service_request.py), un producto no tiene ese flujo.

    Ojo con la palabra "servicio", que en este proyecto nombra tres cosas
    distintas: Categorias.SERVICIOS es el rubro del EMPRENDIMIENTO entero
    (una bicicleteria), Product es un item con precio fijo (que puede ser un
    trabajo cerrado, tipo "service de bici, $8000") y esto es un trabajo a
    presupuestar por zona.

    Cuelga del emprendimiento (Post) y no del usuario, igual que productos y
    eventos: alguien puede tener una gasista y una electricista.
    """

    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, igual que products: sin el
    # CASCADE, MySQL usa RESTRICT y borrar un emprendimiento con servicios
    # falla con IntegrityError; sin el nombre, la FK se llama distinto en cada
    # motor y una migracion futura no tiene como referirse a ella.
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id", ondelete="CASCADE", name="fk_services_post_id_posts"),
        nullable=False, index=True,
    )
    # Indexado porque la busqueda por rubro es lo primero que viene despues de
    # esta tanda, y es la unica consulta que no filtra por post_id.
    rubro = db.Column(
        db.String(40), nullable=False,
        default=Rubros.OTROS, server_default=Rubros.OTROS, index=True,
    )
    titulo = db.Column(db.String(120), nullable=False)
    # Corta como la del producto: es lo que entra en una tarjeta del listado,
    # no la descripcion larga del emprendimiento.
    descripcion = db.Column(db.String(300), nullable=True)
    # Texto libre por ahora: "Maipu y alrededores", "toda la ciudad", "hasta
    # 20km". Cuando haya con que normalizarlo se vera, hoy seria adivinar.
    zona_cobertura = db.Column(db.String(120), nullable=True)
    # Nullable, y ahi esta la diferencia con Product.precio: un servicio puede
    # no tener precio fijo, y "a presupuestar" es una respuesta valida. Numeric
    # y no Float por lo mismo que el producto: en binario 0.1 no es exactamente
    # 0.1, y con Float un precio vuelve de la base con centavos de diferencia.
    precio_estimado = db.Column(db.Numeric(10, 2), nullable=True)
    # "No estoy tomando trabajos por ahora" sin tener que borrar el servicio.
    # Los no disponibles los ve solo el dueño.
    disponible = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"<Service post_id={self.post_id} {self.titulo}>"

    @property
    def rubro_label(self):
        """El rubro como se muestra. Mismo patron que Post.category_label."""
        return Rubros.ETIQUETAS.get(self.rubro, self.rubro)

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "rubro": self.rubro,
            "rubro_label": self.rubro_label,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "zona_cobertura": self.zona_cobertura,
            # str y no float: el que consuma esto tiene que poder leer el
            # precio exacto (ver la columna). None cuando es a presupuestar,
            # que no es lo mismo que cero.
            "precio_estimado": (
                str(self.precio_estimado) if self.precio_estimado is not None else None
            ),
            "disponible": self.disponible,
        }
