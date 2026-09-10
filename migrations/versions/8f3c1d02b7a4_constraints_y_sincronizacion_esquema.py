"""Sincronizar el esquema con los modelos y agregar constraints

Revision ID: 8f3c1d02b7a4
Revises: 72d2e64a3fae
Create Date: 2026-08-13

Contexto: hasta ahora las tablas se venian creando con db.create_all() y no con
migraciones, asi que el historial de Alembic no reflejaba el modelo real (por
ejemplo, las columnas de ubicacion y la tabla reviews nunca tuvieron migracion).

Por eso esta migracion es idempotente: mira que hay en la base y agrega solo lo
que falta. Funciona igual sobre una base vacia (crea todo) que sobre una base ya
en uso (completa lo que falte y agrega los constraints nuevos).
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f3c1d02b7a4'
down_revision = '72d2e64a3fae'
branch_labels = None
depends_on = None


@contextmanager
def _sin_foreign_keys_en_sqlite():
    """Apaga la verificacion de FK mientras dura el batch, solo en SQLite.

    En SQLite un batch_alter_table recrea la tabla: copia a una temporal,
    dropea la original y renombra. Aca hace falta porque users es una tabla
    referenciada y db.py deja PRAGMA foreign_keys=ON en toda conexion: si ya
    hay filas hijas, el DROP TABLE users muere con "FOREIGN KEY constraint
    failed". Es el mismo caso que d4a2b6f19c73 con posts, b2b97d078fb2 con
    reviews y a3f1c9d47b52 con users, y esta copiada de ahi por la misma razon
    que se duplica _nombre_fk en esas: una migracion es una foto de un momento
    y tiene que poder correr sola.

    En MySQL no hace falta: ahi el batch es un ALTER TABLE comun, sin recrear.

    Al salir se hace detach de la conexion en vez de volver a prender el
    pragma: prenderlo no serviria de nada, porque en SQLite un PRAGMA es no-op
    si ya hay una transaccion abierta, y a esa altura el batch ya emitio DML.
    Por lo mismo, el bloque tiene que abrirse ANTES de cualquier DML de la
    migracion, no solo antes del batch que recrea.
    """
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        yield
        return

    bind.exec_driver_sql('PRAGMA foreign_keys=OFF')

    # El OFF se relee para confirmar que agarro. En SQLite un PRAGMA es un
    # no-op SILENCIOSO si ya hay una transaccion abierta: no tira error, no
    # avisa, simplemente no apaga nada. Sin este chequeo el sintoma aparece
    # recien mas adelante, como un "FOREIGN KEY constraint failed" sobre un
    # DROP TABLE que no explica por que las FK seguian prendidas.
    if bind.exec_driver_sql('PRAGMA foreign_keys').scalar():
        raise RuntimeError(
            "PRAGMA foreign_keys sigue en ON despues del OFF: hay una "
            "transaccion abierta antes de este punto y el pragma quedo en "
            "no-op. Este bloque tiene que abrirse antes de cualquier DML de "
            "la migracion."
        )

    try:
        yield
    finally:
        # detach() y no invalidate(): invalidar tira la conexion en el acto y
        # alembic todavia la necesita para escribir alembic_version.
        bind.detach()


# ---------------------------------------------------------------- utilidades

def _columnas(inspector, tabla):
    return {col["name"] for col in inspector.get_columns(tabla)}


def _constraints_unique(inspector, tabla):
    nombres = {uc["name"] for uc in inspector.get_unique_constraints(tabla)}
    # En MySQL un UNIQUE tambien aparece como indice unico.
    nombres |= {ix["name"] for ix in inspector.get_indexes(tabla) if ix.get("unique")}
    return nombres


def _indices(inspector, tabla):
    return {ix["name"] for ix in inspector.get_indexes(tabla)}


def _abortar_si_hay_duplicados(bind, tabla, columnas):
    """Un UNIQUE no se puede crear si ya hay datos repetidos.

    Preferimos cortar con un mensaje claro antes que dejar que la base tire un
    error indescifrable a mitad de la migracion.
    """
    lista = ", ".join(columnas)
    filas = bind.execute(
        sa.text(f"SELECT {lista} FROM {tabla} GROUP BY {lista} HAVING COUNT(*) > 1")
    ).fetchall()
    if filas:
        raise RuntimeError(
            f"No se puede aplicar la migracion: la tabla '{tabla}' tiene valores "
            f"repetidos en ({lista}): {filas}. "
            f"Limpia o unifica esos registros y volve a correr 'flask db upgrade'."
        )


def _abortar_si_hay_nulos(bind, tabla, columna):
    total = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {tabla} WHERE {columna} IS NULL")
    ).scalar()
    if total:
        raise RuntimeError(
            f"No se puede aplicar la migracion: hay {total} fila(s) en '{tabla}' "
            f"con '{columna}' vacio, y esa columna pasa a ser obligatoria. "
            f"Completa o elimina esos registros y volve a intentar."
        )


# ------------------------------------------------------------------- upgrade

def upgrade():
    with _sin_foreign_keys_en_sqlite():
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        tablas = set(inspector.get_table_names())

        # ---- users ----
        if "users" not in tablas:
            op.create_table(
                "users",
                sa.Column("id", sa.Integer(), nullable=False),
                sa.Column("username", sa.String(length=50), nullable=False),
                sa.Column("password", sa.Text(), nullable=False),
                sa.Column("rol", sa.String(length=50), nullable=False),
                sa.Column("email", sa.String(length=120), nullable=False),
                sa.Column("biography", sa.Text(), nullable=True),
                sa.Column("latitude", sa.Float(), nullable=True),
                sa.Column("longitude", sa.Float(), nullable=True),
                sa.Column("address_street", sa.String(length=255), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=False,
                          server_default=sa.func.now()),
                sa.Column("updated_at", sa.DateTime(), nullable=False,
                          server_default=sa.func.now()),
                sa.PrimaryKeyConstraint("id"),
            )
            op.create_index("ix_users_username", "users", ["username"], unique=True)
            op.create_index("ix_users_email", "users", ["email"], unique=True)
        else:
            cols = _columnas(inspector, "users")

            with op.batch_alter_table("users") as batch:
                if "biography" not in cols:
                    batch.add_column(sa.Column("biography", sa.Text(), nullable=True))
                if "latitude" not in cols:
                    batch.add_column(sa.Column("latitude", sa.Float(), nullable=True))
                if "longitude" not in cols:
                    batch.add_column(sa.Column("longitude", sa.Float(), nullable=True))
                if "address_street" not in cols:
                    batch.add_column(sa.Column("address_street", sa.String(length=255), nullable=True))
                if "created_at" not in cols:
                    batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=False,
                                               server_default=sa.func.now()))
                if "updated_at" not in cols:
                    batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False,
                                               server_default=sa.func.now()))

            # username y email pasan a ser obligatorios y unicos.
            for columna in ("username", "email", "password"):
                _abortar_si_hay_nulos(bind, "users", columna)
            _abortar_si_hay_duplicados(bind, "users", ["username"])
            _abortar_si_hay_duplicados(bind, "users", ["email"])

            with op.batch_alter_table("users") as batch:
                batch.alter_column("username", existing_type=sa.String(length=50), nullable=False)
                batch.alter_column("password", existing_type=sa.Text(), nullable=False)
                batch.alter_column("rol", existing_type=sa.String(length=50), nullable=False,
                                   server_default="usuario")
                # El email pasa de 50 a 120: 50 se queda corto para direcciones reales.
                batch.alter_column("email", existing_type=sa.String(length=50),
                                   type_=sa.String(length=120), nullable=False)

            indices = _indices(inspector, "users")
            if "ix_users_username" not in indices:
                op.create_index("ix_users_username", "users", ["username"], unique=True)
            if "ix_users_email" not in indices:
                op.create_index("ix_users_email", "users", ["email"], unique=True)

        # ---- posts ----
        if "posts" not in tablas:
            op.create_table(
                "posts",
                sa.Column("id", sa.Integer(), nullable=False),
                sa.Column("author", sa.Integer(), nullable=False),
                sa.Column("title", sa.String(length=100), nullable=True),
                sa.Column("body", sa.Text(), nullable=True),
                sa.Column("created", sa.DateTime(), nullable=False),
                sa.Column("image", sa.String(length=100), nullable=True),
                sa.Column("latitude", sa.Float(), nullable=True),
                sa.Column("longitude", sa.Float(), nullable=True),
                sa.Column("address_street", sa.String(length=255), nullable=True),
                # Con nombre explicito, por lo mismo que las de reviews mas abajo:
                # sin nombre seria posts_ibfk_1 en MySQL y nada en SQLite, y la
                # migracion que le agrega el ON DELETE CASCADE necesita dropearla.
                sa.ForeignKeyConstraint(["author"], ["users.id"],
                                        name="fk_posts_author_users"),
                sa.PrimaryKeyConstraint("id"),
            )
            op.create_index("ix_posts_author", "posts", ["author"])
        else:
            cols = _columnas(inspector, "posts")
            with op.batch_alter_table("posts") as batch:
                if "image" not in cols:
                    batch.add_column(sa.Column("image", sa.String(length=100), nullable=True))
                if "latitude" not in cols:
                    batch.add_column(sa.Column("latitude", sa.Float(), nullable=True))
                if "longitude" not in cols:
                    batch.add_column(sa.Column("longitude", sa.Float(), nullable=True))
                if "address_street" not in cols:
                    batch.add_column(sa.Column("address_street", sa.String(length=255), nullable=True))

            # Indice en la FK: se filtra por autor en "mis emprendimientos".
            if "ix_posts_author" not in _indices(inspector, "posts"):
                op.create_index("ix_posts_author", "posts", ["author"])

        # ---- reviews ----
        if "reviews" not in tablas:
            op.create_table(
                "reviews",
                sa.Column("id", sa.Integer(), nullable=False),
                sa.Column("post_id", sa.Integer(), nullable=False),
                sa.Column("user_id", sa.Integer(), nullable=False),
                sa.Column("rating", sa.Integer(), nullable=False),
                sa.Column("comment", sa.Text(), nullable=True),
                sa.Column("created", sa.DateTime(), nullable=False),
                # Con nombre explicito: sin nombre cada motor le pone el suyo
                # (reviews_ibfk_1/2 en MySQL, ninguno en SQLite), asi que una
                # migracion posterior que necesite dropearlas no tendria un nombre
                # que sirva en los dos. Es lo que rompio d09128dd029c (ver 22dd9d0).
                # Ojo: esto solo aplica a las bases que se crean desde cero. Una
                # base que ya tenia la tabla (la rama else) sigue con los nombres
                # que le puso su motor.
                sa.ForeignKeyConstraint(["post_id"], ["posts.id"],
                                        name="fk_reviews_post_id_posts"),
                sa.ForeignKeyConstraint(["user_id"], ["users.id"],
                                        name="fk_reviews_user_id_users"),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("post_id", "user_id", name="uq_review_post_user"),
                sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
            )
        else:
            if "uq_review_post_user" not in _constraints_unique(inspector, "reviews"):
                # Si un usuario dejo varias resenas al mismo post, hay que quedarse
                # con una sola antes de poder crear el UNIQUE.
                _abortar_si_hay_duplicados(bind, "reviews", ["post_id", "user_id"])
                # batch_alter_table para que tambien funcione en SQLite, que no
                # soporta ALTER de constraints (util para los tests).
                with op.batch_alter_table("reviews") as batch:
                    batch.create_unique_constraint(
                        "uq_review_post_user", ["post_id", "user_id"]
                    )


# ----------------------------------------------------------------- downgrade

def downgrade():
    """Revierte solo los constraints e indices que agrega esta migracion.

    No se borran columnas ni tablas a proposito: hacerlo destruiria datos de
    usuarios (ubicaciones, resenas) que ya podrian estar cargados.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tablas = set(inspector.get_table_names())

    if "reviews" in tablas and "uq_review_post_user" in _constraints_unique(inspector, "reviews"):
        with op.batch_alter_table("reviews") as batch:
            batch.drop_constraint("uq_review_post_user", type_="unique")

    if "posts" in tablas and "ix_posts_author" in _indices(inspector, "posts"):
        op.drop_index("ix_posts_author", table_name="posts")

    if "users" in tablas:
        indices = _indices(inspector, "users")
        if "ix_users_email" in indices:
            op.drop_index("ix_users_email", table_name="users")
        if "ix_users_username" in indices:
            op.drop_index("ix_users_username", table_name="users")
