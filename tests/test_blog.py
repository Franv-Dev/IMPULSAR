import pytest
from flask import Flask, g, session
from views.blog import blog, allowed_file, get_user, get_post
from models.user import User
from models.post import Post
from db import db



# FIXTURES


@pytest.fixture
def app():
    """Aplicación de prueba con BD aislada en memoria."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "testing-secret"

    db.init_app(app)
    app.register_blueprint(blog)

    # Simula el load_logged_in_user de auth (usa session["user_id"])
    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
        else:
            g.user = User.query.get(user_id)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login_as(client, user_id: int):
    """Helper para loguear un usuario en los tests."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id



# TESTS UNITARIOS


def test_allowed_file_valid_extensions():

    assert allowed_file("foto.jpg")
    assert allowed_file("imagen.PNG")      
    assert allowed_file("algo.JPEG")
    assert not allowed_file("documento.pdf")
    assert not allowed_file("foto")        


def test_user_model_creation(app):

    with app.app_context():
        u = User(
            username="testuser",
            email="t@t.com",
            password="1234",
            rol="usuario",          
        )
        db.session.add(u)
        db.session.commit()

        found = User.query.filter_by(username="testuser").first()
        assert found is not None
        assert found.email == "t@t.com"
        assert found.rol == "usuario"


def test_get_post_check_author_blocked_redirects(app):

    with app.app_context():
        autor = User(
            username="autor",
            email="a@a.com",
            password="123",
            rol="usuario",   
        )      
        otro = User(
            username="otro",
            email="b@b.com",
            password="123",
            rol="usuario",          
        )
        db.session.add_all([autor, otro])
        db.session.commit()

        post = Post(title="titulo", body="contenido", author=autor.id)
        db.session.add(post)
        db.session.commit()

        # simulamos request con g.user = otro
        with app.test_request_context():
            g.user = otro
            resp = get_post(post.id, check_author=True)

            assert resp.status_code == 302
            assert "/blog/mis-emprendimientos" in resp.location



# TEST DE INTEGRACIÓN


def test_flow_create_update_delete_post(client, app):
    
    # 1) Crear usuario autor en la BD
    with app.app_context():
        autor = User(
            username="autor",
            email="autor@test.com",
            password="123",
            rol="usuario",
        )
        db.session.add(autor)
        db.session.commit()
        autor_id = autor.id

    # Loguear al autor para que pase el @login_required
    login_as(client, autor_id)

    # 2) CREATE – crear post (NO seguimos el redirect)
    resp = client.post(
        "/blog/create",
        data={"title": "Titulo original", "body": "Contenido inicial"},
        follow_redirects=False,
    )
    # debe redirigir a mis-emprendimientos
    assert resp.status_code == 302
    assert "/blog/mis-emprendimientos" in resp.headers.get("Location", "")

    with app.app_context():
        post = Post.query.filter_by(title="Titulo original").first()
        assert post is not None
        post_id = post.id

    # 3) UPDATE – modificar título y cuerpo
    resp = client.post(
        f"/blog/update/{post_id}",
        data={"title": "Titulo modificado", "body": "Contenido editado"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/blog/mis-emprendimientos" in resp.headers.get("Location", "")

    with app.app_context():
        post = Post.query.get(post_id)
        assert post is not None
        assert post.title == "Titulo modificado"
        assert post.body == "Contenido editado"

    # 4) DELETE – eliminar publicación (solo por POST, un GET no debe borrar)
    resp = client.get(f"/blog/delete/{post_id}", follow_redirects=False)
    assert resp.status_code == 405, "Borrar por GET debe estar prohibido"

    resp = client.post(f"/blog/delete/{post_id}", follow_redirects=False)
    assert resp.status_code == 302
    assert "/blog/mis-emprendimientos" in resp.headers.get("Location", "")

    with app.app_context():
        deleted = Post.query.get(post_id)
        assert deleted is None
