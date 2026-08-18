"""Tests de reportes de contenido inapropiado y su integracion con el panel de admin."""

import threading

import pytest
from sqlalchemy.exc import IntegrityError

from app.blog.modelo_post import Post
from app.blog.modelo_reporte import Report
from app.blog.modelo_resenia import Review
from db import db as _db
from main import create_app
from models.user import Roles, User


def test_reportar_un_emprendimiento(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Contenido falso"})

    reporte = Report.query.filter_by(post_id=post.id).first()
    assert reporte is not None
    assert reporte.reason == "Contenido falso"
    assert reporte.reporter_id == denunciante.id
    assert reporte.resolved is False


def test_no_se_puede_reportar_el_propio_emprendimiento(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    login(autor.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})

    assert Report.query.count() == 0


def test_reportar_una_resenia(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1, comment="Insultos")
    db.session.add(review)
    db.session.commit()

    login(denunciante.id)
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "Lenguaje ofensivo"})

    reporte = Report.query.filter_by(review_id=review.id).first()
    assert reporte is not None


def test_no_se_puede_reportar_la_propia_resenia(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=3)
    db.session.add(review)
    db.session.commit()

    login(cliente.id)
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "x"})

    assert Report.query.count() == 0


def test_reportar_sin_motivo_no_guarda_nada(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "   "})

    assert Report.query.count() == 0


def test_reportar_requiere_login(client, crear_usuario, crear_post):
    autor = crear_usuario(username="autor")
    post = crear_post(autor.id)

    resp = client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"}, follow_redirects=False)

    assert resp.status_code == 302


# ---------------------------------------------------------- spam de reportes

def test_no_se_puede_reportar_dos_veces_el_mismo_post(client, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Motivo uno"})
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Motivo dos"})

    assert Report.query.filter_by(post_id=post.id, reporter_id=denunciante.id).count() == 1


def test_no_se_puede_reportar_dos_veces_la_misma_resenia(client, db, crear_usuario, crear_post, login):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1)
    db.session.add(review)
    db.session.commit()

    login(denunciante.id)
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "uno"})
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "dos"})

    assert Report.query.filter_by(review_id=review.id, reporter_id=denunciante.id).count() == 1


def test_dos_usuarios_distintos_pueden_reportar_el_mismo_post(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    uno = crear_usuario(username="uno")
    dos = crear_usuario(username="dos")
    post = crear_post(autor.id)

    login(uno.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})
    login(dos.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "y"})

    assert Report.query.filter_by(post_id=post.id).count() == 2


def test_se_puede_reportar_de_nuevo_despues_de_que_el_primero_se_resuelva(
    client, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "primero"})
    primer_reporte = Report.query.filter_by(post_id=post.id).first()

    login(admin.id)
    client.post(f"/admin/reportes/{primer_reporte.id}/resolver")

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "segundo"})

    assert Report.query.filter_by(post_id=post.id, reporter_id=denunciante.id).count() == 2


def test_el_formulario_avisa_si_ya_hay_un_reporte_pendiente(
    client, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})

    html = client.get(f"/blog/reportar/post/{post.id}").get_data(as_text=True)

    assert "Ya tenés un reporte pendiente" in html


def test_el_panel_de_admin_lista_los_reportes_pendientes(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id, title="Emprendimiento sospechoso")

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Estafa"})

    login(admin.id)
    html = client.get("/admin/reportes").get_data(as_text=True)

    assert "Emprendimiento sospechoso" in html
    assert "Estafa" in html


def test_el_admin_puede_marcar_un_reporte_como_resuelto(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})
    reporte = Report.query.filter_by(post_id=post.id).first()

    login(admin.id)
    client.post(f"/admin/reportes/{reporte.id}/resolver")

    db.session.refresh(reporte)
    assert reporte.resolved is True
    assert reporte.resolved_at is not None


def test_un_reporte_resuelto_no_aparece_en_pendientes(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id, title="Ya resuelto")

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})
    reporte = Report.query.filter_by(post_id=post.id).first()

    login(admin.id)
    client.post(f"/admin/reportes/{reporte.id}/resolver")
    html = client.get("/admin/reportes").get_data(as_text=True)

    assert "Ya resuelto" not in html


def test_el_dashboard_cuenta_los_reportes_pendientes(
    client, db, crear_usuario, crear_post, login
):
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})

    login(admin.id)
    html = client.get("/admin/").get_data(as_text=True)

    assert "Reportes pendientes" in html


# --------------------------------------------- ON DELETE CASCADE (FK 1451)

