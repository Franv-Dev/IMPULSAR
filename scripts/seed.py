"""Carga datos de prueba en la base, para poder navegar la app con contenido.

No es un one-off: se puede volver a correr. Todo lo que crea queda marcado
(los usuarios con el dominio de EMAIL_SEED, las imagenes con el prefijo
PREFIJO_IMAGEN), asi que `--reset` y `--borrar` saben exactamente que sacar.

    python scripts/seed.py            # carga, si todavia no hay datos de seed
    python scripts/seed.py --reset    # borra los de antes y vuelve a cargar
    python scripts/seed.py --borrar   # solo borra

QUE BORRA EXACTAMENTE --borrar (y --reset antes de recargar)

No es solo "lo que creo el seed". Borra los usuarios de seed, sus
emprendimientos y todo lo que cuelga de esos emprendimientos, y eso incluye
filas de usuarios REALES que apunten a contenido del seed:

- la resenia que un usuario tuyo le dejo a un emprendimiento del seed,
- el favorito que marco sobre uno de ellos,
- los mensajes de esa conversacion,
- el reporte que hizo sobre uno de esos posts,
- y el follow a un usuario del seed (en cualquiera de las dos direcciones).

No hay forma de evitarlo: si se va el emprendimiento, la resenia que apunta a
el no puede quedar. Lo que si esta garantizado es lo otro: nada que no
referencie contenido del seed se toca, ni un usuario real, ni sus
emprendimientos, ni sus resenias sobre emprendimientos reales.

Las fotos son imagenes generadas (un degrade con las iniciales), no fotos de
verdad: son para ver como queda la maqueta, no para simular contenido real.

Del disco borra exactamente los archivos que nombran las filas de seed de la
base a la que esta conectado (Post.image, PostImage.filename y Product.foto),
uno por uno. No barre el directorio buscando el prefijo, y la diferencia
importa: static/uploads es una sola carpeta para todas las bases, asi que un
glob de seed_* apuntando a una base se llevaba tambien las imagenes de otra
base sembrada aparte, dejandola con las filas apuntando a archivos que ya no
estaban. Por lo mismo, cada corrida les pone un sufijo propio al nombre (ver
CORRIDA): dos bases sembradas por separado no comparten un solo archivo.

Corre contra la base que diga el entorno, igual que la app: por defecto la de
desarrollo del .env. Si esa base no esta en localhost, pide confirmacion
antes de tocar nada (ver _confirmar_si_no_es_local).
"""

import os
import random
import sys
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

# El script vive en scripts/, asi que la raiz del proyecto no esta en el path
# cuando se lo invoca directamente.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import db, utcnow  # noqa: E402
from main import create_app  # noqa: E402
from models.event import Event  # noqa: E402
from app.blog.modelo_favorito import Favorite  # noqa: E402
from app.perfil.modelo_follow import Follow  # noqa: E402
from app.perfil.modelo_horario import Horario  # noqa: E402
from models.message import Message  # noqa: E402
from app.blog.modelo_post import Categorias, Post  # noqa: E402
from app.blog.modelo_imagen import PostImage  # noqa: E402
from models.product import Product  # noqa: E402
from app.blog.modelo_reporte import Report  # noqa: E402
from app.blog.modelo_resenia import Review  # noqa: E402
from app.servicios.modelo import Rubros, Service  # noqa: E402
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest  # noqa: E402
from models.user import Roles, User  # noqa: E402

# Marcas que identifican lo que creo este script.
EMAIL_SEED = "@seed.impulsar.test"
PREFIJO_IMAGEN = "seed_"

# Sufijo distinto en cada corrida. Sin esto, dos bases sembradas por
# separado generan los mismos nombres de archivo (seed_post_0.png y
# compania) sobre la misma carpeta static/uploads: la segunda pisa las
# imagenes de la primera, y borrar una deja a la otra sin fotos.
CORRIDA = uuid.uuid4().hex[:8]

# La misma para todos, y escrita aca a proposito: son datos de prueba de una
# base de desarrollo, no hay nada que proteger y hace falta poder entrar.
PASSWORD = "impulsar123"

# Maipu, Mendoza. Las coordenadas van a mano y no por geocoding: el seed no
# tiene por que depender de una API externa para correr.
CENTRO = (-32.9833, -68.7833)


# ------------------------------------------------------------------ imagenes

def _carpeta_uploads(app):
    # La misma carpeta que usa la app (config.UPLOAD_FOLDER); ver
    # services/uploads.py carpeta_uploads().
    return app.config["UPLOAD_FOLDER"]


