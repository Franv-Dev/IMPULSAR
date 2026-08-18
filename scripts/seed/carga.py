"""Escribe en la base todo lo que describe datos.py."""

import os
import random
from datetime import date, timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from db import db, utcnow
from models.event import Event
from models.message import Message
from models.product import Product
from models.user import Roles, User
from app.blog.modelo_favorito import Favorite
from app.blog.modelo_imagen import PostImage
from app.blog.modelo_post import Post
from app.blog.modelo_resenia import Review
from app.perfil.modelo_follow import Follow
from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest

from scripts.seed.datos import (
    CENTRO,
    CLIENTES,
    CONVERSACIONES,
    EMAIL_SEED,
    EMPRENDEDORES,
    EMPRENDIMIENTOS,
    EVENTOS,
    FAVORITOS,
    HORARIOS,
    PASSWORD,
    PRODUCTOS,
    RESENIAS,
    SEGUIMIENTOS,
    SERVICIOS,
    SOLICITUDES,
)
from scripts.seed.imagenes import (
    _carpeta_uploads,
    _generar_imagen,
    _iniciales,
    _nombre_de_imagen,
)


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
