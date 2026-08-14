from db import db, utcnow


class Roles:
    """Roles validos del sistema.

    Estan aca para no repetir los strings sueltos por el codigo: si se escribe
    "Usuario" en un lado y "usuario" en otro, cualquier chequeo de permisos
    falla en silencio.
    """

    USUARIO = "usuario"
    EMPRENDEDOR = "emprendedor"
    ADMIN = "admin"

    TODOS = (USUARIO, EMPRENDEDOR, ADMIN)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # unique a nivel de base de datos: validarlo solo en Python tiene una
    # condicion de carrera (dos registros simultaneos pasan los dos el chequeo).
    # index ademas acelera los filter_by(username=...) del login.
    username = db.Column(db.String(50), unique=True, index=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    rol = db.Column(db.String(50), nullable=False, default=Roles.USUARIO)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    biography = db.Column(db.Text, default="Biografía")
    avatar = db.Column(db.String(100), nullable=True)

    # Un admin banea cuentas desde el panel; un usuario baneado no puede
    # iniciar sesion (ver views/auth.py login() y api_login()).
    is_banned = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    # Datos de contacto publico del emprendedor. Todos opcionales: no todos
    # los usuarios son emprendedores ni quieren publicar su telefono.
    phone = db.Column(db.String(30), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)
    instagram_url = db.Column(db.String(255), nullable=True)
    facebook_url = db.Column(db.String(255), nullable=True)
    twitter_url = db.Column(db.String(255), nullable=True)

    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    address_street = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __init__(self, username, password, email, rol=Roles.USUARIO,
                 biography="Biografía", latitude=None, longitude=None,
                 address_street=None, avatar=None, phone=None, whatsapp=None,
                 instagram_url=None, facebook_url=None, twitter_url=None):
        self.username = username
        self.password = password
        # Se normaliza al guardar para que "Admin", "ADMIN" y "admin" sean lo
        # mismo y los chequeos de permisos no dependan de como se escribio.
        self.rol = (rol or Roles.USUARIO).strip().lower()
        self.email = (email or "").strip().lower()
        self.biography = biography
        self.avatar = avatar
        self.phone = phone
        self.whatsapp = whatsapp
        self.instagram_url = instagram_url
        self.facebook_url = facebook_url
        self.twitter_url = twitter_url
        self.latitude = latitude
        self.longitude = longitude
        self.address_street = address_street

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
            "is_banned": self.is_banned,
            "biography": self.biography,
            "avatar": self.avatar,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "instagram_url": self.instagram_url,
            "facebook_url": self.facebook_url,
            "twitter_url": self.twitter_url,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address_street": self.address_street,
        }

    # Alias más estándar para usar en la API
    def to_dict(self):
        return self.serialize()
