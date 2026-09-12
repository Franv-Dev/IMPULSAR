"""Lo de las variantes que SQLite no puede probar.

Dos cosas, y las dos cambian el codigo que hay que escribir:

  - UN CHECK VIOLADO EN MySQL ES OperationalError Y NO IntegrityError. En
    SQLite es IntegrityError, asi que un `except IntegrityError` alrededor del
    INSERT parece cubrir el stock negativo en la suite y no lo cubre en
    produccion. Por eso el stock se valida en la vista y el CHECK es solo la
    red de abajo.
  - EL ON DELETE CASCADE de verdad: se borra con SQL crudo y no por la
    sesion del ORM, porque las relaciones tienen cascade="all, delete-orphan" y
    borrando por la sesion el que se lleva las filas es SQLAlchemy, no la base.
  - LA DERIVA ENTRE LOS MODELOS Y LA MIGRACION: el resto de la suite arma las
    tablas con create_all(), o sea desde los modelos, asi que una migracion que
    se olvide de una columna pasaria la suite entera en verde y se enteraria en
    el deploy. Un test compara los dos esquemas.
  - EL UNIQUE COMPUESTO CON EL EJE VACIO. Es la decision de guardar '' y no
    NULL, y hay que verla contra el motor real: si alguna vez alguien cambia la
    columna a nullable, este test se pone en rojo en MySQL antes de que dos
    filas "M" convivan en produccion.

El archivo arma su propia app y no usa las fixtures de conftest, por lo mismo
que app_en_mysql en test_largos.py: con aquellas la app se destruye DESPUES de
esta fixture, y el DROP DATABASE se queda esperando para siempre a una conexion
que todavia no se cerro.
"""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import generate_password_hash

from app.blog.modelo_post import Post
from config import TestingConfig
from db import db as _db
from main import create_app
from models.product import Product
from models.producto_variante import ProductoVariante, ProductoVarianteOpcion
from models.user import Roles, User