def _generar_imagen(carpeta, nombre, texto, color):
    """Un PNG con un degrade y unas iniciales. Placeholder, no una foto."""
    from PIL import Image, ImageDraw, ImageFont

    ancho, alto = 800, 600
    imagen = Image.new("RGB", (ancho, alto), color)
    dibujo = ImageDraw.Draw(imagen)

    # Degrade vertical simple: se oscurece hacia abajo.
    for y in range(alto):
        factor = 1 - (y / alto) * 0.45
        dibujo.line(
            [(0, y), (ancho, y)],
            fill=tuple(int(canal * factor) for canal in color),
        )

    try:
        fuente = ImageFont.truetype("arial.ttf", 120)
    except OSError:
        # En una maquina sin esa fuente el placeholder sale igual, mas chico.
        fuente = ImageFont.load_default()

    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    dibujo.text(
        ((ancho - caja[2] + caja[0]) / 2, (alto - caja[3] + caja[1]) / 2),
        texto, font=fuente, fill=(255, 255, 255),
    )

    ruta = os.path.join(carpeta, nombre)
    imagen.save(ruta, format="PNG", optimize=True)
    return nombre


def _nombre_de_imagen(que):
    """seed_<corrida>_<que>.png. El prefijo para reconocerlas de un
    vistazo en la carpeta; la corrida para que no se pisen entre bases."""
    return f"{PREFIJO_IMAGEN}{CORRIDA}_{que}.png"


def _iniciales(titulo):
    palabras = [p for p in titulo.split() if p[0].isalpha()]
    return "".join(p[0] for p in palabras[:2]).upper() or "IM"


# --------------------------------------------------------------------- datos

# Los usernames van sin tilde y de una sola palabra a proposito: el login
# busca por username exacto (ver views/auth.login), asi que "Lucía Herrera"
# obligaria a escribir el nombre completo con tilde para entrar a probar.
EMPRENDEDORES = ["Lucia", "Joaquin", "Carla", "Diego", "Valentina"]

CLIENTES = ["Nicolas", "Camila", "Bruno"]

# (dueño, titulo, categoria, descripcion, direccion, color de la foto)
EMPRENDIMIENTOS = [
    ("Lucia", "Huerta La Semilla", Categorias.ALIMENTOS,
     "Verduras agroecológicas de estación, cosechadas el mismo día que las "
     "entregamos. Bolsón semanal a domicilio en Maipú y alrededores.",
     "Ozamis 1200, Maipú, Mendoza", (86, 140, 74)),
    ("Lucia", "Conservas del Valle", Categorias.ALIMENTOS,
     "Dulces, escabeches y conservas hechos con fruta y verdura de la zona. "
     "Sin conservantes, en frascos de vidrio retornables.",
     "San Martín 850, Maipú, Mendoza", (176, 96, 60)),
    ("Joaquin", "Tejidos Andinos", Categorias.INDUMENTARIA,
     "Ruanas, chales y bufandas tejidos a telar con lana de oveja y llama. "
     "Cada pieza es única y lleva entre dos y cinco días de trabajo.",
     "Maza 340, Maipú, Mendoza", (120, 92, 160)),
    ("Joaquin", "Zapatillas Pintadas", Categorias.INDUMENTARIA,
     "Zapatillas de lona intervenidas a mano, con diseños a pedido. "
     "También restauramos y repintamos las que ya tenés.",
     "Vergara 90, Maipú, Mendoza", (60, 130, 176)),
    ("Carla", "Velas Aroma Sur", Categorias.HOGAR,
     "Velas de soja con esencias naturales, en frascos reutilizados. "
     "Armamos combos para regalo y velas personalizadas para eventos.",
     "Alsina 455, Maipú, Mendoza", (200, 150, 70)),
    ("Carla", "Cerámica Maipú", Categorias.ARTESANIAS,
     "Vajilla de gres hecha a torno: tazas, platos y fuentes para uso diario. "
     "Aptas para horno y lavavajillas. También damos talleres los sábados.",
     "Pescara 1100, Maipú, Mendoza", (150, 110, 95)),
    ("Diego", "Bicicletería El Piñón", Categorias.SERVICIOS,
     "Service completo, armado de ruedas y puesta a punto de cambios. "
     "Retiramos y entregamos la bici a domicilio sin costo dentro de Maipú.",
     "Urquiza 620, Maipú, Mendoza", (70, 70, 80)),
    ("Diego", "Reparación de Notebooks", Categorias.TECNOLOGIA,
     "Cambio de pantallas, teclados y baterías, limpieza y cambio de pasta "
     "térmica. Diagnóstico sin cargo y presupuesto antes de tocar nada.",
     "Godoy Cruz 210, Maipú, Mendoza", (55, 110, 130)),
    ("Valentina", "Cosmética Natural Ruda", Categorias.OTROS,
     "Jabones, bálsamos y aceites hechos con ingredientes de origen vegetal. "
     "Sin testeo en animales y con envases que recibimos de vuelta.",
     "Terrada 75, Maipú, Mendoza", (110, 150, 120)),
    ("Valentina", "Tostado Sur", Categorias.ALIMENTOS,
     "Café de especialidad tostado acá, en lotes chicos. Vendemos en grano o "
     "molido a tu método, y prestamos molinillo a los clientes del barrio.",
     "Sáenz Peña 1450, Maipú, Mendoza", (120, 80, 55)),
]

