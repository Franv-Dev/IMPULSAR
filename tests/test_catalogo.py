"""El catalogo publico de productos: la grilla, el detalle y los guardados.

Aparte de test_products.py, que prueba el ABM y el panel del dueño: eso es lo
que ya existia, y esto es lo que agrego la tanda de disenio-productos/. Lo que
comparten es la fabrica de productos, que se repite aca a proposito -- moverla
a conftest para dos archivos seria dejarla lejos de los dos.
"""

import re
from datetime import time
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.perfil.modelo_horario import Horario
from models.product import Product
from models.product_favorite import ProductFavorite
from models.producto_variante import (
    ProductoVariante, ProductoVarianteOpcion, TiposDeOpcion,
)
from services.horarios import ahora_en_argentina


@pytest.fixture
def crear_producto(db):
    def _crear(post_id, nombre="Pan de campo", precio="1500.00",
               descripcion=None, foto=None, disponible=True):
        producto = Product(
            post_id=post_id, nombre=nombre, descripcion=descripcion,
            precio=Decimal(precio), foto=foto, disponible=disponible,
        )
        db.session.add(producto)
        db.session.commit()
        return producto

    return _crear


@pytest.fixture
def abrir_ahora(db):
    """Deja al usuario atendiendo en este momento, para el filtro "abierto ahora".

    Escribe el horario de HOY con un rango que contiene la hora argentina
    actual, que es la referencia que usa el filtro (no la del servidor ni la
    del visitante).
    """

    def _abrir(user_id):
        ahora = ahora_en_argentina()
        db.session.add(Horario(
            user_id=user_id, dia_semana=ahora.weekday(), cerrado=False,
            abre=time(0, 0), cierra=time(23, 59),
        ))
        db.session.commit()

    return _abrir


def _html(respuesta):
    return respuesta.get_data(as_text=True)


# --- las URL

def test_el_catalogo_es_publico_y_el_panel_no(client, crear_usuario, crear_post,
                                              crear_producto):
    """La URL corta es la publica; el panel del dueño se corrio a /mios."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Dulce de leche")

    assert client.get("/productos/").status_code == 200
    assert client.get("/productos/mios").status_code == 302


def test_el_detalle_es_publico(client, crear_usuario, crear_post, crear_producto):
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, nombre="Dulce de leche")

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Dulce de leche" in html


def test_un_producto_que_no_existe_es_404(client):
    assert client.get("/productos/9999").status_code == 404


# --- la grilla

def test_muestra_productos_de_todos_los_emprendimientos(
    client, crear_usuario, crear_post, crear_producto
):
    """Es lo que no existia: hasta ahora habia que saber quien lo vende."""
    una = crear_usuario(username="una")
    otra = crear_usuario(username="otra")
    crear_producto(crear_post(una.id, title="Panadería").id, nombre="Pan de masa madre")
    crear_producto(crear_post(otra.id, title="Cerámica").id, nombre="Tarro esmaltado")

    html = _html(client.get("/productos/"))

    assert "Pan de masa madre" in html
    assert "Tarro esmaltado" in html


def test_la_tarjeta_nombra_al_emprendimiento_que_vende(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id, title="Conservas del Challao").id)

    html = _html(client.get("/productos/"))

    assert "Conservas del Challao" in html


def test_cuenta_productos_y_emprendimientos(
    client, crear_usuario, crear_post, crear_producto
):
    """El encabezado dice de cuantos negocios distintos salen los resultados."""
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Uno")
    crear_producto(post.id, nombre="Dos")

    html = _html(client.get("/productos/"))

    assert "2 productos" in html
    assert "1 emprendimiento" in html


# --- los filtros

def test_filtra_por_texto_del_producto(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Dulce de leche repostero")
    crear_producto(post.id, nombre="Escabeche de berenjenas")

    html = _html(client.get("/productos/?q=dulce"))

    assert "Dulce de leche repostero" in html
    assert "Escabeche" not in html


def test_filtra_por_descripcion_del_producto(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Frasco chico", descripcion="Cocido a leña en cobre")
    crear_producto(post.id, nombre="Frasco grande", descripcion="Sin conservantes")

    html = _html(client.get("/productos/?q=cobre"))

    assert "Frasco chico" in html
    assert "Frasco grande" not in html


def test_filtra_por_rubro_del_emprendimiento(
    client, crear_usuario, crear_post, crear_producto
):
    """Product no tiene categoria propia: el rubro es el del negocio."""
    dueno = crear_usuario(username="dueno")
    crear_producto(
        crear_post(dueno.id, title="Panadería", category="alimentos").id,
        nombre="Pan de masa madre",
    )
    crear_producto(
        crear_post(dueno.id, title="Taller", category="hogar").id,
        nombre="Cuchara de algarrobo",
    )

    html = _html(client.get("/productos/?category=alimentos"))

    assert "Pan de masa madre" in html
    assert "Cuchara de algarrobo" not in html


def test_un_rubro_que_no_existe_no_filtra_nada(
    client, crear_usuario, crear_post, crear_producto
):
    """Se repinta el control con lo que vino, pero la consulta lo ignora."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Pan de masa madre")

    html = _html(client.get("/productos/?category=inventado"))

    assert "Pan de masa madre" in html


