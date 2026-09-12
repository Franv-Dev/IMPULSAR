"""Oportunidades: publicar, proponer y el ciclo de estados.

Lo que se prueba y por que:

  - los largos, CON CONTRAPRUEBA: que el texto que entra se guarde y que el que
    no entra corte. Sin la contraprueba, un test de largo pasa igual aunque la
    validacion rechace todo (B1). En SQLite no se nota nunca: guarda el texto
    entero se pase o no.
  - los permisos DEL LADO DEL SERVIDOR, pidiendo las URL a mano: que el boton
    no se dibuje no prueba nada (B4).
  - las transiciones de estado, las tres, incluida la que NO se puede hacer.
  - el UNIQUE de la unica propuesta aceptada, que es lo que tapa el doble click.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.oportunidades import consultas, reglas
from app.oportunidades.modelo_oportunidad import EstadosOportunidad, Oportunidad
from app.oportunidades.modelo_propuesta import Propuesta
from db import db as _db


@pytest.fixture
def usuario_completo(crear_usuario, db):
    """Un usuario con el perfil completo: puede publicar oportunidades."""

    def _crear(username="clienta"):
        user = crear_usuario(username=username)
        user.phone = "261 123-4567"
        user.location = "Mendoza"
        db.session.commit()
        return user

    return _crear


@pytest.fixture
def crear_oportunidad(db):
    def _crear(autor_id, titulo="Necesito un logo", **kwargs):
        oportunidad = Oportunidad(
            autor_id=autor_id,
            titulo=titulo,
            descripcion=kwargs.pop("descripcion", "Tengo el nombre y los colores."),
            **kwargs,
        )
        db.session.add(oportunidad)
        db.session.commit()
        return oportunidad

    return _crear


@pytest.fixture
def crear_propuesta(db):
    def _crear(oportunidad_id, post_id, precio="25000", plazo_dias=7, **kwargs):
        propuesta = Propuesta(
            oportunidad_id=oportunidad_id,
            post_id=post_id,
            precio=precio,
            plazo_dias=plazo_dias,
            mensaje=kwargs.pop("mensaje", "Te mando tres bocetos."),
            **kwargs,
        )
        db.session.add(propuesta)
        db.session.commit()
        return propuesta

    return _crear


# ------------------------------------------------------------------ publicar

def test_publicar_crea_la_oportunidad_abierta(client, login, usuario_completo):
    user = usuario_completo()
    login(user.id)

    respuesta = client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "Para el cartel y las redes.",
        "presupuesto": "30000",
        "fecha_limite": "",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    oportunidad = Oportunidad.query.one()
    assert oportunidad.estado == EstadosOportunidad.ABIERTA
    assert str(oportunidad.presupuesto) == "30000.00"
    assert oportunidad.cerrada_at is None
    assert oportunidad.finalizada_at is None


def test_sin_perfil_completo_no_se_puede_publicar(client, login, crear_usuario):
    """Publicar exige telefono y ubicacion, el mismo criterio que postularse."""
    user = crear_usuario(username="sinperfil")
    login(user.id)

    respuesta = client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "Para el cartel.",
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    assert Oportunidad.query.count() == 0


def test_el_presupuesto_y_la_fecha_son_opcionales(client, login, usuario_completo):
    """Los dos en blanco no son un error: "no se cuanto sale" es el caso real."""
    user = usuario_completo()
    login(user.id)

    client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "Para el cartel.",
        "presupuesto": "",
        "fecha_limite": "",
    })

    oportunidad = Oportunidad.query.one()
    assert oportunidad.presupuesto is None
    assert oportunidad.fecha_limite is None


def test_una_fecha_limite_ya_pasada_se_rechaza(client, login, usuario_completo):
    user = usuario_completo()
    login(user.id)
    ayer = (date.today() - timedelta(days=1)).isoformat()

    client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "Para el cartel.",
        "fecha_limite": ayer,
    })

    assert Oportunidad.query.count() == 0


def test_un_presupuesto_negativo_no_entra(client, login, usuario_completo):
    user = usuario_completo()
    login(user.id)

    client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "Para el cartel.",
        "presupuesto": "-500",
    })

    assert Oportunidad.query.count() == 0


# -------------------------------------------------------------------- largos

def test_el_titulo_en_el_limite_entra(client, login, usuario_completo):
    """La contraprueba del test de abajo: el largo valido TIENE que pasar."""
    user = usuario_completo()
    login(user.id)
    titulo = "a" * reglas.MAX_TITULO

    client.post("/oportunidades/publicar", data={
        "titulo": titulo, "descripcion": "Para el cartel.",
    })

    assert Oportunidad.query.one().titulo == titulo


def test_un_titulo_mas_largo_que_la_columna_se_rechaza(client, login, usuario_completo):
    user = usuario_completo()
    login(user.id)

    client.post("/oportunidades/publicar", data={
        "titulo": "a" * (reglas.MAX_TITULO + 1),
        "descripcion": "Para el cartel.",
    })

    assert Oportunidad.query.count() == 0


def test_la_descripcion_en_el_limite_entra(client, login, usuario_completo):
    user = usuario_completo()
    login(user.id)
    descripcion = "b" * reglas.MAX_DESCRIPCION

    client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo", "descripcion": descripcion,
    })

    assert Oportunidad.query.one().descripcion == descripcion


def test_una_descripcion_mas_larga_que_la_columna_se_rechaza(
    client, login, usuario_completo
):
    user = usuario_completo()
    login(user.id)

    client.post("/oportunidades/publicar", data={
        "titulo": "Necesito un logo",
        "descripcion": "b" * (reglas.MAX_DESCRIPCION + 1),
    })

    assert Oportunidad.query.count() == 0


def test_el_mensaje_de_la_propuesta_en_el_limite_entra(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)
    mensaje = "c" * reglas.MAX_MENSAJE

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25000", "plazo_dias": "7",
        "mensaje": mensaje,
    })

    assert Propuesta.query.one().mensaje == mensaje


def test_un_mensaje_mas_largo_que_la_columna_se_rechaza(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25000", "plazo_dias": "7",
        "mensaje": "c" * (reglas.MAX_MENSAJE + 1),
    })

    assert Propuesta.query.count() == 0


# ------------------------------------------------------------------ proponer

def test_un_emprendedor_puede_proponer(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25.000,50", "plazo_dias": "14",
        "mensaje": "Te mando tres bocetos.",
    })

    propuesta = Propuesta.query.one()
    assert propuesta.post_id == post.id
    # La coma decimal se lee como coma decimal (services/precios.py).
    assert str(propuesta.precio) == "25000.50"
    assert propuesta.plazo_dias == 14
    assert propuesta.aceptada is False


def test_un_usuario_sin_emprendimiento_no_puede_proponer(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    """La asimetria del dominio: publicar no pide un post, proponer si.

    Se manda el post de OTRO, que es lo que haria alguien sin emprendimiento
    escribiendo el POST a mano: el permiso es del lado del servidor.
    """
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    dueño = crear_usuario(username="ajeno")
    post_ajeno = crear_post(dueño.id, title="Estudio ajeno")
    sin_nada = crear_usuario(username="sinposts")
    login(sin_nada.id)

    respuesta = client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post_ajeno.id, "precio": "25000", "plazo_dias": "7",
        "mensaje": "Yo lo hago.",
    })

    assert respuesta.status_code == 403
    assert Propuesta.query.count() == 0


def test_no_se_propone_a_la_propia_oportunidad(
    client, login, usuario_completo, crear_post, crear_oportunidad
):
    """Ademas de no significar nada, el chat de messages.conversation tira 404
    cuando el cliente es el dueño del post: se corta antes."""
    autora = usuario_completo()
    post = crear_post(autora.id, title="Mi propio emprendimiento")
    oportunidad = crear_oportunidad(autora.id)
    login(autora.id)

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25000", "plazo_dias": "7",
        "mensaje": "Me lo hago yo.",
    })

    assert Propuesta.query.count() == 0


def test_una_oportunidad_cerrada_no_recibe_propuestas(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(
        autora.id, estado=EstadosOportunidad.CERRADA,
    )
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25000", "plazo_dias": "7",
        "mensaje": "Llego tarde.",
    })

    assert Propuesta.query.count() == 0


def test_un_emprendimiento_puede_mandar_varias_propuestas(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    """A diferencia de Postulacion, aca NO hay unique: la segunda propuesta
    (despues de hablar por chat) es informacion nueva, no un duplicado."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    for precio in ("25000", "20000"):
        client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
            "post_id": post.id, "precio": precio, "plazo_dias": "7",
            "mensaje": f"Te lo hago por {precio}.",
        })

    assert Propuesta.query.count() == 2