# titulo del emprendimiento -> productos (nombre, precio, disponible, descripcion)
PRODUCTOS = {
    "Huerta La Semilla": [
        ("Bolsón semanal chico", "6500.00", True,
         "Seis variedades de verdura de estación, para una o dos personas."),
        ("Bolsón semanal grande", "9800.00", True,
         "Diez variedades, alcanza para una familia de cuatro."),
        ("Docena de huevos de campo", "4200.00", True, None),
        ("Plantines de aromáticas", "1500.00", False,
         "Albahaca, perejil y romero. Vuelven en primavera."),
    ],
    "Conservas del Valle": [
        ("Dulce de durazno 400g", "3800.00", True, "Fruta de temporada, poca azúcar."),
        ("Berenjenas en escabeche", "4500.00", True, None),
        ("Tomate triturado 700g", "2900.00", True, None),
        ("Dulce de membrillo 500g", "4100.00", False, "Se agotó, vuelve en otoño."),
    ],
    "Tejidos Andinos": [
        ("Ruana de lana de oveja", "78000.00", True,
         "Tejida a telar, talle único. Colores naturales sin teñir."),
        ("Bufanda de llama", "32000.00", True, None),
        ("Chal calado", "45000.00", True, "Ideal para entretiempo."),
    ],
    "Velas Aroma Sur": [
        ("Vela de soja lavanda", "7200.00", True, "Frasco de 200g, 30 horas de duración."),
        ("Combo tres velas", "19000.00", True, "Lavanda, cítricos y vainilla."),
        ("Vela personalizada para evento", "9500.00", True,
         "Con etiqueta a tu gusto, mínimo diez unidades."),
    ],
    "Cerámica Maipú": [
        ("Taza de gres", "12500.00", True, "Apta para horno y lavavajillas."),
        ("Juego de cuatro platos", "48000.00", True, None),
        ("Taller de torno (2 horas)", "25000.00", True,
         "Sábados a la mañana, cupo de seis personas."),
    ],
    "Tostado Sur": [
        ("Café en grano 250g", "8900.00", True, "Blend de la casa, tueste medio."),
        ("Café molido 250g", "8900.00", True, "Decinos tu método y lo molemos así."),
        ("Bolsa de 1kg", "31000.00", True, None),
    ],
}

# titulo -> eventos (titulo, dias desde hoy, hora, descripcion)
EVENTOS = [
    ("Huerta La Semilla", "Feria agroecológica de la plaza", 6, time(9, 0),
     "Con toda la verdura de la semana y plantines a precio de feria."),
    ("Cerámica Maipú", "Taller abierto de torno", 13, time(10, 30),
     "Para quienes nunca tocaron el torno. Se llevan lo que hagan."),
    ("Tostado Sur", "Cata de café de especialidad", 3, time(18, 0),
     "Probamos tres orígenes distintos. Cupo limitado."),
    ("Tejidos Andinos", "Muestra de telar en el Museo", 21, None,
     "Exposición de piezas grandes, entrada libre."),
    ("Velas Aroma Sur", "Feria navideña", -18, time(17, 0),
     "Estuvimos con los combos de regalo."),
    ("Conservas del Valle", "Jornada de cosecha y conserva", -40, time(8, 30),
     "Vinimos con los frascos del año pasado."),
]

