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
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    rating = db.Column(db.Integer, nullable=False)  # 1 a 5
    comment = db.Column(db.Text, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

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
        }

    def to_dict(self):
        return self.serialize()
