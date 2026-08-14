from db import db, utcnow


class Report(db.Model):
    """Reporte de contenido inapropiado: apunta a un emprendimiento o a una
    reseña, nunca a los dos ni a ninguno (ver el CheckConstraint)."""

    __tablename__ = "reports"

    __table_args__ = (
        db.CheckConstraint(
            "(post_id IS NOT NULL) != (review_id IS NOT NULL)",
            name="ck_report_target_xor",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True, index=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=True, index=True)

    reason = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Lo marca el admin desde el panel cuando ya tomo una decision (ver
    # views/admin.py resolve_report). No implica que se haya borrado nada:
    # puede resolverse dejando el contenido tal cual.
    resolved = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    resolved_at = db.Column(db.DateTime, nullable=True)

    reporter = db.relationship("User")
    post = db.relationship("Post")
    review = db.relationship("Review")

    def __repr__(self):
        objetivo = f"post_id={self.post_id}" if self.post_id else f"review_id={self.review_id}"
        return f"<Report {objetivo} reporter_id={self.reporter_id}>"

    def serialize(self):
        return {
            "id": self.id,
            "reporter_id": self.reporter_id,
            "post_id": self.post_id,
            "review_id": self.review_id,
            "reason": self.reason,
            "created": self.created.isoformat() if self.created else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
