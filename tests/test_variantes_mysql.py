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

    # Se saca todo de la sesion antes del DELETE crudo: si no, el identity map
    # sigue devolviendo las filas que la base ya borro y el conteo mentiria.
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
