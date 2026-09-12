"""Variantes de producto: la matriz, su edicion y lo que ve el que compra.

Lo que se prueba y por que:

  - REGRESION PRIMERO: el producto sin variantes tiene que comportarse
    exactamente como antes de la tanda. Es la condicion de todo lo demas, asi
    que va arriba y no como nota al pie.
  - la matriz: N x M filas, y llamar dos veces no duplica.
  - que generar NO PISE lo editado, que es la regla que hace usable la
    pantalla.
  - la combinacion apagada: ni se ofrece ni se puede consultar aunque tenga
    stock.
  - precio_override: NULL hereda, con valor pisa.
  - el UNIQUE A NIVEL BASE, insertando a mano por el ORM y no por la vista: lo
    que se prueba es que la constraint existe, no que la vista chequea.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from models.product import Product
from models.producto_variante import (
    MAX_STOCK, ProductoVariante, ProductoVarianteOpcion, TiposDeOpcion,
)
from services import variantes as reglas


@pytest.fixture
def vendedor(crear_usuario, crear_post, db):
    """Un emprendedor con su emprendimiento."""
    user = crear_usuario(username="vendedora")
    post = crear_post(user.id, title="Ropa del barrio")
    return user, post


@pytest.fixture
def crear_producto(db):
    def _crear(post_id, nombre="Remera", precio="12000", **kwargs):
        producto = Product(post_id=post_id, nombre=nombre, precio=precio, **kwargs)
        db.session.add(producto)
        db.session.commit()
        return producto

    return _crear


def _guardar_listas(client, producto, talles="", colores=""):
    return client.post(
        f"/productos/{producto.id}/variantes/opciones",
        data={"talles": talles, "colores": colores},
    )


# ------------------------------------------------------- regresion: sin variantes

def test_un_producto_sin_variantes_se_comporta_como_siempre(
    client, login, vendedor, crear_producto
):
    """La condicion de la tanda: el camino viejo no cambia.

    Se mira lo que de verdad usa ese camino -- el precio del producto, el
    booleano `disponible` y el boton de consultar de siempre -- y ademas que no
    aparezca ni un rastro del selector de combinaciones.
    """
    user, post = vendedor
    producto = crear_producto(post.id, nombre="Taza", precio="3000")

    assert producto.tiene_variantes is False
    # None y no cero: "este producto no maneja stock" no es lo mismo que "no
    # queda ninguna".
    assert producto.stock_total is None
    assert producto.disponible_efectivo is True

    login(user.id)
    html = client.get(f"/productos/{producto.id}").get_data(as_text=True)
    assert "producto__variantes" not in html
    assert "3.000" in html


def test_sin_variantes_el_disponible_sigue_mandando(
    client, vendedor, crear_producto, db
):
    user, post = vendedor
    producto = crear_producto(post.id, disponible=False)

    assert producto.disponible_efectivo is False


# ---------------------------------------------------------- generar la matriz

def test_tres_talles_por_dos_colores_son_seis_filas(
    client, login, vendedor, crear_producto
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)

    _guardar_listas(client, producto, talles="S, M, L", colores="Negro, Blanco")

    assert ProductoVariante.query.count() == 6
    assert {(v.talle, v.color) for v in producto.variantes} == {
        (talle, color)
        for talle in ("S", "M", "L")
        for color in ("Negro", "Blanco")
    }
    # Las opciones quedan guardadas en el orden en que las escribio.
    assert reglas.opciones_de(producto, TiposDeOpcion.TALLE) == ["S", "M", "L"]


def test_llamar_dos_veces_con_la_misma_lista_no_duplica(
    client, login, vendedor, crear_producto
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)

    _guardar_listas(client, producto, talles="S, M", colores="Negro")
    _guardar_listas(client, producto, talles="S, M", colores="Negro")

    assert ProductoVariante.query.count() == 2
    assert ProductoVarianteOpcion.query.count() == 3


def test_un_solo_eje_genera_una_fila_por_valor(
    client, login, vendedor, crear_producto
):
    """Vender solo por talle es el caso mas comun y tiene que funcionar."""
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)

    _guardar_listas(client, producto, talles="S, M, L")

    assert ProductoVariante.query.count() == 3
    # El eje que no se usa es cadena VACIA y nunca NULL: es lo que hace que el
    # UNIQUE de la base siga aplicando (ver el docstring del modelo).
    assert all(variante.color == "" for variante in producto.variantes)
    assert all(variante.color is not None for variante in producto.variantes)


def test_sin_ninguna_lista_no_hay_matriz(client, login, vendedor, crear_producto):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)

    _guardar_listas(client, producto)

    assert ProductoVariante.query.count() == 0
    assert producto.tiene_variantes is False


def test_agregar_un_talle_no_pisa_lo_ya_editado(
    client, login, vendedor, crear_producto, db
):
    """La regla que hace usable la pantalla: volver a tocar las listas no borra
    el trabajo de cargar stock y precios."""
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M", colores="Negro")

    editada = producto.variantes[0]
    editada.stock = 7
    editada.precio_override = "15000"
    editada.activo = False
    db.session.commit()

    _guardar_listas(client, producto, talles="S, M, L", colores="Negro")

    assert ProductoVariante.query.count() == 3
    assert editada.stock == 7
    assert str(editada.precio_override) == "15000.00"
    assert editada.activo is False


def test_sacar_un_talle_apaga_sus_filas_pero_no_las_borra(
    client, login, vendedor, crear_producto, db
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M", colores="Negro")
    for variante in producto.variantes:
        variante.stock = 5
    db.session.commit()

    _guardar_listas(client, producto, talles="S", colores="Negro")

    # Las dos filas siguen: la que salio de la lista queda apagada, con su
    # stock intacto, porque puede tener historia.
    assert ProductoVariante.query.count() == 2
    apagadas = [v for v in producto.variantes if not v.activo]
    assert [v.talle for v in apagadas] == ["M"]
    assert apagadas[0].stock == 5
    # Y no suma al total, porque el vendedor dijo que no existe.
    assert producto.stock_total == 5


@pytest.mark.parametrize("texto,esperado", [
    ("S, M, L", ["S", "M", "L"]),
    ("S\nM\nL", ["S", "M", "L"]),
    ("  S ,M ,  L  ", ["S", "M", "L"]),
    ("S, M, , L,", ["S", "M", "L"]),
    ("S, M, S", ["S", "M"]),
    ("", []),
    (None, []),
])
def test_la_lista_se_limpia_sin_reordenar(texto, esperado):
    """El orden es el que eligio el vendedor: alfabetico seria "L, M, S"."""
    assert reglas.normalizar_lista(texto) == esperado


# ------------------------------------------------------------ editar una fila

def test_editar_stock_precio_y_estado(client, login, vendedor, crear_producto):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S", colores="Negro")
    variante = producto.variantes[0]

    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "12", "precio": "9.500,50", "activo": "on"},
    )

    assert variante.stock == 12
    # La coma decimal se lee como coma decimal (services/precios.py).
    assert str(variante.precio_override) == "9500.50"
    assert variante.activo is True


def test_el_stock_negativo_se_rechaza_en_el_servidor(
    client, login, vendedor, crear_producto
):
    """El min="0" del input se saltea mandando el POST a mano."""
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]
    variante.stock = 4

    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "-3", "activo": "on"},
    )

    assert variante.stock == 4


def test_no_se_puede_editar_la_variante_de_otro_producto(
    client, login, vendedor, crear_producto
):
    """Los dos ids llegan por la URL y nada obliga a que vayan juntos."""
    user, post = vendedor
    uno = crear_producto(post.id, nombre="Remera")
    otro = crear_producto(post.id, nombre="Buzo")
    login(user.id)
    _guardar_listas(client, uno, talles="S")
    variante = uno.variantes[0]

    respuesta = client.post(
        f"/productos/{otro.id}/variantes/{variante.id}",
        data={"stock": "99", "activo": "on"},
    )

    assert respuesta.status_code == 404
    assert variante.stock == 0


def test_un_ajeno_no_puede_tocar_las_variantes(
    client, login, vendedor, crear_producto, crear_usuario
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]

    intruso = crear_usuario(username="intruso")
    login(intruso.id)
    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "99", "activo": "on"},
    )
    client.post(
        f"/productos/{producto.id}/variantes/opciones",
        data={"talles": "XXL", "colores": ""},
    )

    assert variante.stock == 0
    assert ProductoVariante.query.count() == 1


# ------------------------------------------------------------------- precio

def test_precio_override_en_null_hereda_el_del_producto(
    client, login, vendedor, crear_producto, db
):
    user, post = vendedor
    producto = crear_producto(post.id, precio="12000")
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]

    assert variante.precio_override is None
    assert variante.hereda_precio is True
    assert str(variante.precio_efectivo) == "12000.00"

    # Y hereda DE VERDAD: subir el precio del producto mueve el de la variante,
    # que es lo que no pasaria si se hubiera copiado al generar la fila.
    producto.precio = "15000"
    db.session.commit()
    assert str(variante.precio_efectivo) == "15000.00"


def test_precio_override_con_valor_pisa_el_del_producto(
    client, login, vendedor, crear_producto, db
):
    user, post = vendedor
    producto = crear_producto(post.id, precio="12000")
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]

    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "3", "precio": "20000", "activo": "on"},
    )
    assert str(variante.precio_efectivo) == "20000.00"

    producto.precio = "15000"
    db.session.commit()
    assert str(variante.precio_efectivo) == "20000.00"


def test_vaciar_el_precio_vuelve_a_heredar(
    client, login, vendedor, crear_producto
):
    """Es la unica forma de deshacer un precio propio, asi que tiene que andar."""
    user, post = vendedor
    producto = crear_producto(post.id, precio="12000")
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]

    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "3", "precio": "20000", "activo": "on"},
    )
    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "3", "precio": "", "activo": "on"},
    )

    assert variante.precio_override is None
    assert str(variante.precio_efectivo) == "12000.00"


# ------------------------------------------------- la combinacion desactivada

def test_una_combinacion_apagada_no_se_ofrece_ni_se_consulta(
    client, login, vendedor, crear_producto, crear_usuario, db
):
    """AUNQUE TENGA STOCK, que es todo el punto de `activo`."""
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M")
    apagada, viva = producto.variantes
    apagada.stock = 10
    apagada.activo = False
    viva.stock = 4
    db.session.commit()

    assert apagada.comprable is False
    assert producto.variantes_comprables == [viva]
    # No suma al total aunque tenga diez unidades cargadas.
    assert producto.stock_total == 4

    cliente = crear_usuario(username="clienta")
    login(cliente.id)
    html = client.get(f"/productos/{producto.id}").get_data(as_text=True)
    # Se miran los <option> y no un value suelto: el formulario tiene tambien
    # un input oculto con el id del PRODUCTO, y buscar 'value="1"' a secas lo
    # engancha y da un falso positivo (paso escribiendo este test).
    assert f'<option value="{viva.id}">' in html
    assert f'<option value="{apagada.id}">' not in html

    # Y pedirla a mano por la URL no precarga la combinacion en el chat.
    chat = client.get(
        f"/mensajes/{post.id}/{cliente.id}"
        f"?producto={producto.id}&variante={apagada.id}"
    ).get_data(as_text=True)
    assert "(S)" not in chat
    # El producto si, porque el que pregunta igual quiere preguntar.
    assert producto.nombre in chat


def test_una_combinacion_sin_stock_tampoco_se_puede_pedir(
    client, login, vendedor, crear_producto, crear_usuario, db
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]
    variante.stock = 0
    db.session.commit()

    assert variante.comprable is False
    assert producto.disponible_efectivo is False

    cliente = crear_usuario(username="clienta")
    login(cliente.id)
    html = client.get(f"/productos/{producto.id}").get_data(as_text=True)
    assert "No queda ninguna combinación disponible" in html


def test_la_combinacion_comprable_llega_al_chat(
    client, login, vendedor, crear_producto, crear_usuario, db
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="M", colores="Negro")
    variante = producto.variantes[0]
    variante.stock = 3
    db.session.commit()

    cliente = crear_usuario(username="clienta")
    login(cliente.id)
    chat = client.get(
        f"/mensajes/{post.id}/{cliente.id}"
        f"?producto={producto.id}&variante={variante.id}"
    ).get_data(as_text=True)

    assert "M / Negro" in chat


def test_la_variante_de_otro_producto_no_entra_en_el_borrador(
    client, login, vendedor, crear_producto, crear_usuario, db
):
    """Si no, un id cualquiera pondria el talle de otro producto en la boca del
    que pregunta."""
    user, post = vendedor
    uno = crear_producto(post.id, nombre="Remera")
    otro = crear_producto(post.id, nombre="Buzo")
    login(user.id)
    _guardar_listas(client, otro, talles="XXL")
    ajena = otro.variantes[0]
    ajena.stock = 5
    db.session.commit()

    cliente = crear_usuario(username="clienta")
    login(cliente.id)
    chat = client.get(
        f"/mensajes/{post.id}/{cliente.id}?producto={uno.id}&variante={ajena.id}"
    ).get_data(as_text=True)

    assert "XXL" not in chat
    assert "Remera" in chat


# -------------------------------------------------- las constraints de la base

def test_la_base_rechaza_la_combinacion_duplicada(
    db, vendedor, crear_producto
):
    """A NIVEL BASE y no a nivel aplicacion: se inserta a mano, sin pasar por
    ninguna vista, para probar que la constraint existe y no que la vista
    chequea. Es lo que cierra la ventana entre el SELECT y el INSERT.
    """
    user, post = vendedor
    producto = crear_producto(post.id)

    db.session.add(
        ProductoVariante(product_id=producto.id, talle="M", color="Negro", stock=1)
    )
    db.session.commit()

    db.session.add(
        ProductoVariante(product_id=producto.id, talle="M", color="Negro", stock=9)
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert ProductoVariante.query.count() == 1


def test_el_unique_tambien_aplica_con_el_eje_vacio(db, vendedor, crear_producto):
    """El caso que se romperia si el eje sin usar fuera NULL.

    Un UNIQUE ignora las filas con NULL en los dos motores, asi que guardando
    NULL la regla se caeria justo en "solo talles", que es el caso mas comun.
    """
    user, post = vendedor
    producto = crear_producto(post.id)

    db.session.add(ProductoVariante(product_id=producto.id, talle="S", stock=1))
    db.session.commit()

    db.session.add(ProductoVariante(product_id=producto.id, talle="S", stock=2))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert ProductoVariante.query.count() == 1


def test_la_misma_combinacion_en_otro_producto_si_entra(
    db, vendedor, crear_producto
):
    """La contraprueba: el UNIQUE es por producto, no global."""
    user, post = vendedor
    uno = crear_producto(post.id, nombre="Remera")
    otro = crear_producto(post.id, nombre="Buzo")

    db.session.add_all([
        ProductoVariante(product_id=uno.id, talle="M", color="Negro", stock=1),
        ProductoVariante(product_id=otro.id, talle="M", color="Negro", stock=1),
    ])
    db.session.commit()

    assert ProductoVariante.query.count() == 2


def test_la_base_rechaza_el_stock_negativo(db, vendedor, crear_producto):
    user, post = vendedor
    producto = crear_producto(post.id)

    db.session.add(
        ProductoVariante(product_id=producto.id, talle="M", stock=-1)
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_la_base_rechaza_un_tipo_de_opcion_inventado(db, vendedor, crear_producto):
    user, post = vendedor
    producto = crear_producto(post.id)

    db.session.add(
        ProductoVarianteOpcion(product_id=producto.id, tipo="talel", valor="M")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_borrar_el_producto_se_lleva_opciones_y_variantes(
    client, login, vendedor, crear_producto, db
):
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M", colores="Negro")

    db.session.delete(producto)
    db.session.commit()

    assert ProductoVariante.query.count() == 0
    assert ProductoVarianteOpcion.query.count() == 0


# ------------------------------------------------- los tres de la auditoria
#
# Tres bugs que encontro la auditoria de la tanda. Los tests van con nombre de
# lo que tiene que pasar y no de "bug N": el que los lea en seis meses necesita
# saber que se espera, no en que informe aparecio.


def test_vaciar_las_dos_listas_devuelve_el_producto_a_como_estaba(
    client, login, vendedor, crear_producto, db
):
    """Apagar las variantes tiene que DEVOLVER el producto, no matarlo.

    Era el bug bloqueante: como sacar un talle apaga sus filas en vez de
    borrarlas, vaciar las dos listas dejaba un producto sin ningun eje pero con
    todas sus filas apagadas todavia ahi. tiene_variantes (que miraba solo las
    filas) seguia en True, con lo cual stock_total daba 0 y disponible_efectivo
    False: la ficha decia "sin stock" y "no queda ninguna combinacion", y no
    habia forma desde la pantalla de volver atras. Justo el camino de apagar las
    variantes dejaba el producto peor que antes de entrar.
    """
    user, post = vendedor
    producto = crear_producto(post.id, precio="12000")
    login(user.id)
    _guardar_listas(client, producto, talles="S, M")
    producto.variantes[1].stock = 5
    db.session.commit()
    assert producto.tiene_variantes is True

    _guardar_listas(client, producto, talles="", colores="")

    # Vuelve a ser un producto de los de siempre.
    assert producto.tiene_variantes is False
    assert producto.stock_total is None
    assert producto.disponible_efectivo is True

    html = client.get(f"/productos/{producto.id}").get_data(as_text=True)
    assert "No queda ninguna combinación disponible" not in html
    assert "12.000" in html

    # Y las filas siguen ahi con su historia, que es la otra mitad del diseño.
    assert ProductoVariante.query.count() == 2


def test_con_los_ejes_cargados_y_todo_apagado_sigue_teniendo_variantes(
    client, login, vendedor, crear_producto, db
):
    """La contraprueba del de arriba: apagar a mano NO es lo mismo que vaciar.

    Con los ejes cargados el producto sigue siendo de variantes aunque no quede
    ninguna encendida, y la ficha tiene que decir "no queda ninguna" -- que es
    verdad -- en vez de volver a mostrar el precio base como si nada.
    """
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M")
    for variante in producto.variantes:
        variante.activo = False
    db.session.commit()

    assert producto.tiene_variantes is True
    assert producto.stock_total == 0
    assert producto.disponible_efectivo is False


def test_el_selector_respeta_el_orden_que_escribio_el_vendedor(
    client, login, vendedor, crear_producto, crear_usuario, db
):
    """Alfabeticamente "S, M, L, XL" es "L, M, S, XL", que no es ningun orden
    de talles. Es el caso que justifica la columna `orden` de las opciones, y la
    grilla del panel ya lo respetaba mientras el selector de la ficha no: el
    vendedor veia una cosa y el comprador otra.
    """
    import re

    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S, M, L, XL")
    for variante in producto.variantes:
        variante.stock = 3
    db.session.commit()

    cliente = crear_usuario(username="clienta")
    login(cliente.id)
    html = client.get(f"/productos/{producto.id}").get_data(as_text=True)
    bloque = html[html.index("<select"):html.index("</select>")]
    orden = [texto.strip().split()[0] for texto in re.findall(r"<option[^>]*>([^<]+)", bloque)]

    assert orden == ["S", "M", "L", "XL"]
    # Y es el mismo orden que ve el vendedor en su grilla, que es el punto.
    assert [fila["talle"] for fila in reglas.grilla(producto)] == ["S", "M", "L", "XL"]


def test_un_stock_gigante_se_rechaza_antes_de_llegar_a_la_base(
    client, login, vendedor, crear_producto
):
    """El tope de arriba hace falta por lo mismo que el de abajo.

    Sin el, un numero mas grande que un INT llega al INSERT y MySQL corta con un
    DataError 1264 que nadie atrapa: el vendedor ve un 500. SQLite lo guarda sin
    chistar, que es por lo que la suite no lo mostraba.
    """
    user, post = vendedor
    producto = crear_producto(post.id)
    login(user.id)
    _guardar_listas(client, producto, talles="S")
    variante = producto.variantes[0]

    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": "99999999999999", "activo": "on"},
    )
    assert variante.stock == 0

    # La contraprueba: el tope exacto SI entra, si no seria un test que pasa
    # aunque la validacion rechace todo.
    client.post(
        f"/productos/{producto.id}/variantes/{variante.id}",
        data={"stock": str(MAX_STOCK), "activo": "on"},
    )
    assert variante.stock == MAX_STOCK
