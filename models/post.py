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


# Cuantas fotos puede tener un emprendimiento contando la principal
# (Post.image). Las que sobran van en post_images (ver models/post_image.py).
MAX_IMAGENES_POR_POST = 5


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

    # Cuantas veces se vio el detalle. No cuenta las vistas del propio dueño
    # (ver blog.detail()): sin eso, el emprendedor inflaria su propia
    # metrica cada vez que revisa su publicacion.
    views_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    # Evita tener que hacer User.query.get(post.author) a mano en cada vista
    # y template: con esto se escribe directamente post.author_user.username.
    author_user = db.relationship("User", backref="posts", lazy="joined")

    # cascade="all, delete-orphan": la FK ya borra en la base, pero sin esto el
    # ORM intenta dejar las filas huerfanas poniendo post_id en NULL cuando se
    # borra un Post desde la sesion, y la columna es NOT NULL.
    imagenes = db.relationship(
        "PostImage",
        backref="post",
        cascade="all, delete-orphan",
        order_by="PostImage.posicion",
    )

    # Mismo criterio que imagenes: la FK ya borra en la base, pero sin el
    # cascade del ORM borrar un Post desde la sesion intenta dejar los eventos
    # huerfanos con post_id en NULL, que es NOT NULL.
    eventos = db.relationship(
        "Event",
        backref="post",
        cascade="all, delete-orphan",
        order_by="Event.fecha",
    )

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

    @property
    def galeria(self):
        """Todas las fotos del emprendimiento, con la principal primero.

        Los listados siguen usando post.image directamente; esto es para el
        detalle, que las muestra todas juntas.
        """
        fotos = [self.image] if self.image else []
        fotos += [imagen.filename for imagen in self.imagenes]
        return fotos

    @property
    def lugares_de_imagen_libres(self):
        """Cuantas fotos mas se pueden subir antes de llegar al maximo."""
        return max(0, MAX_IMAGENES_POR_POST - len(self.galeria))

    # Método para devolver JSON
    def serialize(self, include_views=False):
        """include_views=True solo cuando quien pregunta es el dueño del post:
        /api/posts/ es publica y sin auth, así que por default no viaja."""
        data = {
            "id": self.id,
            "author_id": self.author,  # ID del usuario autor
            "title": self.title,
            "body": self.body,
            "image": self.image,
            "category": self.category,
            "category_label": self.category_label,
            "created": self.created.isoformat() if self.created else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address_street": self.address_street
        }
        if include_views:
            data["views_count"] = self.views_count
        return data

    # Alias estándar para usar en las rutas JSON
    def to_dict(self, include_views=False):
        return self.serialize(include_views=include_views)
