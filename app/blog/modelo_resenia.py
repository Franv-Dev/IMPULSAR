from db import db, utcnow


class Review(db.Model):
    __tablename__ = "reviews"

    # Un usuario deja una sola resena por emprendimiento. Sin esto, alguien
    # puede cargar diez resenas de 5 estrellas sobre el mismo post e inflar
    # el promedio.
    __table_args__ = (
        db.UniqueConstraint("post_id", "user_id", name="uq_review_post_user"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" (c1f4a90b6e35): la resenia no tiene sentido sin el
    # emprendimiento resenado. Era la ultima FK a posts que no lo tenia; que la
    # app no fallara por eso era casualidad del cascade del ORM de mas abajo,
    # que borra las resenias antes de que el motor mire la FK.
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id", ondelete="CASCADE", name="fk_reviews_post_id_posts"),
        nullable=False,
    )
    # ondelete="CASCADE": la resenia se va con quien la escribio, aunque sea
    # sobre un emprendimiento ajeno. Es la decision tomada para b2b97d078fb2:
    # dejarla huerfana pediria hacer la columna nullable y que todo el codigo
    # que muestra el autor sepa vivir sin el.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_reviews_user_id_users"),
        nullable=False,
    )

    rating = db.Column(db.Integer, nullable=False)  # 1 a 5
    comment = db.Column(db.Text, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Null mientras la reseña no se edito nunca. No usa default/onupdate
    # automatico a proposito: se setea a mano en blog.add_review() cuando el
    # contenido realmente cambia, junto con la limpieza de reply/replied_at.
    updated_at = db.Column(db.DateTime, nullable=True)

    # Respuesta publica del dueño del emprendimiento a esta reseña. Vive en la
    # misma fila en vez de una tabla aparte porque una reseña tiene a lo sumo
    # una respuesta.
    reply = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)

    # Relaciones (útil para acceder desde el post y el usuario)
    post = db.relationship(
        "Post",
        backref=db.backref("reviews", lazy="dynamic", cascade="all, delete-orphan")
    )
    user = db.relationship("User")

    def __repr__(self):
        return f"<Review post_id={self.post_id} user_id={self.user_id} rating={self.rating}>"

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "created": self.created.isoformat() if self.created else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "reply": self.reply,
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
        }

    def to_dict(self):
        return self.serialize()