def test_se_puede_eliminar_un_post_con_un_reporte_sin_resolver(
    client, db, crear_usuario, crear_post, login
):
    """Antes del fix, esto fallaba con IntegrityError 1451 en MySQL: el FK
    de reports.post_id era RESTRICT por default."""
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Estafa"})
    assert Report.query.filter_by(post_id=post.id).count() == 1

    login(autor.id)
    resp = client.post(f"/blog/delete/{post.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert Post.query.get(post.id) is None
    # El reporte se va con el post: no queda huerfano.
    assert Report.query.filter_by(post_id=post.id).count() == 0


def test_se_puede_eliminar_un_post_con_un_reporte_ya_resuelto(
    client, db, crear_usuario, crear_post, login
):
    """El reporte resuelto tampoco debe bloquear el borrado."""
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    post = crear_post(autor.id)

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "x"})
    reporte = Report.query.filter_by(post_id=post.id).first()

    login(admin.id)
    client.post(f"/admin/reportes/{reporte.id}/resolver")
    resp = client.post(f"/admin/emprendimientos/{post.id}/eliminar", follow_redirects=False)

    assert resp.status_code == 302
    assert Post.query.get(post.id) is None


def test_se_puede_eliminar_una_resenia_con_un_reporte(
    client, db, crear_usuario, crear_post, login
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1, comment="Insultos")
    db.session.add(review)
    db.session.commit()

    login(denunciante.id)
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "Lenguaje ofensivo"})

    login(cliente.id)
    resp = client.post(f"/blog/review/{review.id}/delete", follow_redirects=False)

    assert resp.status_code == 302
    assert Review.query.get(review.id) is None
    assert Report.query.filter_by(review_id=review.id).count() == 0


