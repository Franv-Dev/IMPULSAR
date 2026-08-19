from db import db, utcnow


class Favorite(db.Model):
    """Un emprendimiento que un usuario marco como favorito."""

    __tablename__ = "favorites"

    # Un usuario no puede marcar el mismo emprendimiento dos veces: sin esto,
    # dos clicks casi simultaneos en el boton insertarian dos filas.
    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_favorite_user_post"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE": el favorito es una marca privada de ese usuario sobre
    # contenido ajeno, no le sirve a nadie mas. Sin esto, borrar un usuario que
    # marco un solo favorito fallaba con IntegrityError (ver b2b97d078fb2).
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_favorites_user_id_users"),
        nullable=False, index=True,
    )
    # ondelete="CASCADE": sin esto, MySQL usa RESTRICT por default y borrar un
    # post con al menos un favorito falla con IntegrityError (mismo bug que
    # se arreglo en Report, ver migracion d09128dd029c).
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    post = db.relationship("Post")

    def __repr__(self):
        return f"<Favorite user_id={self.user_id} post_id={self.post_id}>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "post_id": self.post_id,
            "created": self.created.isoformat() if self.created else None,
        }