def test_un_plazo_fuera_de_rango_se_rechaza(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    for plazo in ("0", "-3", str(reglas.MAX_PLAZO + 1), "un mes"):
        client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
            "post_id": post.id, "precio": "25000", "plazo_dias": plazo,
            "mensaje": "Te lo hago.",
        })

    assert Propuesta.query.count() == 0


def test_el_plazo_en_el_limite_entra(
    client, login, usuario_completo, crear_usuario, crear_post, crear_oportunidad
):
    """La contraprueba del de arriba."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    login(emprendedor.id)

    client.post(f"/oportunidades/{oportunidad.id}/proponer", data={
        "post_id": post.id, "precio": "25000",
        "plazo_dias": str(reglas.MAX_PLAZO), "mensaje": "Te lo hago.",
    })

    assert Propuesta.query.one().plazo_dias == reglas.MAX_PLAZO


# ------------------------------------------------------ el ciclo de estados

def test_aceptar_cierra_la_oportunidad_y_marca_la_propuesta(
    client, login, usuario_completo, crear_usuario, crear_post,
    crear_oportunidad, crear_propuesta,
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    propuesta = crear_propuesta(oportunidad.id, post.id)
    login(autora.id)

    respuesta = client.post(
        f"/oportunidades/{oportunidad.id}/aceptar/{propuesta.id}"
    )

    assert oportunidad.estado == EstadosOportunidad.CERRADA
    assert oportunidad.cerrada_at is not None
    assert propuesta.aceptada is True
    # Aceptar ABRE el chat: redirige a la conversacion (post, publicador). No
    # inserta ningun mensaje -- el hilo aparece cuando alguien escribe.
    assert respuesta.headers["Location"].endswith(
        f"/mensajes/{post.id}/{autora.id}"
    )


def test_reabrir_vuelve_a_abierta_y_conserva_las_propuestas(
    client, login, usuario_completo, crear_usuario, crear_post,
    crear_oportunidad, crear_propuesta,
):
    """Al reves que BusquedaPersonal, reabrir NO crea una fila nueva ni
    invalida nada: lo unico que se desmarca es cual era la aceptada."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    otro = crear_usuario(username="otro")
    post_otro = crear_post(otro.id, title="Otro estudio")
    primera = crear_propuesta(oportunidad.id, post.id)
    segunda = crear_propuesta(oportunidad.id, post_otro.id, precio="19000")
    login(autora.id)

    client.post(f"/oportunidades/{oportunidad.id}/aceptar/{primera.id}")
    client.post(f"/oportunidades/{oportunidad.id}/reabrir")

    assert oportunidad.estado == EstadosOportunidad.ABIERTA
    assert oportunidad.cerrada_at is None
    assert primera.aceptada is False
    # Las dos siguen existiendo y las dos siguen siendo elegibles.
    assert Propuesta.query.count() == 2
    assert consultas.propuesta_aceptada_de(oportunidad.id) is None

    # Y se puede elegir la otra, que es todo el sentido de reabrir.
    client.post(f"/oportunidades/{oportunidad.id}/aceptar/{segunda.id}")
    assert segunda.aceptada is True
    assert oportunidad.estado == EstadosOportunidad.CERRADA


