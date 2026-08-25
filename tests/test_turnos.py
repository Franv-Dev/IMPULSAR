"""Tests del corte de slots reservables y del freno a la doble reserva.

La tanda 2a no tiene vistas todavia, asi que aca no hay ni un client.get: se le
pega directo a las funciones. Los del corte puro (cortar_en_slots) no tocan la
base; los de slots_disponibles si, porque su trabajo es justamente juntar el
servicio, el horario del dueño y los turnos ya tomados.
"""

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.turnos import consultas as consultas_turnos
from app.turnos.consultas import horas_tomadas, slots_disponibles
from app.turnos.modelo_turno import EstadosTurno, QuienCancela, Turno
from app.turnos.reglas import cortar_en_slots, es_slot_duplicado, fin_de_turno
from services.eventos import hoy_en_argentina
from services.horarios import ZONA_ARGENTINA

# 2026-09-14 fue lunes (weekday() == 0) y 2026-09-15 martes. Se usan fechas
# fijas y no "hoy" para que los tests no cambien de dia de la semana solos.
LUNES = date(2026, 9, 14)
MARTES = date(2026, 9, 15)


# ------------------------------------------------- el corte puro, sin la base

def test_un_rango_que_divide_exacto_se_corta_entero():
    slots = cortar_en_slots(time(9, 0), time(11, 0), 30)

    assert slots == [
        (time(9, 0), time(9, 30)),
        (time(9, 30), time(10, 0)),
        (time(10, 0), time(10, 30)),
        (time(10, 30), time(11, 0)),
    ]


def test_el_ultimo_slot_puede_terminar_justo_a_la_hora_de_cierre():
    slots = cortar_en_slots(time(9, 0), time(10, 0), 60)

    assert slots == [(time(9, 0), time(10, 0))]


def test_el_sobrante_que_no_entra_se_descarta():
    # 9:00 a 13:00 son 240 minutos; en tramos de 50 entran 4 y sobran 40. El
    # quinto arrancaria 12:20 y terminaria 13:10, con el local ya cerrado.
    slots = cortar_en_slots(time(9, 0), time(13, 0), 50)

    assert len(slots) == 4
    assert slots[-1] == (time(11, 30), time(12, 20))
    # Los 40 minutos entre el ultimo cierre y el del local no se ofrecen.
    assert (time(12, 20), time(13, 10)) not in slots
    # Lo que importa del descarte: ningun slot se pasa del cierre.
    assert all(fin <= time(13, 0) for _, fin in slots)


def test_una_duracion_mas_larga_que_el_rango_no_genera_ningun_slot():
    assert cortar_en_slots(time(9, 0), time(10, 0), 90) == []


def test_un_rango_que_cruza_medianoche_no_genera_slots():
    # Un bar de 20:00 a 02:00. Excluido de v1 a proposito: lo importante es que
    # devuelva vacio y no que reviente ni que invente un rango al reves.
    assert cortar_en_slots(time(20, 0), time(2, 0), 30) == []


def test_abre_igual_a_cierra_tampoco_genera_slots():
    assert cortar_en_slots(time(9, 0), time(9, 0), 30) == []


@pytest.mark.parametrize("abre, cierra, duracion", [
    (None, time(18, 0), 30),
    (time(9, 0), None, 30),
    (time(9, 0), time(18, 0), None),
    (time(9, 0), time(18, 0), 0),
    (time(9, 0), time(18, 0), -30),
])
def test_los_datos_incompletos_o_absurdos_devuelven_vacio(abre, cierra, duracion):
    assert cortar_en_slots(abre, cierra, duracion) == []


def test_fin_de_turno_congela_el_rango():
    assert fin_de_turno(time(15, 0), 45) == time(15, 45)
    assert fin_de_turno(time(23, 30), 30) is None  # se pasaria de medianoche


# ------------------------------------------------------------------- fixtures