def test_el_rango_de_precio_acota_por_los_dos_lados(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Barato", precio="1000.00")
    crear_producto(post.id, nombre="Justo", precio="5000.00")
    crear_producto(post.id, nombre="Caro", precio="9000.00")

    html = _html(client.get("/productos/?precio_min=2000&precio_max=8000"))

    assert "Justo" in html
    assert "Barato" not in html
    assert "Caro" not in html


def test_el_precio_del_filtro_se_lee_como_lo_escribe_la_gente(
    client, crear_usuario, crear_post, crear_producto
):
    """Mismo parsear_precio que el formulario de carga: coma y puntos de miles."""
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Barato", precio="1000.00")
    crear_producto(post.id, nombre="Caro", precio="9000.00")

    html = _html(client.get("/productos/?precio_min=5.000,00"))

    assert "Caro" in html
    assert "Barato" not in html


def test_un_precio_mal_escrito_no_acota_ni_rompe(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Pan de masa madre")

    respuesta = client.get("/productos/?precio_min=gratis")

    assert respuesta.status_code == 200
    assert "Pan de masa madre" in _html(respuesta)


def test_disponibles_viene_encendido(
    client, crear_usuario, crear_post, crear_producto
):
    """Un catalogo que arranca mostrando lo que no hay hace perder tiempo."""
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Hay stock")
    crear_producto(post.id, nombre="Sin stock", disponible=False)

    html = _html(client.get("/productos/"))

    assert "Hay stock" in html
    assert "Sin stock" not in html


def test_se_puede_apagar_disponibles(
    client, crear_usuario, crear_post, crear_producto
):
    """El default es el filtro puesto, asi que lo que viaja en la URL es el apagado."""
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Agotado por ahora", disponible=False)

    html = _html(client.get("/productos/?disponibles=0"))

    assert "Agotado por ahora" in html


def test_abierto_ahora_deja_solo_a_los_que_atienden(
    client, crear_usuario, crear_post, crear_producto, abrir_ahora
):
    """Los horarios son del emprendedor, no del emprendimiento."""
    abierta = crear_usuario(username="abierta")
    cerrada = crear_usuario(username="cerrada")
    abrir_ahora(abierta.id)
    crear_producto(crear_post(abierta.id, title="Abierta").id, nombre="Pan de hoy")
    crear_producto(crear_post(cerrada.id, title="Cerrada").id, nombre="Pan de ayer")

    html = _html(client.get("/productos/?abierto_ahora=1"))

    assert "Pan de hoy" in html
    assert "Pan de ayer" not in html


def test_sin_coordenadas_no_se_dibuja_el_radio(
    client, crear_usuario, crear_post, crear_producto
):
    """Un filtro que la consulta ignora no se ofrece."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id)

    html = _html(client.get("/productos/"))

    assert 'id="filtro-radio"' not in html


def test_el_radio_acota_por_distancia(
    client, crear_usuario, crear_post, crear_producto
):
    """Las coordenadas son del emprendimiento: el producto no tiene propias."""
    dueno = crear_usuario(username="dueno")
    crear_producto(
        crear_post(dueno.id, title="Cerca", latitude=-32.89, longitude=-68.84).id,
        nombre="Pan de al lado",
    )
    crear_producto(
        # A mas de 100 km de la primera.
        crear_post(dueno.id, title="Lejos", latitude=-33.90, longitude=-68.84).id,
        nombre="Pan de allá",
    )

    html = _html(client.get("/productos/?lat=-32.89&lon=-68.84&radio=10"))

    assert "Pan de al lado" in html
    assert "Pan de allá" not in html


def test_un_radio_que_no_esta_en_la_lista_se_ignora(
    client, crear_usuario, crear_post, crear_producto
):
    """El radio va al WHERE como trigonometria: no se acepta cualquier numero."""
    dueno = crear_usuario(username="dueno")
    crear_producto(
        crear_post(dueno.id, latitude=-33.90, longitude=-68.84).id,
        nombre="Pan de allá",
    )

    html = _html(client.get("/productos/?lat=-32.89&lon=-68.84&radio=9999"))

    assert "Pan de allá" in html


def test_el_conteo_de_emprendimientos_respeta_los_filtros(
    client, crear_usuario, crear_post, crear_producto
):
    """Si contara otra cosa que la grilla, el numero mentiria."""
    dueno = crear_usuario(username="dueno")
    crear_producto(
        crear_post(dueno.id, title="Panadería", category="alimentos").id,
        nombre="Pan de masa madre",
    )
    crear_producto(
        crear_post(dueno.id, title="Taller", category="hogar").id,
        nombre="Cuchara de algarrobo",
    )

    html = _html(client.get("/productos/?category=alimentos"))

    assert "1 producto " in html
    assert "de 1 emprendimiento" in html


# --- el orden

def test_ordena_por_precio_de_menor_a_mayor(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Caro", precio="9000.00")
    crear_producto(post.id, nombre="Barato", precio="1000.00")

    html = _html(client.get("/productos/?orden=precio"))

    assert html.index("Barato") < html.index("Caro")


def test_ordena_por_precio_de_mayor_a_menor(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    crear_producto(post.id, nombre="Barato", precio="1000.00")
    crear_producto(post.id, nombre="Caro", precio="9000.00")

    html = _html(client.get("/productos/?orden=precio_desc"))

    assert html.index("Caro") < html.index("Barato")


def test_un_orden_que_no_existe_cae_al_default(
    client, crear_usuario, crear_post, crear_producto
):
    """No es un filtro sino una preferencia: no hay nada que avisarle a nadie."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Pan de masa madre")

    respuesta = client.get("/productos/?orden=inventado")

    assert respuesta.status_code == 200
    assert "Pan de masa madre" in _html(respuesta)


def test_cercania_sin_coordenadas_no_rompe(
    client, crear_usuario, crear_post, crear_producto
):
    """Se puede pedir en la URL sin haber dicho desde donde: cae a "mas nuevos"."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, nombre="Pan de masa madre")

    respuesta = client.get("/productos/?orden=cercania")

    assert respuesta.status_code == 200
    assert "Pan de masa madre" in _html(respuesta)


# --- el detalle

def test_el_detalle_dice_quien_vende(
    client, crear_usuario, crear_post, crear_producto
):
    """Contesta dos preguntas: que es, y quien lo vende."""
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(
        crear_post(dueno.id, title="Conservas del Challao").id,
        nombre="Dulce de leche", descripcion="Cocido a leña en tacho de cobre",
    )

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Conservas del Challao" in html
    assert "Cocido a leña en tacho de cobre" in html


def test_el_detalle_no_ofrece_comprar(
    client, crear_usuario, crear_post, crear_producto
):
    """No es una tienda: sin stock, sin carrito y sin pago (ver el modelo)."""
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id)

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Comprar" not in html
    assert "carrito" not in html.lower()


def test_consultar_lleva_al_chat_con_el_producto(
    client, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id)
    login(cliente.id)

    html = _html(client.get(f"/productos/{producto.id}"))

    assert f"/mensajes/{post.id}/{cliente.id}?producto={producto.id}" in html


def test_el_dueno_ve_editar_y_no_consultar(
    client, crear_usuario, crear_post, crear_producto, login
):
    """Nadie se escribe a si mismo."""
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id)
    login(dueno.id)

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Editar este producto" in html
    assert "Consultar por este producto" not in html


def test_sin_sesion_el_detalle_invita_a_entrar(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id)

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Entrá para consultar" in html


def test_mas_de_este_emprendimiento_no_se_repite_a_si_mismo(
    client, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id, nombre="Dulce de leche")
    crear_producto(post.id, nombre="Mermelada de damasco")

    html = _html(client.get(f"/productos/{producto.id}"))

    assert "Mermelada de damasco" in html
    # El bloque de abajo no se enlaza a sí mismo: sería un link a la pantalla
    # en la que ya estás.
    assert f'href="/productos/{producto.id}"' not in html


# --- el chat con el nombre del producto ya escrito

def test_el_chat_precarga_el_nombre_del_producto(
    client, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    post = crear_post(dueno.id)
    producto = crear_producto(post.id, nombre="Dulce de leche repostero")
    login(cliente.id)

    html = _html(client.get(f"/mensajes/{post.id}/{cliente.id}?producto={producto.id}"))

    assert "Dulce de leche repostero" in html


def test_el_chat_no_precarga_un_producto_de_otro(
    client, crear_usuario, crear_post, crear_producto, login
):
    """Sin el chequeo, un id cualquiera pondria palabras en boca del que pregunta."""
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    post = crear_post(dueno.id, title="Panadería")
    ajeno = crear_producto(
        crear_post(dueno.id, title="Taller").id, nombre="Cuchara de algarrobo"
    )
    login(cliente.id)

    html = _html(client.get(f"/mensajes/{post.id}/{cliente.id}?producto={ajeno.id}"))

    assert "Cuchara de algarrobo" not in html


def test_el_chat_sin_producto_arranca_vacio(
    client, crear_usuario, crear_post, login
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    post = crear_post(dueno.id)
    login(cliente.id)

    html = _html(client.get(f"/mensajes/{post.id}/{cliente.id}"))

    assert 'id="chat-body"' in html
    assert "quería consultar por" not in html


# --- favoritos de productos

def test_guardar_y_desguardar_un_producto(
    client, crear_usuario, crear_post, crear_producto, login
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    producto = crear_producto(crear_post(dueno.id).id)
    login(cliente.id)

    client.post(f"/productos/{producto.id}/favorito")
    assert ProductFavorite.query.count() == 1

    client.post(f"/productos/{producto.id}/favorito")
    assert ProductFavorite.query.count() == 0


def test_guardar_pide_sesion(client, crear_usuario, crear_post, crear_producto):
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id)

    respuesta = client.post(f"/productos/{producto.id}/favorito")

    assert respuesta.status_code == 302
    assert ProductFavorite.query.count() == 0


def test_no_se_puede_guardar_dos_veces_el_mismo(
    db, crear_usuario, crear_post, crear_producto
):
    """La garantia es el UNIQUE de la tabla, no el SELECT de la vista."""
    from sqlalchemy.exc import IntegrityError

    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    producto = crear_producto(crear_post(dueno.id).id)

    db.session.add(ProductFavorite(user_id=cliente.id, product_id=producto.id))
    db.session.commit()
    db.session.add(ProductFavorite(user_id=cliente.id, product_id=producto.id))

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_borrar_el_producto_se_lleva_sus_favoritos(
    db, crear_usuario, crear_post, crear_producto
):
    """ondelete CASCADE en las dos FK: sin eso, MySQL usa RESTRICT y falla."""
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    producto = crear_producto(crear_post(dueno.id).id)
    db.session.add(ProductFavorite(user_id=cliente.id, product_id=producto.id))
    db.session.commit()

    db.session.delete(producto)
    db.session.commit()

    assert ProductFavorite.query.count() == 0


def test_borrar_el_usuario_se_lleva_sus_favoritos(
    db, crear_usuario, crear_post, crear_producto
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    producto = crear_producto(crear_post(dueno.id).id)
    db.session.add(ProductFavorite(user_id=cliente.id, product_id=producto.id))
    db.session.commit()

    db.session.delete(cliente)
    db.session.commit()

    assert ProductFavorite.query.count() == 0


def test_los_guardados_son_solo_los_propios(
    client, crear_usuario, crear_post, crear_producto, login, db
):
    dueno = crear_usuario(username="dueno")
    cliente = crear_usuario(username="cliente")
    otro = crear_usuario(username="otro")
    post = crear_post(dueno.id)
    mio = crear_producto(post.id, nombre="Lo que guardé")
    ajeno = crear_producto(post.id, nombre="Lo que guardó otro")
    db.session.add_all([
        ProductFavorite(user_id=cliente.id, product_id=mio.id),
        ProductFavorite(user_id=otro.id, product_id=ajeno.id),
    ])
    db.session.commit()
    login(cliente.id)

    html = _html(client.get("/productos/guardados"))

    assert "Lo que guardé" in html
    assert "Lo que guardó otro" not in html


def test_las_dos_solapas_de_favoritos_estan_en_las_dos_pantallas(
    client, crear_usuario, login
):
    """Separadas, entrar a una sería quedarse sin salida hacia la otra."""
    usuario = crear_usuario()
    login(usuario.id)

    for url in ("/blog/favoritos", "/productos/guardados"):
        html = _html(client.get(url))
        assert 'href="/blog/favoritos"' in html, url
        assert 'href="/productos/guardados"' in html, url


# ----------------------------------------- las variantes en la tarjeta

"""Lo que prueba esta seccion, y por que cada caso.

La tarjeta tiene que decir el precio y la disponibilidad REALES del producto
que se vende por combinacion, sin preguntarle a la base una vez por tarjeta.
Son tres cosas distintas y se prueban por separado:

  - la REGRESION primero: el producto sin variantes no cambia en nada.
  - el precio: el minimo entre las ACTIVAS, con "desde" solo si no valen todas
    lo mismo, y sin mirar las apagadas aunque sean mas baratas.
  - el stock: alcanza con que una combinacion activa tenga, y la matriz entera
    apagada es "agotado" y no un error.

Y el ultimo, que es la razon de ser de la tanda: que el costo de la pantalla no
crezca con la cantidad de productos listados.
"""


@pytest.fixture
def con_variantes(db):
    """Le carga al producto sus ejes y las combinaciones que pide el test.

    Cada combinacion es una tupla (talle, stock, precio_override, activo), con
    el precio como texto o None para "hereda el del producto". Se cargan
    tambien las OPCIONES y no solo las filas, porque es lo que hace un producto
    de verdad: la pantalla guarda las listas y de ahi sale la matriz.
    Product.tiene_variantes mira las dos cosas, asi que un test que escribiera
    solo las filas estaria probando un estado que la aplicacion no produce.
    """
    def _con(producto, *combinaciones, con_ejes=True):
        if con_ejes:
            talles = dict.fromkeys(talle for talle, _, _, _ in combinaciones)
            for orden, talle in enumerate(talles):
                db.session.add(ProductoVarianteOpcion(
                    product_id=producto.id, tipo=TiposDeOpcion.TALLE,
                    valor=talle, orden=orden,
                ))
        for talle, stock, precio_override, activo in combinaciones:
            db.session.add(ProductoVariante(
                product_id=producto.id, talle=talle, color="", stock=stock,
                precio_override=(
                    Decimal(precio_override) if precio_override is not None else None
                ),
                activo=activo,
            ))
        db.session.commit()
        return producto

    return _con


def _precio_de_la_tarjeta(html):
    """El texto del precio de la unica tarjeta de la grilla, sin los espacios.

    Se lee el span de la tarjeta y no el HTML entero a proposito: la barra de
    filtros tiene un campo "Precio desde" y un chip "Desde $...", asi que
    buscar "desde" suelto en la pagina da positivo siempre y el test no
    probaria nada.
    """
    encontrado = re.search(
        r'class="producto-tarjeta__precio">(.*?)</span>', html, re.S
    )
    assert encontrado, "la grilla no tiene ninguna tarjeta"
    return " ".join(encontrado.group(1).split())


def _dice_sin_stock(html):
    return "producto-tarjeta__agotado" in html


def test_sin_variantes_la_tarjeta_sigue_diciendo_el_precio_base(
    client, crear_usuario, crear_post, crear_producto
):
    """La regresion de la tanda: el camino viejo no se entera de nada."""
    dueno = crear_usuario(username="dueno")
    crear_producto(crear_post(dueno.id).id, precio="1500.00")

    html = _html(client.get("/productos/"))

    assert _precio_de_la_tarjeta(html) == "$ 1.500,00"
    assert not _dice_sin_stock(html)


def test_con_todas_las_combinaciones_al_mismo_precio_no_dice_desde(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """"desde" con un precio unico suena a letra chica, y no hay letra chica.

    Las tres combinaciones valen lo mismo por caminos distintos -- una hereda
    el precio del producto y las otras dos lo pisan con ese mismo numero --,
    que es justo el caso en el que mirar `precio_override` en vez del precio
    efectivo se equivocaria.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, precio="1500.00")
    con_variantes(
        producto,
        ("S", 3, None, True),
        ("M", 2, "1500.00", True),
        ("L", 1, "1500.00", True),
    )

    assert _precio_de_la_tarjeta(_html(client.get("/productos/"))) == "$ 1.500,00"