# emprendimiento -> servicios (titulo, rubro, descripcion, zona, precio o None)
# El precio en None es el caso de "a presupuestar", que es la diferencia con
# los productos: se cotiza contra el caso de cada cliente.
SERVICIOS = {
    "Bicicletería El Piñón": [
        ("Service completo de bicicleta", Rubros.OTROS,
         "Ajuste de cambios y frenos, centrado de ruedas y limpieza de transmisión.",
         "Maipú y alrededores", "18000.00"),
        ("Armado de rueda a medida", Rubros.OTROS,
         "Rayos, llanta y maza a elección. Se cotiza según los materiales.",
         "Maipú", None),
    ],
    "Reparación de Notebooks": [
        ("Cambio de pantalla", Rubros.INFORMATICA,
         "Traé el equipo o lo retiramos. El precio depende del modelo.",
         "Todo el Gran Mendoza", None),
        ("Limpieza y cambio de pasta térmica", Rubros.INFORMATICA,
         "Para equipos que se apagan solos o andan muy calientes.",
         "Todo el Gran Mendoza", "25000.00"),
    ],
}

# (cliente, servicio, descripcion, zona, estado, precio de respuesta, mensaje)
# Una de cada estado, para poder ver el panel del prestador con las tres.
SOLICITUDES = [
    ("Nicolas", "Cambio de pantalla",
     "Se me rompió la pantalla de una Lenovo ideapad 3. ¿La reparan?",
     None, EstadosSolicitud.PENDIENTE, None, None),
    ("Camila", "Service completo de bicicleta",
     "La bici hace ruido en los cambios y los frenos rozan. Es una rodado 29.",
     "Coquimbito", EstadosSolicitud.RESPONDIDA, "18000.00",
     "La dejamos como nueva. Traela un martes y te la entrego el jueves."),
    ("Bruno", "Armado de rueda a medida",
     "Quiero armar una rueda trasera para uso urbano, algo resistente.",
     None, EstadosSolicitud.CERRADA, "62000.00",
     "Con maza Shimano y llanta doble pared queda en ese precio."),
]

# (autor del review, emprendimiento, rating, comentario, respuesta del dueño)
RESENIAS = [
    ("Nicolas", "Huerta La Semilla", 5,
     "El bolsón llegó impecable y todo durísimo de fresco. Ya van tres semanas seguidas.",
     "¡Gracias Nicolás! La semana que viene sumamos acelga."),
    ("Camila", "Huerta La Semilla", 4,
     "Muy buena calidad. Solo que la entrega llegó un rato más tarde de lo pactado.", None),
    ("Bruno", "Tejidos Andinos", 5,
     "La ruana es una obra de arte. Se nota el trabajo que tiene atrás.", None),
    ("Camila", "Velas Aroma Sur", 5,
     "Compré el combo para regalar y quedó bárbaro. El aroma dura muchísimo.",
     "Gracias Camila, un gusto."),
    ("Nicolas", "Bicicletería El Piñón", 4,
     "Dejó la bici andando como nueva y me la trajo a casa. Recomendable.", None),
    ("Bruno", "Tostado Sur", 5,
     "El mejor café que conseguí en Maipú. Además te explican cómo prepararlo.", None),
    ("Camila", "Cerámica Maipú", 3,
     "Las tazas son lindas pero una llegó con una falla en el esmalte.",
     "Perdón Camila, escribinos y te la cambiamos sin cargo."),
]

# (cliente, emprendimiento, [(quien escribe, texto), ...], cuantos quedan sin leer)
CONVERSACIONES = [
    ("Nicolas", "Huerta La Semilla", [
        ("cliente", "Hola! Hacen entrega en Coquimbito?"),
        ("dueño", "Hola Nicolás! Sí, los martes y viernes a la tarde."),
        ("cliente", "Genial. Anotame un bolsón grande para el viernes."),
        ("dueño", "Listo, queda anotado. Te aviso cuando salga el reparto."),
    ], 0),
    ("Camila", "Cerámica Maipú", [
        ("cliente", "Buenas! Queda lugar en el taller del sábado?"),
        ("dueño", "Hola Camila! Quedan dos lugares."),
        ("cliente", "Perfecto, reservame uno."),
    ], 1),
    ("Bruno", "Reparación de Notebooks", [
        ("cliente", "Hola, se me rompió la pantalla de una Lenovo. Reparan ese modelo?"),
        ("cliente", "Es una ideapad 3, por si sirve el dato."),
    ], 2),
]

# usuario -> emprendimientos que marca como favoritos
FAVORITOS = {
    "Nicolas": ["Huerta La Semilla", "Tostado Sur", "Bicicletería El Piñón"],
    "Camila": ["Velas Aroma Sur", "Cerámica Maipú"],
    "Bruno": ["Tejidos Andinos"],
}

