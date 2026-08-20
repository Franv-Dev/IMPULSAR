from db import db, utcnow


class PostImage(db.Model):
    """Una foto adicional de la galeria de un emprendimiento.

    La foto principal sigue viviendo en Post.image: es la que ya usan las
    tarjetas del home, del perfil y de "mis emprendimientos", y moverla aca
    obligaria a tocar todos esos listados sin ganar nada. Esta tabla guarda las
    que se suman a esa, y entre las dos no se pasan de MAX_IMAGENES_POR_POST.
    """

    __tablename__ = "post_images"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" a nivel de base y no solo en el ORM: sin esto MySQL
    # usa RESTRICT por default y borrar un emprendimiento con fotos falla con
    # IntegrityError. Es el mismo bug que ya aparecio en reports, favorites y
    # messages (ver migraciones d09128dd029c y b30b4ba8d199).
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename = db.Column(db.String(100), nullable=False)
    # Para que la galeria se muestre siempre en el mismo orden: sin esto el
    # orden depende de lo que devuelva la base, que no esta garantizado.
    posicion = db.Column(db.Integer, nullable=False, default=0)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"<PostImage post_id={self.post_id} {self.filename}>"

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "filename": self.filename,
            "posicion": self.posicion,
        }
