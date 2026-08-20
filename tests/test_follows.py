"""Tests del sistema de seguir emprendedores."""

from app.perfil.modelo_follow import Follow
from models.user import User


def _seguir(client, slug, seguir_redirect=False):
    """seguir_redirect=True imita al navegador, que sigue el redirect y con eso
    consume el flash ("Ahora seguís a X"). Sin eso el aviso queda encolado en la
    sesion y lo termina mostrando la proxima pagina que renderice flashes, que
    no es donde corresponde."""
    return client.post(f"/perfil/{slug}/seguir", follow_redirects=seguir_redirect)


# ------------------------------------------------------------------- toggle

def test_seguir_a_un_emprendedor(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)

    _seguir(client, emprendedor.slug)

    assert Follow.query.filter_by(
        follower_id=seguidor.id, followed_id=emprendedor.id
    ).count() == 1


def test_seguir_dos_veces_deja_de_seguir(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)

    _seguir(client, emprendedor.slug)
    _seguir(client, emprendedor.slug)

    assert Follow.query.count() == 0


def test_no_te_podes_seguir_a_vos_mismo(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    _seguir(client, usuario.slug)

    assert Follow.query.count() == 0


def test_seguir_requiere_estar_logueado(client, crear_usuario):
    emprendedor = crear_usuario(username="panaderia")

    respuesta = _seguir(client, emprendedor.slug)

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]
    assert Follow.query.count() == 0


def test_seguir_a_un_slug_inexistente_da_404(client, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    assert _seguir(client, "no-existe").status_code == 404


def test_la_base_rechaza_seguirse_a_si_mismo(db, crear_usuario):
    """La regla vive tambien en la base, no solo en la vista."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    usuario = crear_usuario(username="tomy")

    db.session.add(Follow(follower_id=usuario.id, followed_id=usuario.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_no_se_puede_seguir_dos_veces_a_la_misma_persona(db, crear_usuario):
    import pytest
    from sqlalchemy.exc import IntegrityError

    seguidor = crear_usuario(username="seguidor")
    seguido = crear_usuario(username="seguido")

    db.session.add(Follow(follower_id=seguidor.id, followed_id=seguido.id))
    db.session.commit()
    db.session.add(Follow(follower_id=seguidor.id, followed_id=seguido.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# -------------------------------------------------------------------- vistas

def test_el_boton_dice_seguir_y_despues_dejar_de_seguir(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)

    html = client.get(f"/perfil/{emprendedor.slug}").get_data(as_text=True)
    assert 'aria-pressed="false"' in html
    assert "Dejar de seguir" not in html

    _seguir(client, emprendedor.slug)
    html = client.get(f"/perfil/{emprendedor.slug}").get_data(as_text=True)
    assert "Dejar de seguir" in html


def test_el_perfil_propio_no_muestra_el_boton_de_seguir(client, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    html = client.get(f"/perfil/{usuario.slug}").get_data(as_text=True)

    assert "/seguir" not in html


def test_el_dueño_ve_su_lista_de_sigo_a(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)
    _seguir(client, emprendedor.slug)

    html = client.get(f"/perfil/{seguidor.slug}").get_data(as_text=True)

    assert "Sigo a" in html
    assert "panaderia" in html


# ------------------------------------------------------------------ privacidad

def test_un_visitante_no_ve_la_lista_sigo_a_de_otro(client, db, crear_usuario, login):
    """Mismo criterio que views_count: a quien sigue alguien es dato suyo."""
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    curioso = crear_usuario(username="curioso")
    login(seguidor.id)
    # Sigue el redirect para que el flash se consuma en el perfil del seguido,
    # que es a donde lo mandaria el navegador: si no, el aviso viaja encolado
    # hasta el proximo render y este test lo confundiria con una filtracion.
    _seguir(client, emprendedor.slug, seguir_redirect=True)

    login(curioso.id)
    html = client.get(f"/perfil/{seguidor.slug}").get_data(as_text=True)

    assert "Sigo a" not in html
    assert "panaderia" not in html


def test_la_cantidad_de_seguidores_no_se_expone_a_terceros(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)
    _seguir(client, emprendedor.slug)

    html = client.get(f"/perfil/{emprendedor.slug}").get_data(as_text=True)

    assert "Seguidor" not in html


def test_el_dueño_si_ve_su_cantidad_de_seguidores(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)
    _seguir(client, emprendedor.slug)

    login(emprendedor.id)
    html = client.get(f"/perfil/{emprendedor.slug}").get_data(as_text=True)

    assert "Seguidor" in html
    assert ">1<" in html.replace(" ", "").replace("\n", "")
    # Tampoco al dueño se le dice QUIEN lo sigue, solo cuantos: el username del
    # seguidor no aparece en ningun lado del perfil.
    assert "seguidor" not in html


def test_la_api_publica_no_expone_los_seguimientos(client, db, crear_usuario, login):
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)
    _seguir(client, emprendedor.slug)

    datos = User.query.get(emprendedor.id).serialize()

    assert "seguidores" not in datos
    assert "followers" not in datos


# ------------------------------------------------------------------- cascade

def test_borrar_un_usuario_borra_sus_seguimientos(client, db, crear_usuario, login):
    """FK con ondelete CASCADE en las dos puntas."""
    seguidor = crear_usuario(username="seguidor")
    emprendedor = crear_usuario(username="panaderia")
    login(seguidor.id)
    _seguir(client, emprendedor.slug)

    db.session.delete(emprendedor)
    db.session.commit()

    assert Follow.query.count() == 0