# usuario -> a quienes sigue
SEGUIMIENTOS = {
    "Nicolas": ["Lucia", "Valentina"],
    "Camila": ["Carla"],
    "Bruno": ["Joaquin", "Valentina"],
    "Lucia": ["Carla"],
}

# usuario -> horarios (dia_semana, abre, cierra) o (dia, None, None) si cierra
HORARIOS = {
    "Lucia": [(0, time(9, 0), time(13, 0)), (1, time(9, 0), time(13, 0)),
              (2, time(9, 0), time(13, 0)), (3, time(9, 0), time(13, 0)),
              (4, time(9, 0), time(17, 0)), (5, time(9, 0), time(12, 0)),
              (6, None, None)],
    "Carla": [(0, None, None), (1, time(15, 0), time(20, 0)),
              (2, time(15, 0), time(20, 0)), (3, time(15, 0), time(20, 0)),
              (4, time(15, 0), time(20, 0)), (5, time(10, 0), time(13, 0)),
              (6, None, None)],
    "Diego": [(0, time(8, 30), time(18, 0)), (1, time(8, 30), time(18, 0)),
              (2, time(8, 30), time(18, 0)), (3, time(8, 30), time(18, 0)),
              (4, time(8, 30), time(18, 0)), (5, None, None), (6, None, None)],
}


# --------------------------------------------------------------------- borrar

def _usuarios_de_seed():
    return User.query.filter(User.email.like(f"%{EMAIL_SEED}")).all()


def _archivos_de(ids_posts, ids_usuarios=()):
    """Los nombres de archivo que referencian las filas que borra borrar().

    Se pregunta a la base en vez de barrer el directorio buscando el prefijo:
    static/uploads es una sola carpeta para todas las bases, asi que un glob
    de seed_* se lleva tambien las imagenes de otra base sembrada aparte. Los
    nombres salen de las cuatro columnas que guardan uno: Post.image,
    PostImage.filename, Product.foto y ServiceRequest.foto.

    La foto de una solicitud es el unico caso que no cuelga de un post: borrar()
    se lleva tambien las solicitudes que un usuario del seed hizo sobre un
    servicio real, y esas cuelgan de un post ajeno. Por eso ademas de los posts
    recibe los usuarios, con el mismo criterio con el que se borran las filas:
    si el criterio de los dos lados no coincide, la fila se va y el archivo
    queda huerfano en el disco para siempre.
    """
    nombres = []

    if ids_posts:
        for post in Post.query.filter(Post.id.in_(ids_posts)):
            nombres.append(post.image)
        for (nombre,) in db.session.query(PostImage.filename).filter(
            PostImage.post_id.in_(ids_posts)
        ):
            nombres.append(nombre)
        for (nombre,) in db.session.query(Product.foto).filter(
            Product.post_id.in_(ids_posts)
        ):
            nombres.append(nombre)

    condiciones = []
    if ids_posts:
        condiciones.append(ServiceRequest.service_id.in_(
            db.session.query(Service.id).filter(Service.post_id.in_(ids_posts))
        ))
    if ids_usuarios:
        condiciones.append(ServiceRequest.cliente_id.in_(ids_usuarios))
    if condiciones:
        for (nombre,) in db.session.query(ServiceRequest.foto).filter(
            db.or_(*condiciones)
        ):
            nombres.append(nombre)

    return [n for n in nombres if n]


def _borrar_archivos(app, nombres):
    """Borra esos archivos del disco. Solo esos, por nombre exacto."""
    carpeta = _carpeta_uploads(app)
    borradas = 0
    for nombre in nombres:
        try:
            os.remove(os.path.join(carpeta, nombre))
            borradas += 1
        except FileNotFoundError:
            # Ya no estaba: nada que hacer, y no es un error.
            pass
        except OSError:
            print(f"  (no se pudo borrar {nombre})")
    return borradas