def test_finalizar_no_tiene_vuelta(
    client, login, usuario_completo, crear_oportunidad,
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    login(autora.id)

    client.post(f"/oportunidades/{oportunidad.id}/finalizar")
    assert oportunidad.estado == EstadosOportunidad.FINALIZADA
    assert oportunidad.finalizada_at is not None

    # Ni reabrir ni volver a finalizar la sacan de ahi.
    client.post(f"/oportunidades/{oportunidad.id}/reabrir")
    assert oportunidad.estado == EstadosOportunidad.FINALIZADA

    client.post(f"/oportunidades/{oportunidad.id}/finalizar")
    assert oportunidad.estado == EstadosOportunidad.FINALIZADA


def test_una_finalizada_sale_del_listado_publico_pero_queda_en_el_historial(
    client, login, usuario_completo, crear_oportunidad,
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id, titulo="Necesito un logo")
    login(autora.id)
    client.post(f"/oportunidades/{oportunidad.id}/finalizar")

    publico = client.get("/oportunidades/")
    assert "Necesito un logo" not in publico.get_data(as_text=True)

    historial = client.get("/oportunidades/mias")
    assert "Necesito un logo" in historial.get_data(as_text=True)


def test_una_finalizada_ajena_es_404(
    client, login, usuario_completo, crear_usuario, crear_oportunidad,
):
    """404 y no 403: para el que la mira dejo de existir, y un 403 confirmaria
    que existe."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    login(autora.id)
    client.post(f"/oportunidades/{oportunidad.id}/finalizar")

    curioso = crear_usuario(username="curioso")
    login(curioso.id)
    assert client.get(f"/oportunidades/{oportunidad.id}").status_code == 404


def test_una_cerrada_sigue_siendo_visible(
    client, login, usuario_completo, crear_usuario, crear_oportunidad,
):
    """Sale del listado publico pero no del alcance: el que mando una propuesta
    tiene que poder ver en que quedo."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(
        autora.id, estado=EstadosOportunidad.CERRADA,
    )
    curioso = crear_usuario(username="curioso")
    login(curioso.id)

    assert client.get(f"/oportunidades/{oportunidad.id}").status_code == 200
    assert oportunidad.titulo not in client.get("/oportunidades/").get_data(
        as_text=True
    )