def test_con_precios_distintos_dice_desde_el_mas_barato_de_los_activos(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """El minimo es entre las ENCENDIDAS, y la apagada mas barata no cuenta.

    La combinacion de $900 esta apagada: el vendedor dijo que esa no existe, y
    anunciarla seria mandar a la gente a preguntar por algo que no se puede
    pedir.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, precio="1500.00")
    con_variantes(
        producto,
        ("S", 1, "900.00", False),
        ("M", 1, "1200.00", True),
        ("L", 1, "1800.00", True),
    )

    assert _precio_de_la_tarjeta(_html(client.get("/productos/"))) == "desde $ 1.200,00"


def test_el_precio_heredado_entra_en_la_cuenta_del_minimo(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """precio_override en NULL es "vale lo que el producto", no "no tiene precio".

    Si el minimo se calculara sobre la columna sola, la combinacion que hereda
    quedaria afuera y la tarjeta anunciaria $2.000 cuando hay una a $1.500.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, precio="1500.00")
    con_variantes(
        producto,
        ("S", 1, None, True),
        ("M", 1, "2000.00", True),
    )

    assert _precio_de_la_tarjeta(_html(client.get("/productos/"))) == "desde $ 1.500,00"


def test_con_una_combinacion_con_stock_la_tarjeta_no_dice_agotado(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """Alcanza con UNA. La tarjeta no dice cuanto hay: eso es de la ficha."""
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id)
    con_variantes(
        producto,
        ("S", 0, None, True),
        ("M", 4, None, True),
    )

    assert not _dice_sin_stock(_html(client.get("/productos/")))