def borrar(app):
    """Saca todo lo que dejo este script, y nada mas.

    El orden es a mano y no por cascada porque hay cinco FK que apuntan a
    users sin ON DELETE CASCADE (favorites.user_id, messages.client_id,
    messages.sender_id, reports.reporter_id y reviews.user_id): borrar el
    usuario de una sin limpiar eso primero falla con IntegrityError.

    service_requests.cliente_id SI tiene ON DELETE CASCADE, asi que no
    necesitaria estar en esta lista para que el borrado no falle. Va igual, y
    por la otra mitad de lo que hace esta funcion: las solicitudes que un
    usuario REAL hizo sobre un servicio del seed tienen que irse con el seed,
    y la unica forma de que se vayan por cascada seria borrando al usuario
    real, que es justo lo que esta funcion no hace.
    """
    usuarios = _usuarios_de_seed()
    if not usuarios:
        print("No hay datos de seed que borrar.")
        # Y por lo tanto tampoco hay archivos: los nombres salen de las filas.
        print("Ningún archivo tocado.")
        return

    ids = [u.id for u in usuarios]
    posts = Post.query.filter(Post.author.in_(ids)).all()
    ids_posts = [p.id for p in posts]

    # Los nombres de archivo se juntan ANTES de borrar las filas: despues no
    # queda de donde sacarlos.
    archivos = _archivos_de(ids_posts, ids)

    def borrar_filas(modelo, condicion):
        modelo.query.filter(condicion).delete(synchronize_session=False)

    # Las solicitudes van primero porque cuelgan de services, que cuelga de
    # posts: si se borrara el post antes, la cascada del ORM ya se las habria
    # llevado y este filtro no encontraria las del usuario real.
    ids_servicios = [
        fila[0] for fila in db.session.query(Service.id).filter(
            Service.post_id.in_(ids_posts or [0])
        )
    ]
    borrar_filas(ServiceRequest, db.or_(
        ServiceRequest.cliente_id.in_(ids),
        ServiceRequest.service_id.in_(ids_servicios or [0]),
    ))

    borrar_filas(Report, db.or_(
        Report.reporter_id.in_(ids),
        Report.post_id.in_(ids_posts or [0]),
    ))
    borrar_filas(Follow, db.or_(
        Follow.follower_id.in_(ids), Follow.followed_id.in_(ids)
    ))
    borrar_filas(Favorite, db.or_(
        Favorite.user_id.in_(ids), Favorite.post_id.in_(ids_posts or [0])
    ))
    borrar_filas(Message, db.or_(
        Message.client_id.in_(ids), Message.sender_id.in_(ids),
        Message.post_id.in_(ids_posts or [0]),
    ))
    borrar_filas(Review, db.or_(
        Review.user_id.in_(ids), Review.post_id.in_(ids_posts or [0])
    ))
    db.session.flush()

    for post in posts:
        # Por el ORM y no con delete() masivo, para que se lleve productos,
        # eventos e imagenes con la cascada del modelo.
        db.session.delete(post)
    db.session.flush()

    for usuario in usuarios:
        db.session.delete(usuario)
    db.session.commit()
    print(f"Borrados {len(usuarios)} usuarios de seed y sus {len(posts)} emprendimientos.")

    borradas = _borrar_archivos(app, archivos)
    print(f"Borradas {borradas} imágenes del disco (de {len(archivos)} que referenciaban).")


# --------------------------------------------------------------------- cargar