# ------------------------------------------------------------------ permisos

@pytest.mark.parametrize("accion", ["reabrir", "finalizar"])
def test_un_no_autor_no_puede_decidir(
    client, login, usuario_completo, crear_usuario, crear_oportunidad, accion,
):
    """Del lado del SERVIDOR, pidiendo la URL a mano: que el boton no se dibuje
    no prueba nada (B4)."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(
        autora.id, estado=EstadosOportunidad.CERRADA,
    )
    intruso = crear_usuario(username="intruso")
    login(intruso.id)

    respuesta = client.post(f"/oportunidades/{oportunidad.id}/{accion}")

    assert respuesta.status_code == 403
    assert oportunidad.estado == EstadosOportunidad.CERRADA


def test_un_no_autor_no_puede_aceptar(
    client, login, usuario_completo, crear_usuario, crear_post,
    crear_oportunidad, crear_propuesta,
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    propuesta = crear_propuesta(oportunidad.id, post.id)
    # El propio emprendedor intentando aceptarse la propuesta.
    login(emprendedor.id)

    respuesta = client.post(
        f"/oportunidades/{oportunidad.id}/aceptar/{propuesta.id}"
    )

    assert respuesta.status_code == 403
    assert propuesta.aceptada is False
    assert oportunidad.estado == EstadosOportunidad.ABIERTA


def test_no_se_acepta_una_propuesta_de_otra_oportunidad(
    client, login, usuario_completo, crear_usuario, crear_post,
    crear_oportunidad, crear_propuesta,
):
    """Los dos ids llegan por la URL y nada obliga a que vayan juntos."""
    autora = usuario_completo()
    una = crear_oportunidad(autora.id, titulo="Necesito un logo")
    otra = crear_oportunidad(autora.id, titulo="Necesito un sitio")
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    propuesta = crear_propuesta(otra.id, post.id)
    login(autora.id)

    client.post(f"/oportunidades/{una.id}/aceptar/{propuesta.id}")

    assert propuesta.aceptada is False
    assert una.estado == EstadosOportunidad.ABIERTA


def test_las_propuestas_solo_las_ve_quien_publico(
    client, login, usuario_completo, crear_usuario, crear_post,
    crear_oportunidad, crear_propuesta,
):
    """Si un emprendedor viera las demas, cotizar seria mirar el precio del
    otro."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    uno = crear_usuario(username="uno")
    post_uno = crear_post(uno.id, title="Estudio uno")
    crear_propuesta(
        oportunidad.id, post_uno.id, mensaje="Mi propuesta secreta",
    )
    otro = crear_usuario(username="otro")
    crear_post(otro.id, title="Estudio otro")

    login(otro.id)
    ajeno = client.get(f"/oportunidades/{oportunidad.id}").get_data(as_text=True)
    assert "Mi propuesta secreta" not in ajeno

    login(autora.id)
    propio = client.get(f"/oportunidades/{oportunidad.id}").get_data(as_text=True)
    assert "Mi propuesta secreta" in propio


