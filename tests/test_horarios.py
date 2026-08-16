"""Tests de horarios de atencion y del indicador "abierto ahora"."""

from datetime import datetime, time, timedelta, timezone

import pytest

from models.horario import Horario
from services.horarios import ZONA_ARGENTINA, esta_abierto, parsear_hora


def _horario(dia, abre="09:00", cierra="18:00", cerrado=False):
    return Horario(
        dia_semana=dia,
        abre=parsear_hora(abre) if abre else None,
        cierra=parsear_hora(cierra) if cierra else None,
        cerrado=cerrado,
    )


def _momento(dia_semana, hora, minuto=0):
    """Un datetime en hora argentina que caiga en ese dia de la semana."""
    # 2026-08-17 fue lunes (weekday() == 0).
    base = datetime(2026, 8, 17, hora, minuto, tzinfo=ZONA_ARGENTINA)
    return base + timedelta(days=dia_semana)


# ------------------------------------------------------------------ unitarios

def test_esta_abierto_dentro_del_rango():
    horarios = [_horario(0, "09:00", "18:00")]

    assert esta_abierto(horarios, _momento(0, 12)) is True


def test_esta_cerrado_fuera_del_rango():
    horarios = [_horario(0, "09:00", "18:00")]

    assert esta_abierto(horarios, _momento(0, 8)) is False
    assert esta_abierto(horarios, _momento(0, 19)) is False


def test_el_limite_de_apertura_cuenta_como_abierto():
    horarios = [_horario(0, "09:00", "18:00")]

    assert esta_abierto(horarios, _momento(0, 9, 0)) is True
    # A la hora exacta de cierre ya esta cerrado.
    assert esta_abierto(horarios, _momento(0, 18, 0)) is False


def test_un_dia_marcado_cerrado_no_abre():
    horarios = [_horario(0, "09:00", "18:00", cerrado=True)]

    assert esta_abierto(horarios, _momento(0, 12)) is False


def test_solo_cuenta_el_horario_del_dia_correspondiente():
    horarios = [_horario(0, "09:00", "18:00")]  # solo lunes

    assert esta_abierto(horarios, _momento(1, 12)) is False


def test_un_rango_que_cruza_medianoche_sigue_abierto_de_madrugada():
    """Un bar de 20:00 a 02:00: a la 01:00 del martes abre por el horario del
    lunes, no por el del martes."""
    horarios = [_horario(0, "20:00", "02:00")]  # lunes

    assert esta_abierto(horarios, _momento(0, 21)) is True    # lunes 21:00
    assert esta_abierto(horarios, _momento(1, 1)) is True     # martes 01:00
    assert esta_abierto(horarios, _momento(1, 3)) is False    # martes 03:00
    assert esta_abierto(horarios, _momento(0, 19)) is False   # lunes 19:00


def test_el_cruce_de_medianoche_funciona_del_domingo_al_lunes():
    horarios = [_horario(6, "22:00", "04:00")]  # domingo

    assert esta_abierto(horarios, _momento(0, 2)) is True  # lunes 02:00


def test_sin_horarios_no_esta_abierto():
    assert esta_abierto([]) is False


def test_se_usa_la_hora_de_argentina_y_no_utc():
    """A las 23:00 UTC ya son las 20:00 en Argentina: un negocio abierto hasta
    las 21:00 tiene que figurar abierto."""
    horarios = [_horario(0, "09:00", "21:00")]
    en_utc = datetime(2026, 8, 17, 23, 0, tzinfo=timezone.utc)

    assert en_utc.astimezone(ZONA_ARGENTINA).hour == 20
    assert esta_abierto(horarios, en_utc.astimezone(ZONA_ARGENTINA)) is True


@pytest.mark.parametrize("texto", ["", "  ", "25:00", "9:60", "nueve", None])
def test_parsear_hora_rechaza_lo_que_no_es_una_hora(texto):
    assert parsear_hora(texto) is None


def test_parsear_hora_acepta_el_formato_del_input_time():
    assert parsear_hora("09:30") == time(9, 30)


# --------------------------------------------------------------- integracion

def test_el_dueño_guarda_sus_horarios(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    datos = {"abre_0": "09:00", "cierra_0": "18:00", "cerrado_6": "on"}
    client.post("/perfil/horarios", data=datos)

    db.session.refresh(usuario)
    guardados = {h.dia_semana: h for h in usuario.horarios}
    assert guardados[0].abre == time(9, 0)
    assert guardados[0].cierra == time(18, 0)
    assert guardados[0].cerrado is False
    assert guardados[6].cerrado is True


def test_cargar_solo_una_de_las_dos_horas_es_un_error(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    respuesta = client.post("/perfil/horarios", data={"abre_0": "09:00"})

    db.session.refresh(usuario)
    assert respuesta.status_code == 200
    assert not [h for h in usuario.horarios if h.dia_semana == 0 and h.abre]


def test_guardar_los_horarios_dos_veces_no_duplica_filas(client, db, crear_usuario, login):
    usuario = crear_usuario(username="tomy")
    login(usuario.id)

    for hora in ("09:00", "10:00"):
        client.post("/perfil/horarios", data={"abre_0": hora, "cierra_0": "18:00"})

    db.session.refresh(usuario)
    del_lunes = [h for h in usuario.horarios if h.dia_semana == 0]
    assert len(del_lunes) == 1
    assert del_lunes[0].abre == time(10, 0)


def test_el_perfil_muestra_el_indicador_y_la_tabla(client, db, crear_usuario):
    usuario = crear_usuario(username="tomy")
    db.session.add(_horario_de(usuario.id, 0))
    db.session.commit()

    html = client.get("/perfil/tomy").get_data(as_text=True)

    assert "Horarios de atención" in html
    assert "09:00" in html
    # Uno de los dos estados tiene que estar, segun la hora real del test.
    # El indicador es el chip del hero del perfil (antes .estado-atencion).
    assert ("Abierto ahora" in html) or ("perfil-chip--cerrado" in html)


def test_un_perfil_sin_horarios_no_dice_cerrado(client, crear_usuario):
    """Sin horarios cargados, "Cerrado" seria mentira: no se muestra nada."""
    crear_usuario(username="tomy")

    html = client.get("/perfil/tomy").get_data(as_text=True)

    assert "perfil-chip--cerrado" not in html
    assert "Abierto ahora" not in html


def test_los_horarios_se_borran_con_el_usuario(client, db, crear_usuario):
    """FK con ondelete CASCADE, el bug que ya aparecio tres veces."""
    usuario = crear_usuario(username="tomy")
    db.session.add(_horario_de(usuario.id, 0))
    db.session.commit()
    user_id = usuario.id

    db.session.delete(usuario)
    db.session.commit()

    assert Horario.query.filter_by(user_id=user_id).count() == 0


def _horario_de(user_id, dia):
    horario = _horario(dia)
    horario.user_id = user_id
    return horario