@pytest.fixture
def servicio_con_turnos(db, crear_usuario, crear_post):
    """Un servicio que toma turnos de 30 minutos, con su dueño abierto el lunes.

    Devuelve (servicio, dueño, cliente) para que cada test toque lo que necesite.
    """

    def _crear(duracion=30, turnos_habilitados=True, dia=0,
               abre=time(9, 0), cierra=time(11, 0), cerrado=False):
        dueño = crear_usuario(username="vendedora")
        cliente = crear_usuario(username="clienta")
        post = crear_post(dueño.id, title="Peluquería")

        db.session.add(Horario(
            user_id=dueño.id, dia_semana=dia,
            abre=abre, cierra=cierra, cerrado=cerrado,
        ))
        servicio = Service(
            post_id=post.id, titulo="Corte", rubro="otros",
            turnos_habilitados=turnos_habilitados,
            duracion_turno_minutos=duracion,
        )
        db.session.add(servicio)
        db.session.commit()
        return servicio, dueño, cliente

    return _crear


def _reservar(db, servicio, cliente, fecha, hora_inicio, hora_fin,
              estado=EstadosTurno.ACTIVO):
    turno = Turno(
        service_id=servicio.id, cliente_id=cliente.id, fecha=fecha,
        hora_inicio=hora_inicio, hora_fin=hora_fin, estado=estado,
    )
    db.session.add(turno)
    db.session.commit()
    return turno


# ------------------------------------------- slots disponibles, contra la base

def test_un_dia_con_horario_normal_ofrece_toda_la_grilla(db, servicio_con_turnos):
    servicio, _, _ = servicio_con_turnos()

    assert slots_disponibles(servicio, LUNES) == [
        (time(9, 0), time(9, 30)),
        (time(9, 30), time(10, 0)),
        (time(10, 0), time(10, 30)),
        (time(10, 30), time(11, 0)),
    ]


def test_un_dia_sin_horario_cargado_no_ofrece_nada(db, servicio_con_turnos):
    # El horario se carga para el lunes; el martes no existe.
    servicio, _, _ = servicio_con_turnos()

    assert slots_disponibles(servicio, MARTES) == []


def test_un_dia_marcado_cerrado_no_ofrece_nada(db, servicio_con_turnos):
    servicio, _, _ = servicio_con_turnos(cerrado=True)

    assert slots_disponibles(servicio, LUNES) == []


def test_un_dia_con_horario_que_cruza_medianoche_no_ofrece_nada(db, servicio_con_turnos):
    servicio, _, _ = servicio_con_turnos(abre=time(20, 0), cierra=time(2, 0))

    assert slots_disponibles(servicio, LUNES) == []


def test_un_servicio_sin_turnos_habilitados_no_ofrece_nada(db, servicio_con_turnos):
    # El horario esta, la duracion esta, pero el vendedor no habilito turnos.
    servicio, _, _ = servicio_con_turnos(turnos_habilitados=False)

    assert slots_disponibles(servicio, LUNES) == []


def test_un_servicio_habilitado_pero_sin_duracion_no_ofrece_nada(db, servicio_con_turnos):
    # Combinacion que el formulario no deja guardar, pero que una fila vieja o
    # tocada a mano si puede tener: tiene que descartarse, no romperse.
    servicio, _, _ = servicio_con_turnos(duracion=None)

    assert slots_disponibles(servicio, LUNES) == []


def test_un_slot_ya_reservado_no_se_vuelve_a_ofrecer(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 30), time(10, 0))

    slots = slots_disponibles(servicio, LUNES)

    assert (time(9, 30), time(10, 0)) not in slots
    assert slots == [
        (time(9, 0), time(9, 30)),
        (time(10, 0), time(10, 30)),
        (time(10, 30), time(11, 0)),
    ]


