"""Catalogo de productos de los emprendimientos.

El ABM vive aca y no en views/blog.py por lo mismo que el de eventos: es su
propia entidad, con su propio formulario y su propio panel, y meterlo adentro
de blog.py solo haria mas grande un archivo que ya es el mas grande del
proyecto.

Un producto pertenece a un emprendimiento (Post), no a un usuario, asi que el
permiso siempre se resuelve mirando el dueño de ese emprendimiento. El chequeo
va en la vista y no solo en el template: esconder un boton no es un permiso,
cualquiera puede mandar el POST a mano.
"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy.orm import joinedload

from db import db
from models.post import Post
from models.product import MAX_PRODUCTOS_POR_POST, Product
from services.precios import parsear_precio, texto_para_formulario
from services.uploads import borrar_de_disco, carpeta_uploads, save_post_image
from views.auth import login_required

products = Blueprint("products", __name__, url_prefix="/productos")


def _upload_dir():
    return carpeta_uploads()


def _producto_propio(id):
    """El producto con ese id si es de un emprendimiento del usuario actual.

    Devuelve (producto, None) si puede tocarlo, o (None, respuesta) con el
    redirect ya armado si no. Mismo criterio que eventos._evento_propio: flash
    y vuelta al panel, no un 403 crudo.
    """
    producto = Product.query.get_or_404(id)
    if producto.post.author != g.user.id:
        flash("No tenés permiso para modificar este producto.")
        return None, redirect(url_for("products.index"))
    return producto, None


def _mis_emprendimientos():
    return Post.query.filter_by(author=g.user.id).order_by(Post.title).all()


def _leer_formulario():
    """Los campos del producto tal como los mando el usuario, ya parseados.

    La validacion es a mano (con flash y una variable `error`) porque asi
    valida todo el proyecto: Flask-WTF esta instalado pero solo se usa para el
    CSRF.
    """
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    precio_texto = (request.form.get("precio") or "").strip()
    # Un checkbox que no se marca directamente no viaja en el POST.
    disponible = request.form.get("disponible") is not None

    precio, error_precio = parsear_precio(precio_texto)

    error = None
    if not nombre:
        error = "Se requiere un nombre para el producto."
    elif error_precio:
        error = error_precio

    # Se devuelve el texto crudo del precio y no el Decimal: si estaba mal
    # escrito, el formulario tiene que volver con lo que puso el usuario.
    datos = {
        "nombre": nombre, "descripcion": descripcion,
        "precio": precio_texto, "disponible": disponible,
    }
    return datos, nombre, descripcion, precio, disponible, error


@products.route("/")
@login_required
def index():
    """El panel: todos los productos de los emprendimientos propios.

    joinedload trae el emprendimiento en la misma consulta (y con el su autor,
    que ya es lazy="joined"), para no disparar un SELECT por producto al
    mostrar de cual es: es el mismo problema N+1 que la cartelera de eventos.
    """
    productos = (
        Product.query
        .join(Post, Post.id == Product.post_id)
        .options(joinedload(Product.post))
        .filter(Post.author == g.user.id)
        .order_by(Post.title, Product.nombre)
        .all()
    )
    return render_template(
        "products/index.html",
        productos=productos,
        posts=_mis_emprendimientos(),
        maximo=MAX_PRODUCTOS_POR_POST,
    )


@products.route("/nuevo", methods=("GET", "POST"))
@login_required
def nuevo():
    """Cargar un producto en uno de los emprendimientos propios."""
    posts = _mis_emprendimientos()
    if not posts:
        flash("Primero registrá un emprendimiento para poder cargar productos.")
        return redirect(url_for("blog.my_posts"))

    if request.method == "POST":
        datos, nombre, descripcion, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        # El emprendimiento no se toma del formulario a ciegas: sin este
        # chequeo cualquiera podria colgar un producto del emprendimiento de
        # otro mandando un post_id ajeno.
        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        if error is None and _cuantos_tiene(post_id) >= MAX_PRODUCTOS_POR_POST:
            error = (
                f"Ese emprendimiento ya tiene {MAX_PRODUCTOS_POR_POST} productos, "
                "que es el máximo. Borrá alguno para cargar uno nuevo."
            )

        foto = None
        if error is None:
            # La foto se guarda al final: si algo de arriba fallaba, no tiene
            # sentido escribir un archivo que despues nadie va a referenciar.
            foto, error = save_post_image(request.files.get("foto"), _upload_dir())

        if error:
            flash(error)
            return render_template(
                "products/form.html", posts=posts, datos=datos, producto=None
            )

        db.session.add(Product(
            post_id=post_id, nombre=nombre, descripcion=descripcion or None,
            precio=precio, foto=foto, disponible=disponible,
        ))
        db.session.commit()
        flash("Producto agregado correctamente.")
        return redirect(url_for("products.index"))

    datos = {
        "nombre": "", "descripcion": "", "precio": "",
        "disponible": True, "post_id": None,
    }
    return render_template("products/form.html", posts=posts, datos=datos, producto=None)


@products.route("/<int:id>/editar", methods=("GET", "POST"))
@login_required
def editar(id):
    """Editar un producto propio."""
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    posts = _mis_emprendimientos()

    if request.method == "POST":
        datos, nombre, descripcion, precio, disponible, error = _leer_formulario()
        post_id = request.form.get("post_id", type=int)
        datos["post_id"] = post_id

        if error is None and post_id not in {post.id for post in posts}:
            error = "Elegí uno de tus emprendimientos."

        # El tope solo aplica si el producto se esta MUDANDO a otro
        # emprendimiento: si se queda donde estaba, ya esta contado.
        if (
            error is None
            and post_id != producto.post_id
            and _cuantos_tiene(post_id) >= MAX_PRODUCTOS_POR_POST
        ):
            error = (
                f"Ese emprendimiento ya tiene {MAX_PRODUCTOS_POR_POST} productos, "
                "que es el máximo."
            )

        foto_nueva = None
        if error is None:
            foto_nueva, error = save_post_image(request.files.get("foto"), _upload_dir())

        if error:
            # Si la foto nueva llego a escribirse pero algo posterior fallo,
            # se borra: si no, queda en disco sin ninguna fila que la use.
            borrar_de_disco(_upload_dir(), [foto_nueva])
            flash(error)
            return render_template(
                "products/form.html", posts=posts, datos=datos, producto=producto
            )

        foto_vieja = producto.foto
        producto.post_id = post_id
        producto.nombre = nombre
        producto.descripcion = descripcion or None
        producto.precio = precio
        producto.disponible = disponible
        if foto_nueva:
            producto.foto = foto_nueva
        db.session.commit()

        # Recien despues del commit: si la base fallaba, la fila seguiria
        # apuntando a la foto vieja y borrarla antes la dejaria rota.
        if foto_nueva:
            borrar_de_disco(_upload_dir(), [foto_vieja])

        flash("Producto actualizado correctamente.")
        return redirect(url_for("products.index"))

    datos = {
        "nombre": producto.nombre,
        "descripcion": producto.descripcion or "",
        "precio": texto_para_formulario(producto.precio),
        "disponible": producto.disponible,
        "post_id": producto.post_id,
    }
    return render_template(
        "products/form.html", posts=posts, datos=datos, producto=producto
    )


@products.route("/<int:id>/eliminar", methods=("POST",))
@login_required
def eliminar(id):
    """Eliminar un producto propio.

    Solo POST, con la misma razon que blog.delete: un GET no debe tener
    efectos secundarios (lo puede disparar un prefetch del navegador o un
    crawler).
    """
    producto, rechazo = _producto_propio(id)
    if rechazo:
        return rechazo

    foto = producto.foto
    db.session.delete(producto)
    db.session.commit()

    # Despues del commit y no antes: si el borrado en la base falla, el
    # producto sigue existiendo y tiene que seguir teniendo su foto.
    borrar_de_disco(_upload_dir(), [foto])

    flash("Producto eliminado correctamente.")
    return redirect(url_for("products.index"))


def _cuantos_tiene(post_id):
    """Cuantos productos tiene ya ese emprendimiento.

    Un COUNT y no len(post.productos): trae un numero en vez de todas las
    filas solo para contarlas.
    """
    return Product.query.filter_by(post_id=post_id).count()
