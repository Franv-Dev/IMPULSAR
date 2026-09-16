"""El prestador puede guardar su respuesta sin enviarla.

DOS COSAS QUE HAY QUE TENER EN LA CABEZA ANTES DE TOCAR ESTO, y ninguna se
deduce leyendo el modelo:

1. BORRADOR NO ES UN ESTADO DEL FLUJO, ES UN ESTADO DEL PRESTADOR. Los otros tres
   (pendiente, respondida, cerrada) significan lo mismo para las dos partes.
   Este no: para el cliente su pedido sigue sin respuesta, y no tiene por que
   enterarse de que el prestador empezo a escribir. De ahi salen la mitad de los
   tests de este archivo: lo que el cliente ve.

2. EL BORRADOR SIGUE OCUPANDO EL CUPO DE LA PENDIENTE UNICA. La tabla tiene un
   UNIQUE(service_id, cliente_id, cupo_pendiente) donde cupo_pendiente vale 1
   mientras la solicitud esta sin responder, y un borrador cuenta como sin
   responder. Si lo liberara, el cliente podria mandar un segundo pedido
   identico sobre el mismo servicio mientras el primero espera -- que es
   exactamente lo que el UNIQUE vino a evitar --. El efecto practico es que pasar
   de pendiente a borrador NO toca ninguna de las tres columnas del UNIQUE, asi
   que el camino nuevo no puede chocar con el; los tests de abajo lo recorren en
   los tres ordenes igual, porque eso es lo que hay que poder afirmar y no el
   razonamiento.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.servicios.modelo import Rubros, Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest


@pytest.fixture
def crear_servicio(db):
    def _crear(post_id, titulo="Destapaciones"):
        servicio = Service(
            post_id=post_id, titulo=titulo, rubro=Rubros.PLOMERIA,
            descripcion="Arreglos de canios", zona_cobertura="Toda la ciudad",
        )
        db.session.add(servicio)
        db.session.commit()
        return servicio

    return _crear


@pytest.fixture
def solicitud_pendiente(db, crear_usuario, crear_post, crear_servicio):
    """Un pedido de presupuesto sin contestar, con sus dos partes."""

    def _crear():
        prestador = crear_usuario(username="prestador")
        post = crear_post(prestador.id)
        servicio = crear_servicio(post.id)
        cliente = crear_usuario(username="cliente")
        solicitud = ServiceRequest(
            service_id=servicio.id, cliente_id=cliente.id,
            descripcion="Se me tapo la pileta",
        )
        db.session.add(solicitud)
        db.session.commit()
        return prestador, cliente, servicio, solicitud

    return _crear


def _texto(respuesta):
    return respuesta.get_data(as_text=True)


PRECIO = "4500"
MENSAJE = "Voy el martes a la mañana y te lo dejo andando"


def _guardar_borrador(client, solicitud_id, mensaje=MENSAJE, precio=PRECIO):
    return client.post(
        f"/servicios/solicitudes/{solicitud_id}/responder",
        data={
            "respuesta_precio": precio, "respuesta_mensaje": mensaje,
            "accion": "borrador",
        },
        follow_redirects=True,
    )


def _enviar(client, solicitud_id, mensaje=MENSAJE, precio=PRECIO):
    return client.post(
        f"/servicios/solicitudes/{solicitud_id}/responder",
        data={
            "respuesta_precio": precio, "respuesta_mensaje": mensaje,
            "accion": "enviar",
        },
        follow_redirects=True,
    )


def test_guardar_sin_enviar_deja_la_respuesta_escrita_y_no_la_manda(
    client, db, login, solicitud_pendiente
):
    """Guarda las dos columnas, pone el estado en borrador y no toca lo demas.

    responded_at es lo que mas importa que siga en NULL: es la fecha en que el
    cliente recibio la respuesta, y de ahi salen "respondidas este mes" y las
    demoras promedio del resumen del prestador. Escribirla al guardar un borrador
    le mejoraria las metricas por empezar a escribir.
    """
    prestador, _, _, solicitud = solicitud_pendiente()
    login(prestador.id)

    _guardar_borrador(client, solicitud.id)
    db.session.expire_all()

    assert solicitud.estado == EstadosSolicitud.BORRADOR
    assert solicitud.respuesta_mensaje == MENSAJE
    assert solicitud.respuesta_precio == Decimal(PRECIO)
    assert solicitud.responded_at is None


def test_el_cliente_no_ve_el_borrador_y_la_sigue_viendo_pendiente(
    client, db, login, solicitud_pendiente
):
    """Lo que el cliente ve es lo mismo que veia antes de que el otro escribiera.

    Las dos pantallas donde se filtraba, y las dos por el mismo motivo: miraban
    si las COLUMNAS de respuesta tenian algo, y un borrador las tiene escritas.
    Ahora miran el estado (respuesta_visible en el modelo).

    Y tampoco se le nombra el estado: el cartel le dice "Pendiente", no
    "Borrador". Saber que el otro empezo a escribir y lo dejo a medias no es
    informacion que le sirva, y le haria esperar distinto.
    """
    prestador, cliente, _, solicitud = solicitud_pendiente()

    login(prestador.id)
    _guardar_borrador(client, solicitud.id)

    login(cliente.id)
    detalle = _texto(client.get(f"/servicios/solicitudes/{solicitud.id}"))
    assert MENSAJE not in detalle
    assert "4.500" not in detalle
    assert "Borrador" not in detalle
    assert "Pendiente" in detalle

    lista = _texto(client.get("/servicios/solicitudes?lado=enviadas"))
    assert MENSAJE not in lista
    assert "Borrador" not in lista


def test_el_prestador_vuelve_y_encuentra_su_borrador_precargado(
    client, login, solicitud_pendiente
):
    """Si al volver el formulario estuviera en blanco, el borrador no serviria.

    Se afirma que el texto esta ADENTRO del formulario --en el value del precio y
    en el textarea-- y no solo en la pagina: encontrarlo suelto en el HTML podria
    ser el bloque de "tu respuesta" de solo lectura, que es otra cosa.
    """
    prestador, _, _, solicitud = solicitud_pendiente()
    login(prestador.id)

    _guardar_borrador(client, solicitud.id)
    html = _texto(client.get(f"/servicios/solicitudes/{solicitud.id}"))

    # El input se precarga con texto_para_formulario: punto decimal y sin
    # separador de miles, que es lo que parsear_precio vuelve a leer.
    assert 'value="4500.00"' in html
    assert f">{MENSAJE}</textarea>" in html
    # Y se le dice de que lado esta: sigue sin enviarse.
    assert "Guardar sin enviar" in html


def test_enviar_la_respuesta_sigue_funcionando_igual_que_antes(
    client, db, login, solicitud_pendiente, monkeypatch
):
    """El camino de siempre no cambia: respondida, con fecha y con mail."""
    import app.servicios.vistas as vistas

    avisados = []
    monkeypatch.setattr(
        vistas, "notificar_solicitud_respondida", lambda s: avisados.append(s.id)
    )

    prestador, _, _, solicitud = solicitud_pendiente()
    login(prestador.id)

    _enviar(client, solicitud.id)
    db.session.expire_all()

    assert solicitud.estado == EstadosSolicitud.RESPONDIDA
    assert solicitud.respuesta_mensaje == MENSAJE
    assert isinstance(solicitud.responded_at, datetime)
    assert avisados == [solicitud.id]


def test_enviar_desde_un_borrador_tambien_avisa_al_cliente(
    client, db, login, solicitud_pendiente, monkeypatch
):
    """El mail sale al ENVIAR, aunque antes haya pasado por borrador.

    Es el bug que el camino nuevo podia introducir sin que nada se pusiera en
    rojo: el aviso salia solo si el estado anterior era PENDIENTE, asi que
    guardar el borrador primero dejaba al cliente sin el mail para siempre --su
    pedido pasaba de pendiente a respondida sin que nadie le dijera nada--.
    """
    import app.servicios.vistas as vistas

    avisados = []
    monkeypatch.setattr(
        vistas, "notificar_solicitud_respondida", lambda s: avisados.append(s.id)
    )

    prestador, cliente, _, solicitud = solicitud_pendiente()
    login(prestador.id)

    _guardar_borrador(client, solicitud.id)
    assert avisados == [], "el borrador no le manda nada a nadie"

    _enviar(client, solicitud.id, mensaje="Ahora si, va en serio")
    db.session.expire_all()

    assert solicitud.estado == EstadosSolicitud.RESPONDIDA
    assert avisados == [solicitud.id]

    # Y ahora el cliente si la ve.
    login(cliente.id)
    detalle = _texto(client.get(f"/servicios/solicitudes/{solicitud.id}"))
    assert "Ahora si, va en serio" in detalle


def test_un_borrador_sigue_contando_como_pendiente_para_el_prestador(
    client, db, login, solicitud_pendiente
):
    """El contador y el grupo de arriba dicen cuantas le faltan contestar.

    Un borrador le falta: lo empezo y no lo mando. Si contara como contestada, la
    solicitud se le iria al grupo "Ya contestadas" y el aviso del panel bajaria a
    cero, o sea que la forma de sacarse un pendiente de encima seria escribir dos
    palabras y no enviarlas.
    """
    from app.panel import consultas as consultas_panel
    from app.servicios import consultas as consultas_servicios

    prestador, _, _, solicitud = solicitud_pendiente()
    login(prestador.id)

    assert consultas_servicios.cuantas_solicitudes_pendientes_para(prestador.id) == 1
    _guardar_borrador(client, solicitud.id)
    db.session.expire_all()
    assert consultas_servicios.cuantas_solicitudes_pendientes_para(prestador.id) == 1
    assert consultas_panel.contadores_de(
        prestador.id, datetime(2026, 9, 15).date()
    )["solicitudes"] == 1

    # Y recien al enviarla deja de estar pendiente.
    _enviar(client, solicitud.id)
    db.session.expire_all()
    assert consultas_servicios.cuantas_solicitudes_pendientes_para(prestador.id) == 0


# --------------------------------------------------- el cupo de la pendiente unica

def _cupo(solicitud_id):
    return ServiceRequest.query.get(solicitud_id).cupo_pendiente


def test_el_cupo_de_la_pendiente_unica_aguanta_los_tres_caminos(
    client, db, login, solicitud_pendiente
):
    """cupo_pendiente en cada paso, por los tres ordenes posibles.

    Es la columna que sostiene el UNIQUE(service_id, cliente_id, cupo_pendiente),
    la mantiene un listener y no se toca a mano en ningun lado. Lo que se congela
    es que el borrador la deje en 1 --sigue ocupando el cupo-- y que enviar o
    cerrar la libere, salga de donde salga.
    """
    prestador, _, _, solicitud = solicitud_pendiente()
    solicitud_id = solicitud.id
    login(prestador.id)

    # Recien creada: pendiente, ocupa el cupo.
    assert _cupo(solicitud_id) == 1

    # Guardar borrador: sigue ocupandolo, y de hecho no cambio nada del UNIQUE.
    _guardar_borrador(client, solicitud_id)
    assert _cupo(solicitud_id) == 1

    # Guardarlo dos veces seguidas tampoco lo rompe (es el mismo UPDATE).
    _guardar_borrador(client, solicitud_id, mensaje="Lo pienso de nuevo")
    assert _cupo(solicitud_id) == 1

    # Enviar desde el borrador: lo libera.
    _enviar(client, solicitud_id)
    assert _cupo(solicitud_id) is None


def test_enviar_directo_sin_pasar_por_borrador_libera_el_cupo_igual(
    client, db, login, solicitud_pendiente
):
    """El tercer camino: pendiente -> respondida, sin borrador en el medio."""
    prestador, _, _, solicitud = solicitud_pendiente()
    solicitud_id = solicitud.id
    login(prestador.id)

    assert _cupo(solicitud_id) == 1
    _enviar(client, solicitud_id)
    assert _cupo(solicitud_id) is None


def test_con_un_borrador_abierto_el_cliente_no_puede_pedir_dos_veces(
    client, db, login, solicitud_pendiente
):
    """La razon de ser de que el borrador ocupe el cupo.

    El cliente no sabe que el prestador empezo a escribir: para el su pedido
    sigue esperando. Si el borrador liberara el cupo, podria mandar un segundo
    pedido identico sobre el mismo servicio y el prestador se encontraria con dos
    filas, una con su borrador y otra vacia.

    Se chequea el efecto que ve el cliente (el mensaje, no un IntegrityError):
    la garantia la da el UNIQUE de la base, pero la vista tiene que llegar antes
    para poder decirlo con palabras.
    """
    prestador, cliente, servicio, solicitud = solicitud_pendiente()

    login(prestador.id)
    _guardar_borrador(client, solicitud.id)

    login(cliente.id)
    respuesta = client.post(
        f"/servicios/{servicio.id}/solicitar",
        data={"descripcion": "Otra vez lo mismo", "zona": ""},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200

    # Sigue habiendo UNA sola solicitud de ese cliente sobre ese servicio.
    cuantas = ServiceRequest.query.filter_by(
        service_id=servicio.id, cliente_id=cliente.id
    ).count()
    assert cuantas == 1


def test_cerrar_una_solicitud_con_borrador_libera_el_cupo(
    client, db, login, solicitud_pendiente
):
    """Cerrar desde borrador tambien la saca de la lista de lo que falta.

    Es el cuarto camino y el que menos se prueba solo: el prestador escribe algo,
    se arrepiente y la archiva sin contestar. El cupo se libera, asi que el
    cliente puede volver a pedir presupuesto sobre el mismo servicio.
    """
    prestador, _, _, solicitud = solicitud_pendiente()
    solicitud_id = solicitud.id
    login(prestador.id)

    _guardar_borrador(client, solicitud_id)
    assert _cupo(solicitud_id) == 1

    client.post(
        f"/servicios/solicitudes/{solicitud_id}/cerrar", follow_redirects=True
    )
    db.session.expire_all()
    assert ServiceRequest.query.get(solicitud_id).estado == EstadosSolicitud.CERRADA
    assert _cupo(solicitud_id) is None


def test_el_borrador_lo_escribe_solo_el_prestador(
    client, db, login, solicitud_pendiente
):
    """El cliente no puede guardar un borrador en su propia solicitud.

    Pasa por el mismo corte que enviar una respuesta, que es de quien presta el
    servicio: el boton no existe de su lado, y el POST se puede armar a mano.
    """
    _, cliente, _, solicitud = solicitud_pendiente()
    login(cliente.id)

    _guardar_borrador(client, solicitud.id)
    db.session.expire_all()

    assert solicitud.estado == EstadosSolicitud.PENDIENTE
    assert solicitud.respuesta_mensaje is None