def test_un_turno_cancelado_devuelve_el_slot_a_la_grilla(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    turno = _reservar(db, servicio, cliente, LUNES, time(9, 30), time(10, 0))

    turno.estado = EstadosTurno.CANCELADO
    turno.cancelado_por = QuienCancela.CLIENTE
    db.session.commit()

    assert (time(9, 30), time(10, 0)) in slots_disponibles(servicio, LUNES)


def test_una_reserva_solo_ocupa_su_propio_dia(db, servicio_con_turnos):
    # El horario del lunes vale para todos los lunes; una reserva de un lunes
    # puntual no puede tapar el slot del lunes siguiente.
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    otro_lunes = date(2026, 9, 21)

    assert (time(9, 0), time(9, 30)) not in slots_disponibles(servicio, LUNES)
    assert (time(9, 0), time(9, 30)) in slots_disponibles(servicio, otro_lunes)


def test_con_todos_los_slots_tomados_devuelve_vacio(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    for inicio, fin in cortar_en_slots(time(9, 0), time(11, 0), 30):
        _reservar(db, servicio, cliente, LUNES, inicio, fin)

    assert slots_disponibles(servicio, LUNES) == []


def test_horas_tomadas_ignora_los_cancelados(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))
    _reservar(db, servicio, cliente, LUNES, time(10, 0), time(10, 30),
              estado=EstadosTurno.CANCELADO)

    assert horas_tomadas(servicio.id, LUNES) == {time(9, 0)}


# -------------------------------------------------- la doble reserva, en la base

def test_la_base_rechaza_dos_turnos_activos_en_el_mismo_slot(db, servicio_con_turnos):
    """El freno de verdad: no la vista, la constraint.

    Es el caso de los dos clientes que entran juntos al ultimo slot del viernes:
    los dos pasan el chequeo de "esta libre?" y los dos intentan insertar.
    """
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    otro = Turno(
        service_id=servicio.id, cliente_id=cliente.id, fecha=LUNES,
        hora_inicio=time(9, 0), hora_fin=time(9, 30),
    )
    db.session.add(otro)

    with pytest.raises(IntegrityError) as choque:
        db.session.commit()

    assert es_slot_duplicado(choque.value)
    db.session.rollback()


def test_cancelar_libera_el_slot_para_la_base(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    turno = _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    turno.estado = EstadosTurno.CANCELADO
    turno.cancelado_por = QuienCancela.VENDEDOR
    db.session.commit()

    # El mismo slot se vuelve a poder reservar, y el UNIQUE no se queja: el
    # cancelado tiene cupo_activo en NULL y los dos motores lo eximen.
    nuevo = _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    assert nuevo.id != turno.id
    assert nuevo.cupo_activo == 1
    assert turno.cupo_activo is None


def test_el_listener_deriva_cupo_activo_del_estado(db, servicio_con_turnos):
    """cupo_activo no se escribe a mano en ningun lado: sale de `estado`."""
    servicio, _, cliente = servicio_con_turnos()

    turno = Turno(
        service_id=servicio.id, cliente_id=cliente.id, fecha=LUNES,
        hora_inicio=time(9, 0), hora_fin=time(9, 30),
    )
    db.session.add(turno)
    db.session.commit()

    # Creado sin pasar estado: el listener lo deja en activo y prende el cupo.
    assert turno.estado == EstadosTurno.ACTIVO
    assert turno.cupo_activo == 1

    turno.estado = EstadosTurno.CANCELADO
    db.session.commit()
    assert turno.cupo_activo is None

    turno.estado = EstadosTurno.ACTIVO
    db.session.commit()
    assert turno.cupo_activo == 1


def test_es_slot_duplicado_no_se_come_cualquier_integrityerror(db, servicio_con_turnos):
    """Una FK rota no puede disfrazarse de "ese horario ya esta tomado"."""
    servicio, _, _ = servicio_con_turnos()

    huerfano = Turno(
        service_id=servicio.id, cliente_id=99999, fecha=LUNES,
        hora_inicio=time(9, 0), hora_fin=time(9, 30),
    )
    db.session.add(huerfano)

    with pytest.raises(IntegrityError) as choque:
        db.session.commit()

    assert not es_slot_duplicado(choque.value)
    db.session.rollback()


def test_borrar_el_servicio_se_lleva_sus_turnos(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    db.session.delete(servicio)
    db.session.commit()

    assert Turno.query.count() == 0


def test_borrar_el_cliente_se_lleva_sus_turnos(db, servicio_con_turnos):
    servicio, _, cliente = servicio_con_turnos()
    _reservar(db, servicio, cliente, LUNES, time(9, 0), time(9, 30))

    db.session.delete(cliente)
    db.session.commit()

    assert Turno.query.count() == 0


# ------------------------------- el formulario de Service: habilitar turnos

@pytest.fixture
def emprendedor(crear_usuario, crear_post, login):
    """Un usuario logueado con un emprendimiento propio, para el form de Service."""

    def _crear(username="duenio"):
        usuario = crear_usuario(username=username)
        post = crear_post(usuario.id)
        login(usuario.id)
        return usuario, post

    return _crear


def _alta(post_id, **extra):
    datos = {
        "post_id": post_id, "titulo": "Corte", "rubro": "otros",
        "precio_estimado": "", "disponible": "on",
    }
    datos.update(extra)
    return datos


def test_habilitar_turnos_guarda_el_flag_y_la_duracion(client, emprendedor):
    _usuario, post = emprendedor()

    respuesta = client.post("/servicios/nuevo", data=_alta(
        post.id, turnos_habilitados="on", duracion_turno_minutos="30"))

    assert respuesta.status_code == 302
    servicio = Service.query.one()
    assert servicio.turnos_habilitados is True
    assert servicio.duracion_turno_minutos == 30


def test_sin_tildar_turnos_la_duracion_queda_en_null(client, emprendedor):
    """Aunque el campo venga escrito: con el flag apagado la columna no significa nada."""
    _usuario, post = emprendedor()

    respuesta = client.post("/servicios/nuevo", data=_alta(
        post.id, duracion_turno_minutos="30"))

    assert respuesta.status_code == 302
    servicio = Service.query.one()
    assert servicio.turnos_habilitados is False
    assert servicio.duracion_turno_minutos is None


@pytest.mark.parametrize("duracion", ["", "4", "481", "0", "-30"])
def test_con_turnos_tildados_la_duracion_es_obligatoria_y_acotada(
    client, emprendedor, duracion
):
    _usuario, post = emprendedor()

    respuesta = client.post("/servicios/nuevo", data=_alta(
        post.id, turnos_habilitados="on", duracion_turno_minutos=duracion))

    # Se repinta el formulario en vez de guardar: no hay redirect ni fila.
    assert respuesta.status_code == 200
    assert Service.query.count() == 0


def test_una_duracion_que_no_es_un_numero_lo_dice(client, emprendedor):
    _usuario, post = emprendedor()

    respuesta = client.post("/servicios/nuevo", data=_alta(
        post.id, turnos_habilitados="on", duracion_turno_minutos="media hora"))

    assert respuesta.status_code == 200
    assert "número de minutos" in respuesta.get_data(as_text=True)
    assert Service.query.count() == 0


@pytest.mark.parametrize("duracion", ["5", "480"])
def test_los_dos_bordes_del_rango_se_aceptan(client, emprendedor, duracion):
    _usuario, post = emprendedor()

    respuesta = client.post("/servicios/nuevo", data=_alta(
        post.id, turnos_habilitados="on", duracion_turno_minutos=duracion))

    assert respuesta.status_code == 302
    assert Service.query.one().duracion_turno_minutos == int(duracion)


def test_apagar_los_turnos_al_editar_borra_la_duracion(client, db, emprendedor):
    """Volver a prender los turnos no tiene que revivir una duracion vieja."""
    _usuario, post = emprendedor()
    servicio = Service(post_id=post.id, titulo="Corte", rubro="otros",
                       turnos_habilitados=True, duracion_turno_minutos=30)
    db.session.add(servicio)
    db.session.commit()

    respuesta = client.post(f"/servicios/{servicio.id}/editar", data=_alta(post.id))

    assert respuesta.status_code == 302
    assert servicio.turnos_habilitados is False
    assert servicio.duracion_turno_minutos is None


def test_el_formulario_muestra_los_campos_de_turnos(client, emprendedor):
    _usuario, _post = emprendedor()

    pagina = client.get("/servicios/nuevo").get_data(as_text=True)

    assert 'name="turnos_habilitados"' in pagina
    assert 'name="duracion_turno_minutos"' in pagina
    # El rango sale de reglas.py y no de numeros escritos en el HTML.
    assert 'min="5"' in pagina and 'max="480"' in pagina


# =========================================================== las vistas (2b)

def _proximo_lunes():
    """Un lunes estrictamente futuro, para que el filtro de "ya pasó" no moleste.

    Calculado y no fijo: una fecha escrita a mano deja de ser futura el dia que
    llega, y el test empieza a fallar solo sin que nadie haya tocado nada.
    """
    hoy = hoy_en_argentina()
    return hoy + timedelta(days=(7 - hoy.weekday()) % 7 or 7)


@pytest.fixture
def escenario(db, crear_usuario, crear_post, login):
    """Vendedor con un servicio que toma turnos, y un cliente logueado.

    El cliente queda logueado porque es quien reserva; los tests del vendedor
    cambian la sesion con la fixture login.
    """

    class Escenario:
        pass

    def _crear(duracion=30, abre=time(9, 0), cierra=time(11, 0), dia=0):
        e = Escenario()
        e.vendedor = crear_usuario(username="vendedora")
        e.cliente = crear_usuario(username="clienta")
        e.post = crear_post(e.vendedor.id, title="Peluquería")
        db.session.add(Horario(user_id=e.vendedor.id, dia_semana=dia,
                               abre=abre, cierra=cierra, cerrado=False))
        e.servicio = Service(
            post_id=e.post.id, titulo="Corte", rubro="otros",
            turnos_habilitados=True, duracion_turno_minutos=duracion,
        )
        db.session.add(e.servicio)
        db.session.commit()
        e.fecha = _proximo_lunes()
        login(e.cliente.id)
        return e

    return _crear


def _pedir(client, servicio_id, fecha, hora="09:00"):
    return client.post(f"/turnos/servicio/{servicio_id}",
                       data={"fecha": fecha.isoformat(), "hora_inicio": hora})


# ------------------------------------------------------------------- reservar

def test_la_pantalla_muestra_los_slots_libres(client, escenario):
    e = escenario()

    pagina = client.get(
        f"/turnos/servicio/{e.servicio.id}?fecha={e.fecha.isoformat()}"
    ).get_data(as_text=True)

    for hora in ("09:00", "09:30", "10:00", "10:30"):
        assert hora in pagina


def test_reservar_un_slot_crea_el_turno(client, escenario):
    e = escenario()

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:30")

    assert respuesta.status_code == 302
    turno = Turno.query.one()
    assert turno.cliente_id == e.cliente.id
    assert turno.service_id == e.servicio.id
    assert turno.fecha == e.fecha
    assert turno.hora_inicio == time(9, 30)
    # hora_fin se congela con la duracion del servicio al momento de reservar.
    assert turno.hora_fin == time(10, 0)
    assert turno.estado == EstadosTurno.ACTIVO
    assert turno.cupo_activo == 1


def test_un_slot_reservado_desaparece_de_la_pantalla(client, escenario):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:30")

    pagina = client.get(
        f"/turnos/servicio/{e.servicio.id}?fecha={e.fecha.isoformat()}"
    ).get_data(as_text=True)

    assert 'value="09:30"' not in pagina
    assert 'value="10:00"' in pagina


def test_no_se_puede_reservar_un_horario_que_no_estaba_en_la_lista(client, escenario):
    """El POST se manda a mano: sin este chequeo se reserva a cualquier hora."""
    e = escenario()

    respuesta = _pedir(client, e.servicio.id, e.fecha, "03:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_no_se_puede_reservar_un_dia_cerrado(client, escenario):
    e = escenario()
    martes = e.fecha + timedelta(days=1)

    respuesta = _pedir(client, e.servicio.id, martes, "09:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_no_se_puede_reservar_una_fecha_pasada(client, escenario):
    e = escenario()
    lunes_pasado = e.fecha - timedelta(days=14)

    respuesta = _pedir(client, e.servicio.id, lunes_pasado, "09:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_los_slots_de_hoy_que_ya_pasaron_no_se_ofrecen(client, db, escenario, monkeypatch):
    """El filtro del pasado vive en la vista, con la hora inyectada."""
    e = escenario()
    hoy = hoy_en_argentina()
    # El horario se recarga para el dia de la semana que sea hoy.
    Horario.query.filter_by(user_id=e.vendedor.id).delete()
    db.session.add(Horario(user_id=e.vendedor.id, dia_semana=hoy.weekday(),
                           abre=time(9, 0), cierra=time(11, 0), cerrado=False))
    db.session.commit()

    monkeypatch.setattr(
        "app.turnos.vistas.ahora_en_argentina",
        lambda: datetime.combine(hoy, time(9, 45), tzinfo=ZONA_ARGENTINA),
    )

    pagina = client.get(
        f"/turnos/servicio/{e.servicio.id}?fecha={hoy.isoformat()}"
    ).get_data(as_text=True)

    assert 'value="09:00"' not in pagina
    assert 'value="09:30"' not in pagina
    assert 'value="10:00"' in pagina
    assert 'value="10:30"' in pagina


def test_el_dueno_no_se_saca_turno_a_si_mismo(client, escenario, login):
    e = escenario()
    login(e.vendedor.id)

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_un_servicio_que_no_toma_turnos_no_se_reserva(client, db, escenario):
    e = escenario()
    e.servicio.turnos_habilitados = False
    db.session.commit()

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_un_servicio_apagado_no_se_reserva(client, db, escenario):
    e = escenario()
    e.servicio.disponible = False
    db.session.commit()

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert respuesta.status_code == 302
    assert Turno.query.count() == 0


def test_reservar_pide_sesion(client, escenario):
    e = escenario()
    with client.session_transaction() as sesion:
        sesion.clear()

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert respuesta.status_code == 302
    assert "login" in respuesta.headers["Location"]
    assert Turno.query.count() == 0


# ------------------------------------------- solapamiento entre dos servicios

def _con_color(db, e, inicio=time(9, 0), fin=time(10, 30),
               estado=EstadosTurno.ACTIVO, dueno_post=None):
    """Un segundo servicio del mismo vendedor, con un turno ya tomado."""
    color = Service(post_id=(dueno_post or e.post).id, titulo="Color",
                    rubro="otros", turnos_habilitados=True,
                    duracion_turno_minutos=90)
    db.session.add(color)
    db.session.commit()
    db.session.add(Turno(
        service_id=color.id, cliente_id=e.cliente.id, fecha=e.fecha,
        hora_inicio=inicio, hora_fin=fin, estado=estado,
    ))
    db.session.commit()
    return color


def test_no_se_puede_reservar_pisando_otro_turno_del_mismo_vendedor(
    client, db, escenario
):
    """Lo que el UNIQUE de la base NO cubre: dos servicios distintos del vendedor.

    "Corte" dura 30 minutos y "Color" 90. Con Color tomado de 9:00 a 10:30, el
    slot de Corte de las 9:30 se pisa con el, aunque sea otro service_id y por
    lo tanto otra fila para el UNIQUE.
    """
    e = escenario()
    _con_color(db, e)

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:30")

    assert respuesta.status_code == 302
    assert Turno.query.filter_by(service_id=e.servicio.id).count() == 0


def test_un_turno_pegado_al_anterior_si_se_puede_reservar(client, db, escenario):
    """El borde no es choque: 9:00-10:30 y 10:30-11:00 se tocan, no se pisan."""
    e = escenario()
    _con_color(db, e)

    respuesta = _pedir(client, e.servicio.id, e.fecha, "10:30")

    assert respuesta.status_code == 302
    assert Turno.query.filter_by(service_id=e.servicio.id).count() == 1


def test_el_solapamiento_no_mira_los_turnos_de_otro_vendedor(
    client, db, escenario, crear_usuario, crear_post
):
    e = escenario()
    otro = crear_usuario(username="otrovendedor")
    otro_post = crear_post(otro.id, title="Otra")
    _con_color(db, e, dueno_post=otro_post)

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:30")

    assert respuesta.status_code == 302
    assert Turno.query.filter_by(service_id=e.servicio.id).count() == 1


def test_un_turno_cancelado_no_bloquea_por_solapamiento(client, db, escenario):
    e = escenario()
    _con_color(db, e, estado=EstadosTurno.CANCELADO)

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:30")

    assert respuesta.status_code == 302
    assert Turno.query.filter_by(service_id=e.servicio.id).count() == 1


# ------------------------------------------------ la carrera por el mismo slot

def test_si_otro_agarra_el_slot_en_el_medio_la_base_lo_frena(
    client, db, escenario, monkeypatch
):
    """Reproduce la carrera entre el SELECT y el INSERT.

    Los dos requests leen "el slot está libre" y los dos intentan insertar. El
    que llega segundo choca contra el UNIQUE, y la vista lo traduce a un mensaje
    en vez de reventar con un 500.

    Se simula parchando los dos puntos de lectura de la vista: slots_disponibles
    mete al competidor DESPUES de calcular (o sea, el que reserva vio la lista
    vieja) y rangos_ocupados_del_vendedor devuelve vacio, que es lo que habria
    leido antes de que el otro commiteara.
    """
    e = escenario()
    real = consultas_turnos.slots_disponibles

    def slots_y_competidor(servicio, fecha):
        libres = real(servicio, fecha)
        if not Turno.query.filter_by(hora_inicio=time(9, 0)).count():
            db.session.add(Turno(
                service_id=servicio.id, cliente_id=e.vendedor.id, fecha=fecha,
                hora_inicio=time(9, 0), hora_fin=time(9, 30),
            ))
            db.session.commit()
        return libres

    monkeypatch.setattr("app.turnos.vistas.slots_disponibles", slots_y_competidor)
    monkeypatch.setattr(
        "app.turnos.vistas.rangos_ocupados_del_vendedor", lambda *a, **k: [])

    respuesta = _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert respuesta.status_code == 302
    # Quedo el del competidor y nada mas: el segundo INSERT lo rechazo la base.
    assert Turno.query.filter_by(hora_inicio=time(9, 0)).count() == 1
    assert Turno.query.filter_by(cliente_id=e.cliente.id).count() == 0


def test_un_integrityerror_que_no_es_el_del_slot_no_se_disfraza(
    client, escenario, monkeypatch
):
    """Una FK rota no puede salir como "ese horario lo tomó otra persona".

    Se fabrica el IntegrityError en vez de romper una FK de verdad (borrando el
    cliente o el servicio en el medio): cualquiera de esas dos cosas deja la
    sesion de SQLAlchemy con objetos borrados y el request muere antes de
    llegar al INSERT, con lo cual el test probaria otra cosa. Lo que importa
    aca es la rama: si el choque no es el del slot, sube tal cual.
    """
    e = escenario()

    def choque_ajeno(fila=None):
        raise IntegrityError(
            "INSERT INTO turnos ...", {},
            Exception("FOREIGN KEY constraint failed"),
        )

    monkeypatch.setattr("app.turnos.consultas.guardar", choque_ajeno)

    with pytest.raises(IntegrityError):
        _pedir(client, e.servicio.id, e.fecha, "09:00")

    assert Turno.query.count() == 0


# ------------------------------------------------------------------- cancelar

def test_el_cliente_cancela_su_turno(client, escenario):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()

    respuesta = client.post(f"/turnos/{turno.id}/cancelar")

    assert respuesta.status_code == 302
    assert turno.estado == EstadosTurno.CANCELADO
    assert turno.cancelado_por == QuienCancela.CLIENTE
    assert turno.cupo_activo is None


def test_el_vendedor_cancela_un_turno_que_recibio(client, escenario, login):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()
    login(e.vendedor.id)

    respuesta = client.post(f"/turnos/{turno.id}/cancelar")

    assert respuesta.status_code == 302
    assert turno.estado == EstadosTurno.CANCELADO
    assert turno.cancelado_por == QuienCancela.VENDEDOR


def test_un_tercero_no_puede_cancelar_un_turno_ajeno(
    client, escenario, crear_usuario, login
):
    """El chequeo pasa en la vista, no en el template: el POST se manda a mano."""
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/turnos/{turno.id}/cancelar")

    assert respuesta.status_code == 302
    assert turno.estado == EstadosTurno.ACTIVO
    assert turno.cancelado_por is None


def test_cancelar_dos_veces_no_pisa_quien_cancelo(client, escenario, login):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()
    client.post(f"/turnos/{turno.id}/cancelar")

    login(e.vendedor.id)
    respuesta = client.post(f"/turnos/{turno.id}/cancelar")

    assert respuesta.status_code == 302
    # Sigue diciendo que lo cancelo el cliente, que es quien lo cancelo.
    assert turno.cancelado_por == QuienCancela.CLIENTE


def test_cancelar_libera_el_slot_en_la_pantalla(client, escenario):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()
    client.post(f"/turnos/{turno.id}/cancelar")

    pagina = client.get(
        f"/turnos/servicio/{e.servicio.id}?fecha={e.fecha.isoformat()}"
    ).get_data(as_text=True)

    assert 'value="09:00"' in pagina


def test_cancelar_solo_acepta_post(client, escenario):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()

    assert client.get(f"/turnos/{turno.id}/cancelar").status_code == 405


# -------------------------------------------------------------------- listados

def test_mis_turnos_muestra_los_propios(client, escenario):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")

    pagina = client.get("/turnos/mios").get_data(as_text=True)

    assert "Corte" in pagina
    assert "09:00" in pagina


def test_mis_turnos_no_muestra_los_de_otro_cliente(
    client, escenario, crear_usuario, login
):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    otro = crear_usuario(username="otrocliente")
    login(otro.id)

    pagina = client.get("/turnos/mios").get_data(as_text=True)

    assert "Todavía no reservaste" in pagina


def test_la_agenda_del_vendedor_muestra_lo_que_le_sacaron(client, escenario, login):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    login(e.vendedor.id)

    pagina = client.get("/turnos/agenda").get_data(as_text=True)

    assert "Corte" in pagina
    assert "clienta" in pagina


def test_la_agenda_no_muestra_turnos_de_otro_vendedor(
    client, escenario, crear_usuario, login
):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    ajeno = crear_usuario(username="ajeno")
    login(ajeno.id)

    pagina = client.get("/turnos/agenda").get_data(as_text=True)

    assert "Todavía no te sacaron" in pagina


def test_el_cliente_ve_quien_le_cancelo_el_turno(client, escenario, login):
    e = escenario()
    _pedir(client, e.servicio.id, e.fecha, "09:00")
    turno = Turno.query.one()
    login(e.vendedor.id)
    client.post(f"/turnos/{turno.id}/cancelar")

    login(e.cliente.id)
    pagina = client.get("/turnos/mios").get_data(as_text=True)

    assert "el prestador" in pagina


@pytest.mark.parametrize("ruta", ["/turnos/mios", "/turnos/agenda"])
def test_los_listados_piden_sesion(client, ruta):
    respuesta = client.get(ruta)

    assert respuesta.status_code == 302
    assert "login" in respuesta.headers["Location"]
