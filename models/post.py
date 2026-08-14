from db import db, utcnow


class Categorias:
    """Categorias validas para un emprendimiento.

    Igual que Roles en models/user.py: los strings viven en un solo lugar
    para no repetirlos sueltos por vistas y templates.
    """

    ALIMENTOS = "alimentos"
    INDUMENTARIA = "indumentaria"
    SERVICIOS = "servicios"
    ARTESANIAS = "artesanias"
    TECNOLOGIA = "tecnologia"
    HOGAR = "hogar"
    OTROS = "otros"

    TODAS = (ALIMENTOS, INDUMENTARIA, SERVICIOS, ARTESANIAS, TECNOLOGIA, HOGAR, OTROS)

    ETIQUETAS = {
        ALIMENTOS: "Alimentos",
        INDUMENTARIA: "Indumentaria",
        SERVICIOS: "Servicios",
        ARTESANIAS: "Artesanías",
        TECNOLOGIA: "Tecnología",
        HOGAR: "Hogar",
        OTROS: "Otros",
    }


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    # OJO: la columna se llama "author" pero guarda un id, no un objeto User.
    # Para acceder al usuario usar la relacion author_user de mas abajo.
    author = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(100))
    body = db.Column(db.Text)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)
    image = db.Column(db.String(100), nullable=True)
    category = db.Column(
        db.String(50), nullable=False,
        default=Categorias.OTROS, server_default=Categorias.OTROS, index=True,
    )

    # Evita tener que hacer User.query.get(post.author) a mano en cada vista
    # y template: con esto se escribe directamente post.author_user.username.
    author_user = db.relationship("User", backref="posts", lazy="joined")

    #coordenadas 
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    address_street = db.Column(db.String(255), nullable=True)

    def __init__(self, author, title, body, image=None, latitude=None, longitude=None,
                 address_street=None, category=Categorias.OTROS):
        self.author = author
        self.title = title
        self.body = body
        self.image = image
        self.latitude = latitude
        self.longitude = longitude
        self.address_street = address_street
        self.category = category if category in Categorias.TODAS else Categorias.OTROS

    def __repr__(self):
        return f"Post: {self.title}"

    @property
    def category_label(self):
        return Categorias.ETIQUETAS.get(self.category, self.category)

    # Método para devolver JSON
    def serialize(self):
        return {
            "id": self.id,
            "author_id": self.author,  # ID del usuario autor
            "title": self.title,
            "body": self.body,
            "image": self.image,
            "category": self.category,
            "created": self.created.isoformat() if self.created else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address_street": self.address_street
        }

    # Alias estándar para usar en las rutas JSON
    def to_dict(self):
        return self.serialize()
