from db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.Text)
    rol = db.Column(db.String(50))
    email = db.Column(db.String(50))

    def __init__(self, username, password, rol, email):
        self.username = username
        self.password = password
        self.rol = rol
        self.email = email

    def __repr__(self):
        # Para debugging/logs
        return f"User:{self.username}"

    # Método para devolver el usuario como JSON
    def serialize(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "rol": self.rol,
        }

    # Alias más estándar para usar en la API
    def to_dict(self):
        return self.serialize()