def cargar(app):
    # Semilla fija: dos corridas del script dan el mismo resultado, asi no
    # cambia lo que ves cada vez que se recarga la base.
    azar = random.Random(1985)
    carpeta = _carpeta_uploads(app)
    os.makedirs(carpeta, exist_ok=True)
    ahora = utcnow()
    hoy = date.today()

    usuarios = {}
    for nombre in EMPRENDEDORES + CLIENTES:
        alias = nombre.lower()
        rol = Roles.EMPRENDEDOR if nombre in EMPRENDEDORES else Roles.USUARIO
        usuario = User(
            username=nombre,
            email=f"{alias}{EMAIL_SEED}",
            password=generate_password_hash(PASSWORD),
            rol=rol,
            biography=(
                f"Soy {nombre} y vendo en ferias de Maipú desde 2021. "
                "Escribime por acá y coordinamos."
                if rol == Roles.EMPRENDEDOR else
                f"{nombre}, de Maipú. Me gusta comprarle a quien produce."
            ),
            location="Maipú, Mendoza",
            phone="261 555-0100",
            whatsapp="261 555-0100" if rol == Roles.EMPRENDEDOR else None,
            instagram_url=(
                f"https://instagram.com/{alias}.maipu" if rol == Roles.EMPRENDEDOR else None
            ),
        )
        # El slug se calcula solo en el __init__, pero el username de seed
        # puede chocar con uno que ya este cargado a mano: se fuerza uno
        # propio para que la corrida no dependa de lo que ya haya en la base.
        usuario.slug = User.generar_slug_unico(f"{alias}-seed")
        db.session.add(usuario)
        # Indexado por username, que es como lo nombran las tablas de datos.
        usuarios[nombre] = usuario
    db.session.flush()

    posts = {}
    for numero, (alias, titulo, categoria, cuerpo, direccion, color) in enumerate(EMPRENDIMIENTOS):
        # Las coordenadas se desparraman alrededor del centro para que el mapa
        # y el orden "cerca mío" tengan algo que mostrar.
        post = Post(
            author=usuarios[alias].id,
            title=titulo,
            body=cuerpo,
            category=categoria,
            address_street=direccion,
            latitude=CENTRO[0] + azar.uniform(-0.035, 0.035),
            longitude=CENTRO[1] + azar.uniform(-0.035, 0.035),
            image=_generar_imagen(
                carpeta, _nombre_de_imagen(f"post_{numero}"), _iniciales(titulo), color
            ),
        )
        post.views_count = azar.randint(4, 190)
        db.session.add(post)
        posts[titulo] = post

        # Una galeria corta para los primeros, para ver la grilla de fotos.
        if numero < 4:
            for extra in range(2):
                post.imagenes.append(PostImage(
                    filename=_generar_imagen(
                        carpeta, _nombre_de_imagen(f"post_{numero}_{extra}"),
                        _iniciales(titulo), tuple(min(255, c + 45 * (extra + 1)) for c in color),
                    ),
                    posicion=extra,
                ))
    db.session.flush()

    colores = {fila[1]: fila[5] for fila in EMPRENDIMIENTOS}
    total_productos = 0
    for numero, (titulo, lista) in enumerate(PRODUCTOS.items()):
        for indice, (nombre, precio, disponible, descripcion) in enumerate(lista):
            db.session.add(Product(
                post_id=posts[titulo].id,
                nombre=nombre,
                descripcion=descripcion,
                # Decimal y no float, por lo mismo que la columna es Numeric.
                precio=Decimal(precio),
                disponible=disponible,
                # Foto solo en los dos primeros de cada catalogo, para ver las
                # dos variantes de tarjeta (con imagen y sin).
                foto=_generar_imagen(
                    carpeta, _nombre_de_imagen(f"prod_{numero}_{indice}"),
                    _iniciales(nombre),
                    tuple(min(255, c + 25) for c in colores[titulo]),
                ) if indice < 2 else None,
            ))
            total_productos += 1

    servicios = {}
    for titulo, lista in SERVICIOS.items():
        for nombre, rubro, descripcion, zona, precio in lista:
            servicio = Service(
                post_id=posts[titulo].id, titulo=nombre, rubro=rubro,
                descripcion=descripcion, zona_cobertura=zona,
                precio_estimado=Decimal(precio) if precio else None,
            )
            db.session.add(servicio)
            servicios[nombre] = servicio
    db.session.flush()

    for alias, nombre, descripcion, zona, estado, precio, mensaje in SOLICITUDES:
        respondida = estado != EstadosSolicitud.PENDIENTE
        db.session.add(ServiceRequest(
            service_id=servicios[nombre].id,
            cliente_id=usuarios[alias].id,
            descripcion=descripcion,
            zona=zona,
            estado=estado,
            respuesta_precio=Decimal(precio) if precio else None,
            respuesta_mensaje=mensaje,
            created_at=ahora - timedelta(days=3),
            responded_at=ahora - timedelta(days=2) if respondida else None,
        ))

    for titulo, nombre, dias, hora, descripcion in EVENTOS:
        db.session.add(Event(
            post_id=posts[titulo].id, titulo=nombre, descripcion=descripcion,
            fecha=hoy + timedelta(days=dias), hora=hora,
        ))

    for alias, horarios in HORARIOS.items():
        for dia, abre, cierra in horarios:
            db.session.add(Horario(
                user_id=usuarios[alias].id, dia_semana=dia,
                abre=abre, cierra=cierra, cerrado=abre is None,
            ))

    for indice, (alias, titulo, rating, comentario, respuesta) in enumerate(RESENIAS):
        db.session.add(Review(
            post_id=posts[titulo].id, user_id=usuarios[alias].id,
            rating=rating, comment=comentario,
            created=ahora - timedelta(days=30 - indice * 3),
            reply=respuesta,
            replied_at=ahora - timedelta(days=28 - indice * 3) if respuesta else None,
            # Una editada, para ver la marca "(editado)" en el detalle.
            updated_at=ahora - timedelta(days=5) if indice == 1 else None,
        ))

    for alias, titulos in FAVORITOS.items():
        for titulo in titulos:
            db.session.add(Favorite(
                user_id=usuarios[alias].id, post_id=posts[titulo].id
            ))

    for alias, seguidos in SEGUIMIENTOS.items():
        for seguido in seguidos:
            db.session.add(Follow(
                follower_id=usuarios[alias].id, followed_id=usuarios[seguido].id
            ))

    total_mensajes = 0
    for alias, titulo, dialogo, sin_leer in CONVERSACIONES:
        post = posts[titulo]
        cliente = usuarios[alias]
        cuantos = len(dialogo)
        for indice, (quien, texto) in enumerate(dialogo):
            # Los ultimos `sin_leer` quedan sin read_at, para que se vea el
            # contador de mensajes nuevos del navbar.
            leido = indice < cuantos - sin_leer
            db.session.add(Message(
                post_id=post.id,
                client_id=cliente.id,
                sender_id=cliente.id if quien == "cliente" else post.author,
                body=texto,
                created=ahora - timedelta(hours=(cuantos - indice) * 5),
                read_at=ahora - timedelta(hours=1) if leido else None,
            ))
            total_mensajes += 1

    db.session.commit()

    return {
        "usuarios": len(usuarios),
        "emprendimientos": len(posts),
        "productos": total_productos,
        "servicios": len(servicios),
        "solicitudes": len(SOLICITUDES),
        "eventos": len(EVENTOS),
        "reseñas": len(RESENIAS),
        "mensajes": total_mensajes,
        "favoritos": sum(len(v) for v in FAVORITOS.values()),
        "seguimientos": sum(len(v) for v in SEGUIMIENTOS.values()),
        "horarios": sum(len(v) for v in HORARIOS.values()),
    }


