"""Tests de reportes de contenido inapropiado y su integracion con el panel de admin."""

from models.report import Report
from models.review import Review
from models.user import Roles


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
    assert "/auth/login" in resp.headers["Location"]


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
