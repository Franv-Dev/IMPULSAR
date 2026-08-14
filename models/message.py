from db import db, utcnow


class Message(db.Model):
    """Un mensaje dentro de la conversacion sobre un emprendimiento.

    La conversacion queda identificada por (post_id, client_id): el otro
    lado siempre es el dueño del emprendimiento (post.author), asi que no
    hace falta guardarlo aparte. sender_id dice quien escribio ESTE mensaje
    en particular (puede ser el cliente o el dueño).
    """

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE": sin esto, MySQL usa RESTRICT por default y borrar un
    # post con al menos un mensaje falla con IntegrityError (mismo bug que se
    # arreglo en Report, ver migracion d09128dd029c). client_id/sender_id
    # quedan sin cascada: no hay borrado de usuarios implementado hoy, asi que
    # ese caso no puede darse todavia.
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    body = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    # Null mientras el destinatario no abrio la conversacion. Sirve para el
    # contador de "mensajes sin leer" del navbar.
    read_at = db.Column(db.DateTime, nullable=True)

    post = db.relationship("Post")
    client = db.relationship("User", foreign_keys=[client_id])
    sender = db.relationship("User", foreign_keys=[sender_id])

    def __repr__(self):
        return f"<Message post_id={self.post_id} client_id={self.client_id} sender_id={self.sender_id}>"

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "client_id": self.client_id,
            "sender_id": self.sender_id,
            "sender_username": self.sender.username if self.sender else None,
            "body": self.body,
            "created": self.created.isoformat() if self.created else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }
