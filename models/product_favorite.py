from db import db, utcnow


class ProductFavorite(db.Model):
    """Un producto del catalogo que un usuario marco para volver a encontrar.

    Es una tabla aparte y no una columna mas en favorites: un favorito de
    emprendimiento y uno de producto se guardan igual pero se miran distinto
    -- el primero es "esta gente me interesa", el segundo es "esta cosa a este
    precio" -- y meterlos en la misma tabla con un post_id o un product_id
    nullable obligaria a un CHECK de "uno u otro" y a que cada consulta se
    acuerde de filtrar cual de los dos esta buscando.

    Vive en models/ y no en app/blog/ porque el producto tampoco es del blog:
    Product esta en models/product.py y cuelga del emprendimiento, no del Post
    como entidad editorial.
    """

    __tablename__ = "product_favorites"

    # Un usuario no puede marcar el mismo producto dos veces: sin esto, dos
    # clicks casi simultaneos en el corazon insertarian dos filas. Es la misma
    # garantia (y el mismo motivo) que uq_favorite_user_post.
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "product_id", name="uq_product_favorite_user_product"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito en las dos FK, que es lo que
    # hubo que ir a arreglar despues en las tablas viejas (ver las migraciones
    # d09128dd029c, b30b4ba8d199 y b2b97d078fb2): sin el CASCADE, MySQL usa
    # RESTRICT y borrar un usuario -- o un producto que alguien marco -- falla
    # con IntegrityError; sin el nombre, la FK se llama distinto en cada motor
    # y ninguna migracion posterior puede referirse a ella.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id", ondelete="CASCADE", name="fk_product_favorites_user_id_users"
        ),
        nullable=False, index=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "products.id", ondelete="CASCADE",
            name="fk_product_favorites_product_id_products",
        ),
        nullable=False, index=True,
    )
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    producto = db.relationship("Product")

    def __repr__(self):
        return f"<ProductFavorite user_id={self.user_id} product_id={self.product_id}>"