def test_sin_ninguna_combinacion_con_stock_la_tarjeta_dice_agotado(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """El interruptor del producto dice que si y no queda nada que mandar.

    Es el caso que la tarjeta no sabia leer antes de esta tanda: el producto
    esta `disponible`, asi que se mostraba como si hubiera stock.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, disponible=True)
    con_variantes(
        producto,
        ("S", 0, None, True),
        ("M", 0, None, True),
    )

    assert _dice_sin_stock(_html(client.get("/productos/")))


def test_con_la_matriz_entera_apagada_la_tarjeta_dice_agotado_y_no_revienta(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """Ninguna activa PERO con los ejes cargados: agotado, no precio base.

    Sin la subconsulta de opciones este producto seria indistinguible de uno
    que nunca uso variantes, y la tarjeta lo anunciaria disponible. El precio
    se sigue escribiendo -- un hueco donde va el precio se lee como una pagina
    rota --, pero al lado dice que no hay.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, precio="1500.00")
    con_variantes(
        producto,
        ("S", 5, "900.00", False),
        ("M", 5, "1200.00", False),
    )

    respuesta = client.get("/productos/")
    assert respuesta.status_code == 200
    html = _html(respuesta)
    assert _dice_sin_stock(html)
    assert _precio_de_la_tarjeta(html) == "$ 1.500,00"