def test_eliminar_un_post_reportado_no_deja_huerfano_al_borrarlo_en_cascada(
    client, db, crear_usuario, crear_post, login
):
    """La resenia se borra en cascada junto con el post (comportamiento previo,
    ver app/blog/modelo_resenia.py); el reporte sobre esa resenia tiene que seguirla."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1)
    db.session.add(review)
    db.session.commit()

    login(denunciante.id)
    client.post(f"/blog/reportar/review/{review.id}", data={"reason": "x"})

    login(autor.id)
    resp = client.post(f"/blog/delete/{post.id}", follow_redirects=False)

    assert resp.status_code == 302
    assert Review.query.get(review.id) is None
    assert Report.query.filter_by(review_id=review.id).count() == 0


# --- un solo reporte pendiente: la constraint, no el chequeo

def _reporte(db, reporter_id, post_id=None, review_id=None, motivo="Contenido falso",
             resolved=False):
    reporte = Report(
        reporter_id=reporter_id, post_id=post_id, review_id=review_id,
        reason=motivo, resolved=resolved,
    )
    db.session.add(reporte)
    db.session.commit()
    return reporte


def test_la_base_rechaza_dos_reportes_pendientes_del_mismo_usuario_y_post(
    db, crear_usuario, crear_post
):
    """El freno tiene que estar en la base y no solo en la vista: es lo unico
    que no se puede saltear metiendo dos requests a la vez."""
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    _reporte(db, denunciante.id, post_id=post.id)

    with pytest.raises(IntegrityError):
        _reporte(db, denunciante.id, post_id=post.id, motivo="Lo mismo otra vez")

    db.session.rollback()


def test_la_base_rechaza_dos_reportes_pendientes_del_mismo_usuario_y_resenia(
    db, crear_usuario, crear_post
):
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1, comment="Insultos")
    db.session.add(review)
    db.session.commit()
    _reporte(db, denunciante.id, review_id=review.id)

    with pytest.raises(IntegrityError):
        _reporte(db, denunciante.id, review_id=review.id, motivo="Lo mismo")

    db.session.rollback()


def test_un_post_y_una_resenia_con_el_mismo_id_no_se_pisan(db, crear_usuario, crear_post):
    """La clave lleva prefijo justamente por esto: sin la 'p' y la 'r', el post 3
    y la resenia 3 caerian en el mismo valor y el segundo reporte rebotaria."""
    autor = crear_usuario(username="autor")
    cliente = crear_usuario(username="cliente")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    review = Review(post_id=post.id, user_id=cliente.id, rating=1, comment="Insultos")
    db.session.add(review)
    db.session.commit()

    _reporte(db, denunciante.id, post_id=post.id)
    _reporte(db, denunciante.id, review_id=review.id)

    assert Report.query.count() == 2


def test_la_constraint_no_toca_los_reportes_ya_resueltos(db, crear_usuario, crear_post):
    """El UNIQUE es sobre clave_pendiente, que solo tiene valor mientras el
    reporte esta sin resolver: de los resueltos puede haber todos los que sea."""
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)

    _reporte(db, denunciante.id, post_id=post.id, resolved=True)
    _reporte(db, denunciante.id, post_id=post.id, motivo="Otra vez", resolved=True)

    assert Report.query.count() == 2


def test_resolver_un_reporte_libera_la_clave(db, client, crear_usuario, crear_post, login):
    """La clave la mantiene el listener del modelo, asi que tiene que soltarse
    sola cuando el admin resuelve, sin que la vista la toque."""
    admin = crear_usuario(username="jefa", rol=Roles.ADMIN)
    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    reporte = _reporte(db, denunciante.id, post_id=post.id)

    login(admin.id)
    client.post(f"/admin/reportes/{reporte.id}/resolver")

    assert Report.query.get(reporte.id).clave_pendiente is None

    login(denunciante.id)
    client.post(f"/blog/reportar/post/{post.id}", data={"reason": "Volvio a las andadas"})

    assert Report.query.count() == 2


def test_otra_violacion_de_integridad_no_se_disfraza_de_reporte_duplicado(
    client, db, crear_usuario, crear_post, login, monkeypatch
):
    """El INSERT puede fallar por otra cosa: aca el autor borra el post justo
    entre el chequeo y el INSERT, y lo que salta es la FK.

    Ese error no puede terminar en "ya tenes un reporte pendiente", que ademas
    de ser mentira taparia el problema real sin dejar rastro.
    """
    from app.blog import vistas

    autor = crear_usuario(username="autor")
    denunciante = crear_usuario(username="denunciante")
    post = crear_post(autor.id)
    post_id = post.id

    def _borrar_el_post_en_el_medio(reporter_id, tipo, target_id):
        db.session.execute(db.text("DELETE FROM posts WHERE id = :id"), {"id": post_id})
        return False

    monkeypatch.setattr(
        vistas.consultas, "hay_reporte_pendiente", _borrar_el_post_en_el_medio
    )

    login(denunciante.id)
    with pytest.raises(IntegrityError):
        client.post(f"/blog/reportar/post/{post_id}", data={"reason": "Contenido falso"})

    db.session.rollback()
    assert Report.query.count() == 0


def test_dos_reportes_simultaneos_dejan_uno_solo(tmp_path, monkeypatch):
    """La carrera de verdad, con dos hilos y una Barrier.

    Postear dos veces seguidas no prueba nada de esto: lo ataja el chequeo de
    la vista. El bug esta en la ventana entre ese SELECT y el INSERT, asi que
    la barrera se pone justo ahi, envolviendo hay_reporte_pendiente: los dos
    hilos ven "no hay ninguno pendiente" y recien despues insertan los dos.

    Va sobre una base en un archivo y no sobre la de memoria de conftest,
    porque en SQLite la base ":memory:" vive en una sola conexion y no hay dos
    requests concurrentes que valgan.
    """
    from app.blog import vistas
    from config import TestingConfig

    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{tmp_path / 'concurrencia.sqlite'}",
    )
    app = create_app("testing")

    with app.app_context():
        _db.create_all()
        autor = User(username="autor", email="autor@test.com", password="x")
        denunciante = User(
            username="denunciante", email="denunciante@test.com", password="x"
        )
        _db.session.add_all([autor, denunciante])
        _db.session.commit()
        post = Post(author=autor.id, title="Lo mio", body="Plomeria")
        _db.session.add(post)
        _db.session.commit()
        post_id, denunciante_id = post.id, denunciante.id

    barrera = threading.Barrier(2, timeout=10)
    chequeo_original = vistas.consultas.hay_reporte_pendiente
    # Solo se espera en el chequeo de la ida, que es el unico que corre por
    # request: el que pierde la carrera no vuelve a preguntar.
    ida = threading.local()

    def _chequear_y_esperar(reporter_id, tipo, target_id):
        pendiente = chequeo_original(reporter_id, tipo, target_id)
        if not getattr(ida, "cumplida", False):
            ida.cumplida = True
            # Los dos hilos ya hicieron el SELECT; salen juntos a insertar.
            barrera.wait()
        return pendiente

    monkeypatch.setattr(vistas.consultas, "hay_reporte_pendiente", _chequear_y_esperar)

    respuestas = {}
    fallas = {}

    def reportar(numero):
        try:
            navegador = app.test_client()
            with navegador.session_transaction() as sesion:
                sesion["user_id"] = denunciante_id
            respuestas[numero] = navegador.post(
                f"/blog/reportar/post/{post_id}",
                data={"reason": f"Contenido falso ({numero})"},
            )
        except Exception as e:  # noqa: BLE001 - se reporta abajo, en el assert
            fallas[numero] = e

    hilos = [threading.Thread(target=reportar, args=(numero,)) for numero in (1, 2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert not fallas, f"algun request exploto: {fallas}"
    # Ninguno de los dos ve un error: el que pierde la carrera termina en el
    # detalle del post, igual que si hubiera llegado un rato despues.
    assert [r.status_code for r in respuestas.values()] == [302, 302]

    with app.app_context():
        assert Report.query.filter_by(
            reporter_id=denunciante_id, post_id=post_id, resolved=False
        ).count() == 1
        _db.session.remove()
        _db.engine.dispose()