def _servidor_mysql():
    """La URI del MySQL local SIN base, armada como la arma config.py."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', '')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    )


@pytest.fixture
def variantes_en_mysql():
    """Un producto con su matriz, contra MySQL, en base descartable."""
    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:  # servidor apagado, credenciales, driver
        pytest.skip(f"sin MySQL local: {error}")

    base = "impulsar_test_variantes"
    with conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
        conexion.execute(
            text(
                f"CREATE DATABASE {base} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )

    with pytest.MonkeyPatch.context() as parche:
        parche.setattr(
            TestingConfig, "SQLALCHEMY_DATABASE_URI", f"{_servidor_mysql()}/{base}"
        )
        app = create_app("testing")

    with app.app_context():
        _db.create_all()
        dueña = User(
            username="vendedora", email="v@test.com",
            password=generate_password_hash("secreta123"), rol=Roles.EMPRENDEDOR,
        )
        _db.session.add(dueña)
        _db.session.commit()
        post = Post(author=dueña.id, title="Ropa", body="Remeras")
        _db.session.add(post)
        _db.session.commit()
        producto = Product(post_id=post.id, nombre="Remera", precio="12000")
        _db.session.add(producto)
        _db.session.commit()

        yield SimpleNamespace(app=app, db=_db, producto=producto, post=post)

        _db.session.remove()
        motores = list(app.extensions["sqlalchemy"].engines.values())

    for motor_de_la_app in motores:
        motor_de_la_app.dispose()
    with motor.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
    motor.dispose()


def test_en_mysql_la_combinacion_duplicada_no_entra(variantes_en_mysql):
    """El UNIQUE compuesto, contra el motor de produccion."""
    producto = variantes_en_mysql.producto
    db = variantes_en_mysql.db

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


def test_en_mysql_el_unique_aplica_con_el_eje_vacio(variantes_en_mysql):
    """La razon de guardar '' y no NULL, vista contra el motor real.

    Con NULL en `color`, MySQL dejaria entrar las dos filas sin decir nada,
    porque un UNIQUE ignora las filas que tienen un NULL. Con la cadena vacia
    la regla vale, que es justo el caso "este producto solo usa talles".
    """
    producto = variantes_en_mysql.producto
    db = variantes_en_mysql.db

    db.session.add(ProductoVariante(product_id=producto.id, talle="S", stock=1))
    db.session.commit()

    db.session.add(ProductoVariante(product_id=producto.id, talle="S", stock=2))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert ProductoVariante.query.count() == 1


def test_en_mysql_un_check_violado_es_operational_y_no_integrity(variantes_en_mysql):
    """Por esto el stock se valida en la vista y no se atrapa el choque.

    En SQLite esto mismo es un IntegrityError, asi que un `except
    IntegrityError` alrededor del INSERT pasaria la suite entera y dejaria al
    vendedor viendo un 500 en produccion.
    """
    producto = variantes_en_mysql.producto
    db = variantes_en_mysql.db

    db.session.add(ProductoVariante(product_id=producto.id, talle="M", stock=-1))
    with pytest.raises(OperationalError):
        db.session.commit()
    db.session.rollback()

    db.session.add(
        ProductoVarianteOpcion(product_id=producto.id, tipo="talel", valor="M")
    )
    with pytest.raises(OperationalError):
        db.session.commit()
    db.session.rollback()


def test_en_mysql_borrar_el_producto_se_lleva_las_dos_tablas(variantes_en_mysql):
    """El ON DELETE CASCADE de las dos FK, con el motor que de verdad lo aplica.

    SE BORRA CON UN DELETE CRUDO Y NO CON db.session.delete(), que es la
    diferencia entre probar la base y probar el ORM: las dos relaciones tienen
    cascade="all, delete-orphan", asi que borrando por la sesion SQLAlchemy
    emite los DELETE hijos el mismo y el test pasaria aunque la FK no cascadeara
    -- o sea, no probaria lo que dice el nombre. Con SQL crudo el unico que
    puede llevarse las filas es el motor.

    Version corregida despues de la auditoria de la tanda, que marco justo esto.
    """
    producto = variantes_en_mysql.producto
    db = variantes_en_mysql.db

    db.session.add_all([
        ProductoVariante(product_id=producto.id, talle="M", color="Negro", stock=1),
        ProductoVarianteOpcion(product_id=producto.id, tipo="talle", valor="M"),
    ])
    db.session.commit()
    producto_id = producto.id

    # El expunge_all no es por el conteo -- Query.count() emite un COUNT contra
    # la base y no mira el identity map, asi que el numero seria honesto igual
    # (lo marco la auditoria, y tenia razon). Es para que las instancias que
    # quedaron en la sesion no se refresquen contra filas que la base ya borro
    # si alguien agrega un assert sobre ellas mas abajo.
    db.session.expunge_all()
    db.session.execute(
        text("DELETE FROM products WHERE id = :id"), {"id": producto_id}
    )
    db.session.commit()

    assert ProductoVariante.query.count() == 0
    assert ProductoVarianteOpcion.query.count() == 0


def test_en_mysql_la_pantalla_de_variantes_responde(variantes_en_mysql):
    """La pantalla entera y no solo las consultas sueltas."""
    producto = variantes_en_mysql.producto
    cliente = variantes_en_mysql.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["user_id"] = variantes_en_mysql.post.author

    cliente.post(
        f"/productos/{producto.id}/variantes/opciones",
        data={"talles": "S, M, L", "colores": "Negro, Blanco"},
    )
    assert ProductoVariante.query.count() == 6

    respuesta = cliente.get(f"/productos/{producto.id}/variantes")
    assert respuesta.status_code == 200
    assert "S / Negro" in respuesta.get_data(as_text=True)


# --------------------------------------------- la migracion contra los modelos

def _esquema_de(inspector, tabla):
    """El esquema de una tabla, en una forma comparable entre dos bases.

    Se queda con lo que una migracion puede equivocarse y que el motor devuelve
    de forma estable: nombre y tipo de cada columna, si acepta NULL, su default
    del lado del servidor, y los nombres de las constraints y de los indices.

    NO se comparan cosas que dependen de como se creo la tabla y no de que
    guarda (el orden fisico, el ROW_FORMAT, el auto_increment), porque haria
    fallar el test por diferencias que no le importan a nadie.
    """
    columnas = {}
    for columna in inspector.get_columns(tabla):
        default = columna.get("default")
        columnas[columna["name"]] = (
            str(columna["type"]),
            bool(columna["nullable"]),
            # MySQL devuelve los defaults de texto entre comillas segun la
            # version; se normaliza para que "''" y "" no se lean distinto.
            (default or "").strip("'") if default is not None else None,
        )

    return {
        "columnas": columnas,
        "unicos": {
            (u["name"], tuple(u["column_names"]))
            for u in inspector.get_unique_constraints(tabla)
        },
        "checks": {c["name"] for c in inspector.get_check_constraints(tabla)},
        "fks": {
            (f["name"], tuple(f["constrained_columns"]), f["referred_table"],
             (f.get("options") or {}).get("ondelete"))
            for f in inspector.get_foreign_keys(tabla)
        },
        "indices": {i["name"] for i in inspector.get_indexes(tabla)},
    }


def test_en_mysql_la_migracion_deja_el_mismo_esquema_que_los_modelos():
    """La migracion y create_all() tienen que dar la MISMA tabla.

    ES EL UNICO TEST QUE MIRA LA MIGRACION. Todo el resto de la suite -- este
    archivo incluido -- arma las tablas con create_all(), o sea desde los
    modelos, y ahi esta el agujero: el dia que alguien agregue una columna al
    modelo y se olvide de la migracion, create_all() la crea, la suite pasa
    entera en verde y produccion se entera en el deploy. La deriva es el riesgo
    real, no el de hoy -- hoy los dos esquemas son identicos y se comprobo a
    mano dos veces.

    CUESTA ~21 SEGUNDOS, o sea cerca del 4 % de la corrida, y el numero esta
    medido y no estimado. Conviene dejar claro de donde salen los dos numeros
    que circularon: la auditoria midio +5,5 s, que es la diferencia entre
    create_all y upgrade sobre UNA base; este test arma las DOS (una por cada
    camino, que es la unica forma de comparar los esquemas), asi que paga
    ademas el segundo CREATE DATABASE y la segunda app. Tampoco eran los
    "varios minutos" de la primera estimacion a ojo, que estaba mal y era lo
    unico que sostenia dejar esto afuera.

    Se probo que sirve y no solo que pasa: agregando una columna al modelo sin
    tocar la migracion, el test se pone en rojo.

    Arma DOS bases descartables, una por cada camino, y nunca impulsar_db.
    """
    from flask_migrate import upgrade
    from sqlalchemy import inspect

    try:
        motor = create_engine(_servidor_mysql())
        conexion = motor.connect()
    except Exception as error:
        pytest.skip(f"sin MySQL local: {error}")

    bases = ("impulsar_test_migracion", "impulsar_test_modelos")
    with conexion:
        for base in bases:
            conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
            conexion.execute(
                text(
                    f"CREATE DATABASE {base} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )

    tablas = ("producto_variantes", "producto_variante_opciones")
    esquemas = {}
    try:
        for base, como in zip(bases, ("migracion", "modelos")):
            with pytest.MonkeyPatch.context() as parche:
                parche.setattr(
                    TestingConfig, "SQLALCHEMY_DATABASE_URI",
                    f"{_servidor_mysql()}/{base}",
                )
                app = create_app("testing")

            with app.app_context():
                if como == "migracion":
                    # La cadena entera, como en produccion.
                    upgrade()
                else:
                    _db.create_all()

                inspector = inspect(_db.engine)
                esquemas[como] = {
                    tabla: _esquema_de(inspector, tabla) for tabla in tablas
                }
                _db.session.remove()
                motores = list(app.extensions["sqlalchemy"].engines.values())
            for motor_de_la_app in motores:
                motor_de_la_app.dispose()
    finally:
        with motor.connect() as conexion:
            for base in bases:
                conexion.execute(text(f"DROP DATABASE IF EXISTS {base}"))
        motor.dispose()

    for tabla in tablas:
        assert esquemas["migracion"][tabla] == esquemas["modelos"][tabla], (
            f"{tabla}: la migracion y los modelos dejan tablas distintas. "
            "Alguien toco el modelo sin escribir la migracion (o al reves)."
        )


def test_en_mysql_el_catalogo_pinta_el_resumen_de_variantes(variantes_en_mysql):
    """La consulta del catalogo con su agregacion, contra el motor de produccion.

    ES EL TEST QUE JUSTIFICA LA FORMA DE LA CONSULTA, y por eso pide la pagina
    entera y no la Query suelta: lo que hay que ver es el SELECT completo, con
    el joinedload del emprendimiento, el ORDER BY y el COUNT del paginado.

    Dos cosas que SQLite no puede decir:

      - ONLY_FULL_GROUP_BY. Agrupando la consulta de afuera por products.id,
        las columnas de `posts` que mete el joinedload no dependen
        funcionalmente de esa PK y MySQL corta con el error 1055; SQLite las
        acepta callado. Que esta pagina venga en 200 es lo que prueba que el
        GROUP BY quedo adentro de las subconsultas.
      - el encabezado cuenta FILAS y no grupos: con un GROUP BY afuera, el
        COUNT del paginado contaria grupos y el "1 producto" seria otra cosa.

    El producto vale 12000 y tiene tres combinaciones: una a 9000 encendida y
    con stock, una que hereda el precio (12000) sin stock, y una a 20000
    apagada. Asi el minimo (9000), el maximo (12000, o sea "desde") y el stock
    salen cada uno de una fila distinta, y ninguno se puede acertar por
    casualidad.
    """
    producto = variantes_en_mysql.producto
    db = variantes_en_mysql.db

    for orden, talle in enumerate(("S", "M", "L")):
        db.session.add(ProductoVarianteOpcion(
            product_id=producto.id, tipo="talle", valor=talle, orden=orden,
        ))
    db.session.add_all([
        ProductoVariante(
            product_id=producto.id, talle="S", stock=3,
            precio_override="9000", activo=True,
        ),
        ProductoVariante(
            product_id=producto.id, talle="M", stock=0,
            precio_override=None, activo=True,
        ),
        ProductoVariante(
            product_id=producto.id, talle="L", stock=7,
            precio_override="20000", activo=False,
        ),
    ])
    db.session.commit()

    respuesta = variantes_en_mysql.app.test_client().get("/productos/")
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "desde $ 9.000,00" in html
    assert "1 producto" in html
    assert "producto-tarjeta__agotado" not in html
