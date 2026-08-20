from db import db, utcnow

# Cuantos productos puede cargar un emprendimiento. Mismo criterio que
# MAX_IMAGENES_POR_POST (5 fotos): un tope fijo, chico, que no molesta al uso
# real y corta el abuso. 50 porque un emprendimiento de feria o de barrio
# -tortas, velas, ropa tejida- no llega ni cerca; el que llega ya es un
# comercio que necesita categorias, buscador y paginado, o sea otra feature.
# No es configurable a proposito: cuando alguien lo choque de verdad vamos a
# saber cual es el numero que hace falta, hoy seria adivinar.
MAX_PRODUCTOS_POR_POST = 50


class Product(db.Model):
    """Un item con precio fijo del catalogo de un emprendimiento.

    Es catalogo y no tienda: no hay stock, ni variantes, ni carrito, ni pago.
    Es "esto vendo y a cuanto", para que el emprendedor no tenga que meter la
    lista de precios adentro de la descripcion del emprendimiento.

    Decia "un producto o servicio", y dejo de ser cierto cuando aparecio
    app/servicios/modelo.py: un servicio es un trabajo a presupuestar, con zona de
    cobertura, precio opcional y solicitudes de presupuesto. Un trabajo con
    precio cerrado ("service de bici, $8000") sigue entrando aca, pero como
    producto: lo que define esta tabla es el precio fijo, no la cosa vendida.

    Cuelga del emprendimiento (Post) y no del usuario, igual que los eventos:
    alguien puede tener una panaderia y una huerta, y cada una tiene lo suyo.
    """

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito desde el principio: son las dos
    # cosas que hubo que arreglar despues en el resto de las tablas (ver las
    # migraciones d09128dd029c, b30b4ba8d199 y d4a2b6f19c73). Sin el CASCADE,
    # MySQL usa RESTRICT y borrar un emprendimiento con productos falla con
    # IntegrityError; sin el nombre, la FK se llama distinto en cada motor y
    # cualquier migracion futura que la toque no tiene como referirse a ella.
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id", ondelete="CASCADE", name="fk_products_post_id_posts"),
        nullable=False, index=True,
    )
    nombre = db.Column(db.String(120), nullable=False)
    # Corta a proposito, como la de los eventos: es lo que entra en una tarjeta
    # del catalogo, no la descripcion larga del emprendimiento.
    descripcion = db.Column(db.String(300), nullable=True)
    # Numeric y no Float: en binario 0.1 no es exactamente 0.1, asi que con
    # Float un precio de 1999.95 puede volver de la base como 1999.9499999 y
    # cualquier suma de precios arrastra el error. Numeric guarda el decimal
    # tal cual y devuelve un Decimal. 10,2 da hasta 99.999.999,99, de sobra
    # para pesos incluso con inflacion.
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    # Una sola foto, no una galeria: el catalogo se ve en tarjetas chicas y la
    # segunda foto no se muestra en ningun lado. Guarda el nombre de archivo,
    # igual que Post.image y PostImage.filename.
    foto = db.Column(db.String(100), nullable=True)
    # "Sin stock por ahora" sin tener que borrar el producto y volver a
    # cargarlo despues. Los no disponibles los ve solo el dueño.
    disponible = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"<Product post_id={self.post_id} {self.nombre}>"

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            # str y no float: el que consuma esto tiene que poder leer el
            # precio exacto, y float lo volveria a romper (ver la columna).
            "precio": str(self.precio),
            "foto": self.foto,
            "disponible": self.disponible,
        }
