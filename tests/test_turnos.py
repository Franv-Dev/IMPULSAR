"""Tests del corte de slots reservables y del freno a la doble reserva.

La tanda 2a no tiene vistas todavia, asi que aca no hay ni un client.get: se le
pega directo a las funciones. Los del corte puro (cortar_en_slots) no tocan la
base; los de slots_disponibles si, porque su trabajo es justamente juntar el
servicio, el horario del dueño y los turnos ya tomados.
"""

from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError

from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.turnos.consultas import horas_tomadas, slots_disponibles
from app.turnos.modelo_turno import EstadosTurno, QuienCancela, Turno
from app.turnos.reglas import cortar_en_slots, es_slot_duplicado, fin_de_turno

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