def test_sin_ejes_y_todo_apagado_el_producto_vuelve_a_su_precio_base(
    client, crear_usuario, crear_post, crear_producto, con_variantes
):
    """El camino de "apagar las variantes", igual que Product.tiene_variantes.

    Vaciar las dos listas apaga las filas pero no las borra. Ese producto no
    usa variantes: tiene que volver al precio base y al booleano de siempre, y
    no quedar agotado para siempre sin forma de revivirlo desde la pantalla.
    """
    dueno = crear_usuario(username="dueno")
    producto = crear_producto(crear_post(dueno.id).id, precio="1500.00")
    con_variantes(
        producto,
        ("S", 0, "900.00", False),
        ("M", 0, "1200.00", False),
        con_ejes=False,
    )

    html = _html(client.get("/productos/"))
    assert _precio_de_la_tarjeta(html) == "$ 1.500,00"
    assert not _dice_sin_stock(html)


def test_el_catalogo_no_consulta_de_mas_por_cada_producto_con_variantes(
    app, client, db, crear_usuario, crear_post, crear_producto, con_variantes
):
    """La razon de ser de la tanda: el costo no puede depender de la grilla.

    Se compara el numero de consultas de una pagina con 5 productos con
    variantes contra la misma pagina con 20. Con las properties del modelo
    (precio_desde, disponible_efectivo) cada tarjeta sumaria dos SELECT -- las
    variantes y las opciones son relaciones lazy --, asi que el numero creceria
    con la pagina; con las dos subconsultas agregadas tiene que ser EL MISMO.

    Se mide con el identity map vaciado antes de cada corrida: con los objetos
    ya cargados en la sesion del test un lazy load no llega a la base y el
    contador daria un falso negativo.

    La pagina se pide entera (por_pagina al tope) para que las 20 filas caigan
    en la misma, que es lo que hace comparable el numero.
    """
    app.config["PRODUCTOS_POR_PAGINA"] = 50
    dueno = crear_usuario(username="dueno")
    # El id aparte y no `post.id`: despues del expunge_all de la primera
    # medicion el objeto queda desprendido de la sesion, y leerle un atributo
    # es un DetachedInstanceError.
    post_id = crear_post(dueno.id).id

    def sumar_productos(desde, hasta):
        for numero in range(desde, hasta):
            producto = crear_producto(post_id, nombre=f"Remera {numero}")
            con_variantes(
                producto,
                ("S", 2, None, True),
                ("M", 0, "1800.00", True),
                ("L", 1, "2500.00", False),
            )

    def contar_consultas():
        db.session.expunge_all()
        vistas = []

        def escuchar(conn, cursor, statement, params, context, many):
            vistas.append(statement)

        event.listen(db.engine, "before_cursor_execute", escuchar)
        try:
            respuesta = client.get("/productos/")
        finally:
            event.remove(db.engine, "before_cursor_execute", escuchar)
        assert respuesta.status_code == 200
        return len(vistas)

    sumar_productos(0, 5)
    con_cinco = contar_consultas()

    sumar_productos(5, 20)
    con_veinte = contar_consultas()

    assert con_veinte == con_cinco
