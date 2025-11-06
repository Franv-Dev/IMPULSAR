from db import db
from datetime import datetime

class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    rating = db.Column(db.Integer, nullable=False)  # 1 a 5
    comment = db.Column(db.Text, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
