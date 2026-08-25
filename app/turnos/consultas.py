"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. La aritmetica de horas no esta aca: vive en
reglas.py, que es pura y se prueba sin sesion. Lo que hace este modulo es juntar
las tres cosas que hacen falta para saber que se puede reservar -- el servicio,
el horario de atencion de su dueño y los turnos ya tomados -- y pasarselas.

Va en app/turnos/ y no en services/ (donde estan horarios.py y eventos.py) por
la regla de app/__init__.py: en services/ vive lo que se comparte y no tiene
dueño posible (precios, uploads, slugs). Esto tiene dueño: es el calculo del
dominio de turnos, y de la unica cosa compartida que necesita -- como se lee un
Horario -- ya se ocupa services/horarios.py.
"""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.blog.modelo_post import Post
from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.servicios.reglas import acepta_turnos
from app.turnos.modelo_turno import EstadosTurno, Turno
from app.turnos.reglas import cortar_en_slots
from db import db
from models.user import User


def horario_del_dia(user_id, dia_semana):
    """El Horario de atencion de ese usuario para ese dia, si lo cargo.

    dia_semana en el criterio de datetime.weekday() (lunes = 0), que es el mismo
    que guarda la columna y el mismo que usa services.horarios.DIAS. Como el
    UNIQUE de horarios es (user_id, dia_semana), no puede devolver mas de uno.
    """
    return Horario.query.filter_by(user_id=user_id, dia_semana=dia_semana).first()


def horas_tomadas(service_id, fecha):
    """Las horas de inicio ya reservadas de ese servicio ese dia, como set.

    Solo los turnos activos: uno cancelado libera el slot, que es exactamente lo
    que hace la columna cupo_activo del lado de la base.

    Devuelve las horas y no las filas enteras porque es lo unico que se compara,
    y un set porque la comparacion se hace una vez por slot. Traer solo la
    columna ademas evita cargar el objeto entero de cada turno para mirarle un
    campo.
    """
    filas = (
        Turno.query
        .with_entities(Turno.hora_inicio)
        .filter(
            Turno.service_id == service_id,
            Turno.fecha == fecha,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .all()
    )
    return {fila[0] for fila in filas}


def slots_disponibles(servicio, fecha):
    """Los turnos que un cliente puede reservar en ese servicio y ese dia.

    Devuelve una lista de tuplas (hora_inicio, hora_fin), de la mas temprana a
    la mas tardia, ya sin los slots ocupados. Lista vacia cuando no hay nada que
    ofrecer, que es siempre un resultado valido y nunca un error:

    - el servicio no toma turnos, o los toma pero no tiene duracion cargada
      (ver servicios.reglas.acepta_turnos),
    - el dueño no cargo horario para ese dia de la semana,
    - ese dia esta marcado como cerrado,
    - el horario de ese dia cruza medianoche (excluido en v1, ver
      reglas.cortar_en_slots),
    - la duracion no entra ni una vez en el rango,
    - todos los slots del dia ya estan reservados.

    EL HORARIO SALE DEL DUEÑO DEL EMPRENDIMIENTO, no del servicio: es el mismo
    horario de atencion que ya se muestra en su perfil. Un servicio no tiene
    horario propio y no se le va a agregar uno: el vendedor dice una sola vez
    cuando atiende, y todos sus servicios se cortan de ahi.

    NO FILTRA LO QUE YA PASO. Pedir los slots de un dia de la semana pasada
    devuelve la grilla entera del dia, menos lo que estuvo reservado. Esta bien
    para lo que hace hoy -- calcular, y nada mas --, pero la pantalla que
    reserve (2b) tiene que cortar por su cuenta el pasado y el "faltan diez
    minutos": eso depende de la hora actual en Argentina, y meterlo aca haria
    que el resultado de la funcion cambie sola entre dos llamadas.
    """
    if not acepta_turnos(servicio):
        return []

    horario = horario_del_dia(servicio.post.author, fecha.weekday())
    if horario is None or horario.cerrado:
        return []

    slots = cortar_en_slots(
        horario.abre, horario.cierra, servicio.duracion_turno_minutos
    )
    if not slots:
        return []

    ocupadas = horas_tomadas(servicio.id, fecha)
    return [(inicio, fin) for inicio, fin in slots if inicio not in ocupadas]


def turno_por_id_o_404(id):
    return Turno.query.get_or_404(id)


def usa_candado_de_fila():
    """Si este motor soporta el candado que serializa las reservas.

    Solo MySQL. En SQLite -- que es dev y los tests, monoproceso -- SELECT ...
    FOR UPDATE no existe como candado real: el dialecto de SQLAlchemy ni
    siquiera lo emite. No es una perdida, porque el escenario que el candado
    ataja (dos requests simultaneos del mismo vendedor) no se da ahi.
    """
    return db.engine.dialect.name == "mysql"


def bloquear_agenda_del_vendedor(user_id):
    """Toma el candado de la fila del vendedor. Sin efecto fuera de MySQL.

    Es la primera mitad del cierre de la ventana entre el SELECT del chequeo de
    solapamiento y el INSERT del turno. Serializa POR VENDEDOR: dos clientes
    reservando con prestadores distintos no se estorban, y dos reservando con
    el mismo se ordenan una atras de la otra.

    Se bloquea la fila de users y no la de services a proposito: el
    solapamiento es de la agenda de la PERSONA, que puede tener varios
    emprendimientos y varios servicios. Un candado por servicio dejaria pasar
    justo el caso que hay que frenar, que es el de dos servicios distintos.

    El candado se suelta solo, cuando la transaccion commitea o hace rollback.
    """
    if not usa_candado_de_fila():
        return
    db.session.execute(select(User.id).where(User.id == user_id).with_for_update())


def rangos_ocupados_del_vendedor(user_id, fecha, excluir_turno_id=None):
    """Los (inicio, fin) activos de ESE dia en TODOS los servicios del vendedor.

    Es lo que necesita reglas.hay_solapamiento para el chequeo cross-service:
    el UNIQUE de la base mira un servicio a la vez, y un vendedor con "corte"
    de 30 minutos y "color" de 90 puede terminar con los dos a las 15:00.

    Cruza turnos -> services -> posts porque el turno cuelga del servicio y el
    servicio del emprendimiento; el vendedor es el autor del emprendimiento, y
    puede tener varios.

    ESTA LECTURA TIENE QUE SER CON CANDADO, y es la segunda mitad del cierre de
    la ventana (la primera es bloquear_agenda_del_vendedor). No alcanza con
    tomar el candado y despues leer normal: en MySQL/InnoDB con REPEATABLE READ
    -- que es el default -- el read view del request ya quedo fijado en el
    primer SELECT consistente, o sea al cargar el Service y al calcular los
    slots. Una lectura comun despues del candado seguiria viendo esa foto
    vieja, sin el turno que el ganador de la carrera acaba de commitear, y el
    perdedor se colaria igual. Una lectura con FOR UPDATE, en cambio, siempre
    lee la ultima version commiteada.

    Con las dos cosas juntas el perdedor espera en el candado, relee fresco, ve
    el turno del ganador y lo rechaza por solapamiento.

    El FOR UPDATE cae sobre el join entero, asi que tambien traba las filas de
    services y posts de ese vendedor mientras dura la transaccion. Se acepta:
    son milisegundos, las filas son del mismo vendedor que ya esta serializado
    por el candado de users, y acotarlo con FOR UPDATE OF pide MySQL 8.0.1 y
    dejaria la migracion atada a una version.

    excluir_turno_id existe para cuando se reprograme un turno (todavia no hay
    pantalla): sin eso, un turno chocaria consigo mismo.
    """
    return [(fila[0], fila[1])
            for fila in consulta_de_rangos(user_id, fecha, excluir_turno_id).all()]


def consulta_de_rangos(user_id, fecha, excluir_turno_id=None):
    """La consulta de rangos_ocupados_del_vendedor, sin ejecutar.

    Se separa para que un test pueda compilarla contra el dialecto de MySQL y
    comprobar que lleva el FOR UPDATE: en SQLite no hay forma de verlo, porque
    el dialecto directamente no lo emite, y el candado es justo lo que no se
    puede probar corriendo los tests en el motor donde no existe.
    """
    consulta = (
        Turno.query
        .with_entities(Turno.hora_inicio, Turno.hora_fin)
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            Post.author == user_id,
            Turno.fecha == fecha,
            Turno.estado == EstadosTurno.ACTIVO,
        )
    )
    if excluir_turno_id is not None:
        consulta = consulta.filter(Turno.id != excluir_turno_id)
    if usa_candado_de_fila():
        consulta = consulta.with_for_update()
    return consulta


def turnos_de_cliente(user_id):
    """Los turnos que ese usuario reservo, mas proximos primero.

    Los cancelados vienen tambien: el cliente tiene que poder ver que se
    cancelo y quien lo cancelo, no que el turno desaparezca sin explicacion.

    Los joinedload traen el servicio y su emprendimiento en la misma consulta:
    cada fila del listado los muestra, y sin ellos eso es un SELECT por turno
    (problema N+1). Mismo criterio que consultas.solicitudes_enviadas_por.
    """
    return (
        Turno.query
        .options(joinedload(Turno.servicio).joinedload(Service.post))
        .filter(Turno.cliente_id == user_id)
        .order_by(Turno.fecha.desc(), Turno.hora_inicio.desc())
        .all()
    )


def turnos_recibidos_por(user_id):
    """Los turnos que le sacaron a los servicios de sus emprendimientos.

    Mismo cruce que rangos_ocupados_del_vendedor y misma privacidad que las
    solicitudes: esto lo ve el dueño de los servicios y nadie mas.
    """
    return (
        Turno.query
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .options(
            joinedload(Turno.servicio).joinedload(Service.post),
            joinedload(Turno.cliente),
        )
        .filter(Post.author == user_id)
        .order_by(Turno.fecha.desc(), Turno.hora_inicio.desc())
        .all()
    )


# ------------------------------------------------------------------ escritura

def guardar(fila=None):
    """Confirma la transaccion, agregando la fila nueva si se pasa una.

    Igual que servicios.consultas.guardar: existe para que las vistas no
    importen db solo para escribir dos lineas de sesion. El manejo del
    IntegrityError se queda arriba, que es donde se sabe que significa el
    choque.
    """
    if fila is not None:
        db.session.add(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
