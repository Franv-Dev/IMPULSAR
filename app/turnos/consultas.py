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

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.blog.modelo_post import Post
from app.perfil.modelo_horario import Horario
from app.servicios.modelo import Service
from app.servicios.reglas import acepta_turnos
from app.turnos.modelo_turno import EstadosTurno, Turno
from app.turnos.reglas import (
    cortar_en_slots, descartar_pasados, marcar_ocupados
)
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


def horarios_de(user_id):
    """Los Horario de esa persona, indexados por dia de la semana.

    Una sola consulta para los siete dias, contra una por dia de
    horario_del_dia(). La tira de la semana necesita los siete a la vez, y siete
    consultas para leer siete filas de la misma tabla es el N+1 de siempre.

    horario_del_dia() se queda igual y se sigue usando donde se mira un dia
    solo (el calculo de un dia de slots): pedir la semana entera para mirar el
    lunes seria el desperdicio simetrico.
    """
    return {horario.dia_semana: horario
            for horario in Horario.query.filter_by(user_id=user_id).all()}


def horas_tomadas_por_dia(service_id, desde, hasta):
    """Las horas de inicio ya reservadas de ese servicio, por fecha, en el rango.

    Devuelve {fecha: set de horas}, con [desde, hasta] inclusive de los dos
    lados. Es horas_tomadas() para varios dias de una: la tira de siete dias de
    la pantalla de reservar los necesita todos, y una consulta por dia son
    siete viajes para leer una tabla sola.

    Las fechas sin ningun turno no aparecen en el diccionario. Quien lo lee usa
    .get(fecha, set()), que es lo mismo que devolveria horas_tomadas() para ese
    dia.
    """
    filas = (
        Turno.query
        .with_entities(Turno.fecha, Turno.hora_inicio)
        .filter(
            Turno.service_id == service_id,
            Turno.fecha >= desde,
            Turno.fecha <= hasta,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .all()
    )
    tomadas = {}
    for fecha, hora in filas:
        tomadas.setdefault(fecha, set()).add(hora)
    return tomadas


# Por que un dia no tiene nada que ofrecer. Son los seis vacios que
# slots_disponibles() junta en una lista vacia, agrupados en los que se pueden
# DECIR: quien mira necesita saber si el negocio no atiende ese dia, si no
# queda lugar, o si el servicio directamente no toma turnos. Se ven distintos
# en pantalla y no se arreglan igual.
SIN_TURNOS = "sin-turnos"       # el servicio no los toma, o no tiene duracion
CERRADO = "cerrado"             # ese dia esta marcado cerrado
SIN_HORARIO = "sin-horario"     # el dueño no cargo horario para ese dia
COMPLETO = "completo"           # hay grilla, pero ya se reservaron todas
PASO = "paso"                   # quedaban libres, pero su hora ya paso (es hoy)
HAY_LUGAR = None                # queda al menos una


def dia_de_slots(servicio, fecha, horario, tomadas, ahora):
    """Como se ve un dia en la pantalla de reservar: su grilla y por que esta asi.

    Devuelve un dict con la fecha, el horario de atencion, los slots ya
    marcados (inicio, fin, ocupado) y `motivo`, que es None cuando queda alguna
    libre y una de las constantes de arriba cuando no.

    RECIBE EL HORARIO Y LAS HORAS TOMADAS YA CONSULTADAS, no las busca: se lo
    llama siete veces seguidas para armar la tira de la semana, y buscarlas
    adentro serian catorce consultas. Por eso es una funcion aparte y no una
    variante de slots_disponibles().

    Lo que ya paso queda AFUERA DE LOS LIBRES pero adentro de la grilla: el
    turno de las 10:00 de hoy, a las 15:00, se dibuja como un tramo mas del dia
    y no se puede tocar. Sacarlo de la grilla dejaria el dia de hoy con un
    agujero al principio que no se distingue de un dia con poca atencion.
    """
    vacio = {"fecha": fecha, "horario": None, "slots": [], "libres": 0}

    if not acepta_turnos(servicio):
        return dict(vacio, motivo=SIN_TURNOS)
    if horario is None:
        return dict(vacio, motivo=SIN_HORARIO)
    if horario.cerrado:
        return dict(vacio, horario=horario, motivo=CERRADO)

    grilla = cortar_en_slots(
        horario.abre, horario.cierra, servicio.duracion_turno_minutos
    )
    if not grilla:
        # Un horario que cruza medianoche, o mas corto que la duracion del
        # turno: hay dia de atencion, pero no entra ni uno. Para quien mira es
        # el mismo caso que un dia sin horario cargado -- no hay nada que
        # reservar --, asi que se dice igual y no se inventa otro mensaje.
        return dict(vacio, horario=horario, motivo=SIN_HORARIO)

    slots = marcar_ocupados(grilla, tomadas)
    reservables = {inicio for inicio, _fin in
                   descartar_pasados(grilla, fecha, ahora)}
    libres = [par for par in slots if not par[2] and par[0] in reservables]

    # Sin nada que reservar, POR QUE no lo hay son dos cosas distintas y se
    # dicen distinto: que se lo hayan llevado todo no es lo mismo que que el dia
    # ya haya arrancado. Solo el dia de hoy puede caer en el segundo caso.
    motivo = HAY_LUGAR
    if not libres:
        quedaban = any(not ocupado for _inicio, _fin, ocupado in slots)
        motivo = PASO if quedaban else COMPLETO

    return {
        "fecha": fecha,
        "horario": horario,
        "slots": slots,
        "libres": len(libres),
        "motivo": motivo,
    }


def semana_de_slots(servicio, desde, ahora, dias=7):
    """Los dias de la tira de la pantalla de reservar, a partir de `desde`.

    Dos consultas para toda la semana: los horarios de la persona y las horas
    tomadas del rango. Lo demas es el corte de reglas.cortar_en_slots, que es
    puro.

    Reemplaza al <input type="date"> a ciegas de la pantalla vieja, donde habia
    que adivinar que dia tenia lugar: aca cada dia trae cuantas horas libres le
    quedan antes de tocarlo.
    """
    fechas = [desde + timedelta(days=numero) for numero in range(dias)]
    horarios = horarios_de(servicio.post.author)
    tomadas = horas_tomadas_por_dia(servicio.id, fechas[0], fechas[-1])
    return [
        dia_de_slots(servicio, fecha, horarios.get(fecha.weekday()),
                     tomadas.get(fecha, set()), ahora)
        for fecha in fechas
    ]


def turnos_recibidos_del_dia(user_id, fecha):
    """Los turnos que le sacaron ese dia, en orden de reloj, cancelados incluidos.

    La agenda es un dia y no una lista de tarjetas por fecha DESC: lo que se le
    pide a una agenda es "que tengo mañana", y para eso el orden es el del
    reloj.

    Los cancelados vienen tambien, y a proposito: el vendedor tiene que ver que
    alguien se dio de baja del dia que esta mirando. Se dibujan aparte, porque
    su horario ya no esta tomado y no participa de los huecos.
    """
    return (
        Turno.query
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .options(
            joinedload(Turno.servicio).joinedload(Service.post),
            joinedload(Turno.cliente),
        )
        .filter(Post.author == user_id, Turno.fecha == fecha)
        .order_by(Turno.hora_inicio)
        .all()
    )


def turnos_por_dia_de(user_id, desde, hasta):
    """Cuantos turnos activos le sacaron cada dia del rango. {fecha: cantidad}.

    Es el numerito de cada dia de la tira de la semana de la agenda. Un COUNT
    agrupado y no las filas: de los otros dias solo se muestra cuantos son, y
    traer los turnos enteros de siete dias para contarlos es cargar la semana
    para dibujar seis numeros.
    """
    filas = (
        db.session.query(Turno.fecha, func.count(Turno.id))
        .join(Service, Service.id == Turno.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            Post.author == user_id,
            Turno.fecha >= desde,
            Turno.fecha <= hasta,
            Turno.estado == EstadosTurno.ACTIVO,
        )
        .group_by(Turno.fecha)
        .all()
    )
    return {fecha: cantidad for fecha, cantidad in filas}


def rangos_activos_de(turnos):
    """Los (inicio, fin) de los turnos activos de esa lista, ya consultada.

    Es lo que reglas.huecos_entre necesita para dibujar lo que queda libre. No
    consulta nada: la agenda ya tiene los turnos del dia en la mano, y volver a
    pedirlos a la base para mirarles dos columnas seria una consulta de mas.
    """
    return [(turno.hora_inicio, turno.hora_fin)
            for turno in turnos if turno.esta_activo]


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