HOSTS_LOCALES = {"", "localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _confirmar_si_no_es_local(app):
    """Freno si la base no esta en esta maquina. Devuelve si seguir o no.

    El script borra filas y sube archivos: contra la base de desarrollo eso es
    lo que uno quiere, contra cualquier otra es un accidente. Y es un
    accidente facil, porque el destino sale del entorno (DATABASE_URL o el
    .env) y no de un argumento que uno escriba y vea.

    Con --forzar-host no pregunta: es para poder usarlo en un contenedor o en
    un CI, donde no hay nadie del otro lado para contestar.
    """
    host = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).host or ""
    if host.lower() in HOSTS_LOCALES:
        return True

    if "--forzar-host" in sys.argv:
        print(f"Base remota ({host}), pero se paso --forzar-host. Sigo.")
        return True

    print(
        f"\n  La base NO esta en esta maquina: {host}\n"
        "  Este script borra filas y escribe archivos. Si esa base es de\n"
        "  produccion o la comparte alguien mas, no la corras.\n"
    )
    try:
        respuesta = input(f"  Escribí el nombre del host ({host}) para seguir: ")
    except (EOFError, KeyboardInterrupt):
        # Sin nadie del otro lado que conteste, la respuesta segura es que no.
        # Se captura en vez de mirar sys.stdin.isatty() porque isatty() miente
        # segun como se haya invocado el script: dice que hay terminal y el
        # input() explota igual con EOFError.
        print("\n  Sin respuesta. Cortado, no se tocó nada.")
        print("  Si estás seguro, repetí el comando con --forzar-host.")
        return False

    if respuesta.strip() != host:
        print("  No coincide. Cortado, no se tocó nada.")
        return False
    return True


def main():
    reset = "--reset" in sys.argv
    solo_borrar = "--borrar" in sys.argv

    app = create_app("development")
    with app.app_context():
        destino = app.config["SQLALCHEMY_DATABASE_URI"].rsplit("@", 1)[-1]
        print(f"Base: {destino}")

        if not _confirmar_si_no_es_local(app):
            return

        if reset or solo_borrar:
            borrar(app)
        if solo_borrar:
            return

        if _usuarios_de_seed():
            print(
                "Ya hay datos de seed cargados. Corré con --reset para "
                "rehacerlos, o con --borrar para sacarlos."
            )
            return

        resumen = cargar(app)

    print("\nCargado:")
    for que, cuantos in resumen.items():
        print(f"  {cuantos:>3} {que}")
    print(f"\nTodos los usuarios entran con la contraseña: {PASSWORD}")
    print("  emprendedores: " + ", ".join(EMPRENDEDORES))
    print("  clientes:      " + ", ".join(CLIENTES))


if __name__ == "__main__":
    main()