# --------------------------------------------------- el unique de la aceptada

def test_la_base_no_deja_dos_propuestas_aceptadas(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    """El UNIQUE parcial, que es lo que tapa el doble click en "Aceptar".

    Sin el, los dos POST pasan el chequeo previo y aceptan los dos, y el
    publicador termina con dos emprendedores convencidos de que ganaron.
    """
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    uno = crear_usuario(username="uno")
    otro = crear_usuario(username="otro")
    post_uno = crear_post(uno.id, title="Estudio uno")
    post_otro = crear_post(otro.id, title="Estudio otro")
    primera = crear_propuesta(oportunidad.id, post_uno.id)
    segunda = crear_propuesta(oportunidad.id, post_otro.id)

    primera.aceptada = True
    db.session.commit()

    segunda.aceptada = True
    with pytest.raises(IntegrityError) as choque:
        db.session.commit()
    db.session.rollback()

    assert reglas.es_aceptada_duplicada(choque.value)


def test_dos_oportunidades_pueden_tener_cada_una_su_aceptada(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    """La contraprueba: el unique es por oportunidad, no global."""
    autora = usuario_completo()
    una = crear_oportunidad(autora.id, titulo="Necesito un logo")
    otra = crear_oportunidad(autora.id, titulo="Necesito un sitio")
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")

    for oportunidad in (una, otra):
        propuesta = crear_propuesta(oportunidad.id, post.id)
        propuesta.aceptada = True
        db.session.commit()

    assert Propuesta.query.filter_by(aceptada=True).count() == 2


def test_el_listener_deriva_cupo_aceptada(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    """cupo_aceptada no se toca a mano en ningun lado: sale de `aceptada`."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    propuesta = crear_propuesta(oportunidad.id, post.id)

    assert propuesta.cupo_aceptada is None

    propuesta.aceptada = True
    db.session.commit()
    assert propuesta.cupo_aceptada == 1

    propuesta.aceptada = False
    db.session.commit()
    assert propuesta.cupo_aceptada is None


# ----------------------------------------------------------------- consultas

def test_las_propuestas_se_agrupan_por_emprendimiento(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    """Tres propuestas de dos emprendimientos son dos grupos, no tres filas.

    En una lista plana por fecha, el que manda tres aparece tres veces y se lee
    como tres candidatos: insistir inflaria la presencia.
    """
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    uno = crear_usuario(username="uno")
    otro = crear_usuario(username="otro")
    post_uno = crear_post(uno.id, title="Estudio uno")
    post_otro = crear_post(otro.id, title="Estudio otro")

    crear_propuesta(oportunidad.id, post_uno.id, precio="30000")
    crear_propuesta(oportunidad.id, post_otro.id, precio="28000")
    ultima = crear_propuesta(oportunidad.id, post_uno.id, precio="24000")

    grupos = consultas.propuestas_de(oportunidad.id)

    assert len(grupos) == 2
    grupo_uno = next(g for g in grupos if g["post"].id == post_uno.id)
    # La mas nueva es la que se muestra; la vieja queda plegada.
    assert grupo_uno["ultima"].id == ultima.id
    assert len(grupo_uno["anteriores"]) == 1


def test_el_grupo_aceptado_va_primero(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    uno = crear_usuario(username="uno")
    otro = crear_usuario(username="otro")
    post_uno = crear_post(uno.id, title="Estudio uno")
    post_otro = crear_post(otro.id, title="Estudio otro")

    vieja = crear_propuesta(oportunidad.id, post_uno.id)
    crear_propuesta(oportunidad.id, post_otro.id)
    # Se acepta la MAS VIEJA, que sin el orden especial quedaria ultima.
    vieja.aceptada = True
    db.session.commit()

    grupos = consultas.propuestas_de(oportunidad.id)

    assert grupos[0]["post"].id == post_uno.id
    assert grupos[0]["aceptada"] is True


def test_el_conteo_de_propuestas_es_una_sola_consulta(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    autora = usuario_completo()
    una = crear_oportunidad(autora.id, titulo="Necesito un logo")
    otra = crear_oportunidad(autora.id, titulo="Necesito un sitio")
    vacia = crear_oportunidad(autora.id, titulo="Necesito tarjetas")
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")

    crear_propuesta(una.id, post.id)
    crear_propuesta(una.id, post.id, precio="20000")
    crear_propuesta(otra.id, post.id)

    conteo = consultas.conteo_de_propuestas([una.id, otra.id, vacia.id])

    assert conteo == {una.id: 2, otra.id: 1}
    # Sin ids no se le pregunta nada a la base: seria un IN () que ya sabemos
    # que no devuelve nada.
    assert consultas.conteo_de_propuestas([]) == {}


def test_borrar_al_autor_se_lleva_la_oportunidad_y_sus_propuestas(
    db, usuario_completo, crear_usuario, crear_post, crear_oportunidad,
    crear_propuesta,
):
    """ON DELETE CASCADE en las dos FK, que desde b2b97d078fb2 es la regla."""
    autora = usuario_completo()
    oportunidad = crear_oportunidad(autora.id)
    emprendedor = crear_usuario(username="disenio")
    post = crear_post(emprendedor.id, title="Estudio de diseño")
    crear_propuesta(oportunidad.id, post.id)

    db.session.delete(autora)
    db.session.commit()

    assert Oportunidad.query.count() == 0
    assert Propuesta.query.count() == 0


def test_el_listado_publico_solo_trae_abiertas(
    db, usuario_completo, crear_oportunidad,
):
    autora = usuario_completo()
    abierta = crear_oportunidad(autora.id, titulo="Abierta")
    crear_oportunidad(
        autora.id, titulo="Cerrada", estado=EstadosOportunidad.CERRADA,
    )
    crear_oportunidad(
        autora.id, titulo="Finalizada", estado=EstadosOportunidad.FINALIZADA,
    )

    assert [o.id for o in consultas.abiertas()] == [abierta.id]


def test_el_historial_trae_las_tres_con_las_abiertas_primero(
    db, usuario_completo, crear_oportunidad,
):
    autora = usuario_completo()
    finalizada = crear_oportunidad(
        autora.id, titulo="Finalizada", estado=EstadosOportunidad.FINALIZADA,
    )
    cerrada = crear_oportunidad(
        autora.id, titulo="Cerrada", estado=EstadosOportunidad.CERRADA,
    )
    abierta = crear_oportunidad(autora.id, titulo="Abierta")

    assert [o.id for o in consultas.de_usuario(autora.id)] == [
        abierta.id, cerrada.id, finalizada.id,
    ]


# -------------------------------------------------------------- presentacion

@pytest.mark.parametrize("dias,esperado", [
    (1, "1 día"),
    (3, "3 días"),
    (7, "1 semana"),
    (14, "2 semanas"),
    (10, "10 días"),
])
def test_el_plazo_se_lee_como_se_dice(dias, esperado):
    """La columna es un entero para comparar; esto es lo unico que sabe que
    "14" se dice "2 semanas"."""
    assert Propuesta(plazo_dias=dias).plazo_label == esperado
