"""Busqueda de personal: el aviso, las postulaciones y la señal debil."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.personal import consultas, reglas
from app.personal.modelo_busqueda import BusquedaPersonal, Modalidades
from app.personal.modelo_postulacion import Postulacion
from models.message import Message


@pytest.fixture
def crear_busqueda(db):
    """Fabrica de avisos de busqueda."""

    def _crear(post_id, puesto="Ayudante de cocina",
               modalidad=Modalidades.PRESENCIAL,
               descripcion="Cuatro horas por la mañana.", activa=True):
        busqueda = BusquedaPersonal(
            post_id=post_id, puesto=puesto, modalidad=modalidad,
            descripcion=descripcion, activa=activa,
        )
        db.session.add(busqueda)
        db.session.commit()
        return busqueda

    return _crear


@pytest.fixture
def postulante(db, crear_usuario):
    """Un usuario con el perfil completo, o sea listo para postularse."""
    user = crear_usuario(username="postulante")
    user.phone = "2614445566"
    user.location = "Godoy Cruz"
    db.session.commit()
    return user


# ----------------------------------------------------------------- el modelo

def test_una_sola_busqueda_activa_por_emprendimiento(db, crear_usuario, crear_post,
                                                     crear_busqueda):
    """Lo garantiza la base y no la vista.

    El chequeo previo de la vista deja una ventana entre el SELECT y el INSERT:
    lo que de verdad cierra esa ventana es el UNIQUE(post_id, cupo_activa), y
    por eso se prueba contra la base directamente, sin pasar por HTTP.
    """
    user = crear_usuario()
    post = crear_post(user.id)
    crear_busqueda(post.id)

    with pytest.raises(IntegrityError):
        crear_busqueda(post.id, puesto="Otro puesto")
    db.session.rollback()


def test_se_pueden_acumular_busquedas_cerradas(db, crear_usuario, crear_post,
                                               crear_busqueda):
    """El unique es parcial: solo aplica a las activas.

    Si aplicara a todas, un emprendimiento no podria buscar personal dos veces
    en su vida.
    """
    user = crear_usuario()
    post = crear_post(user.id)
    crear_busqueda(post.id, puesto="Primera", activa=False)
    crear_busqueda(post.id, puesto="Segunda", activa=False)
    crear_busqueda(post.id, puesto="La abierta", activa=True)

    assert BusquedaPersonal.query.filter_by(post_id=post.id).count() == 3
    assert consultas.busqueda_activa_de(post.id).puesto == "La abierta"


def test_cupo_activa_lo_mantiene_el_listener(db, crear_usuario, crear_post,
                                             crear_busqueda):
    """Nadie escribe cupo_activa a mano: se deriva de `activa` en cada flush."""
    user = crear_usuario()
    post = crear_post(user.id)
    busqueda = crear_busqueda(post.id)
    assert busqueda.cupo_activa == 1

    busqueda.activa = False
    db.session.commit()
    assert busqueda.cupo_activa is None

    busqueda.activa = True
    db.session.commit()
    assert busqueda.cupo_activa == 1


def test_una_postulacion_por_persona_y_busqueda(db, crear_usuario, crear_post,
                                                crear_busqueda, postulante):
    user = crear_usuario(username="dueña")
    post = crear_post(user.id)
    busqueda = crear_busqueda(post.id)

    db.session.add(Postulacion(
        busqueda_id=busqueda.id, postulante_id=postulante.id,
        nombre="Ana", contacto="2614445566",
        experiencia="Dos años en cocina.", disponibilidad="Mañanas",
    ))
    db.session.commit()

    db.session.add(Postulacion(
        busqueda_id=busqueda.id, postulante_id=postulante.id,
        nombre="Ana", contacto="2614445566",
        experiencia="Otra cosa.", disponibilidad="Tardes",
    ))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# --------------------------------------------------------------- los largos

def test_la_descripcion_del_aviso_valida_su_largo(client, crear_usuario,
                                                  crear_post, login):
    """Contraprueba incluida: el tope justo pasa y uno mas corta.

    Sin la mitad de abajo, un validar_largo que rechazara TODO tambien pasaria
    este test. Es el patron de B1.
    """
    user = crear_usuario()
    post = crear_post(user.id)
    login(user.id)

    justo = "a" * reglas.MAX_DESCRIPCION
    respuesta = client.post(
        f"/personal/emprendimiento/{post.id}/buscar",
        data={"puesto": "Ayudante", "modalidad": Modalidades.PRESENCIAL,
              "descripcion": justo},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    busqueda = consultas.busqueda_activa_de(post.id)
    assert busqueda is not None and busqueda.descripcion == justo

    # Y uno mas no entra. Sobre OTRO emprendimiento, porque este ya tiene su
    # busqueda activa y el freno seria el otro.
    otro = crear_post(user.id, title="Otro emprendimiento")
    uno_mas = "a" * (reglas.MAX_DESCRIPCION + 1)
    respuesta = client.post(
        f"/personal/emprendimiento/{otro.id}/buscar",
        data={"puesto": "Ayudante", "modalidad": Modalidades.PRESENCIAL,
              "descripcion": uno_mas},
        follow_redirects=True,
    )
    assert "no puede tener más de" in respuesta.get_data(as_text=True)
    assert consultas.busqueda_activa_de(otro.id) is None


def test_el_puesto_valida_su_largo(client, crear_usuario, crear_post, login):
    user = crear_usuario()
    post = crear_post(user.id)
    login(user.id)

    respuesta = client.post(
        f"/personal/emprendimiento/{post.id}/buscar",
        data={"puesto": "a" * (reglas.MAX_PUESTO + 1),
              "modalidad": Modalidades.PRESENCIAL, "descripcion": "Corta."},
        follow_redirects=True,
    )
    assert "no puede tener más de" in respuesta.get_data(as_text=True)
    assert consultas.busqueda_activa_de(post.id) is None


def test_la_experiencia_valida_su_largo(client, crear_usuario, crear_post,
                                        crear_busqueda, postulante, login):
    """Los dos lados, igual que la descripcion: el tope justo entra."""
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)
    login(postulante.id)

    datos = {
        "nombre": "Ana", "contacto": "2614445566",
        "experiencia": "a" * (reglas.MAX_EXPERIENCIA + 1),
        "disponibilidad": "Mañanas",
    }
    respuesta = client.post(
        f"/personal/{busqueda.id}/postular", data=datos, follow_redirects=True,
    )
    assert "no puede tener más de" in respuesta.get_data(as_text=True)
    assert consultas.postulacion_de(busqueda.id, postulante.id) is None

    datos["experiencia"] = "a" * reglas.MAX_EXPERIENCIA
    client.post(
        f"/personal/{busqueda.id}/postular", data=datos, follow_redirects=True,
    )
    guardada = consultas.postulacion_de(busqueda.id, postulante.id)
    assert guardada is not None
    assert len(guardada.experiencia) == reglas.MAX_EXPERIENCIA


def test_los_topes_salen_de_las_columnas(db):
    """Si alguien agranda la columna, el tope la sigue sin tocar nada mas.

    Y si alguien la pasa a Text, largo_de devuelve None y esto lo agarra acá y
    no en el primer POST de produccion (H4).
    """
    assert reglas.MAX_DESCRIPCION == 500
    assert reglas.MAX_EXPERIENCIA == 600
    assert all(
        isinstance(tope, int)
        for tope in (
            reglas.MAX_PUESTO, reglas.MAX_DESCRIPCION, reglas.MAX_NOMBRE,
            reglas.MAX_CONTACTO, reglas.MAX_EXPERIENCIA,
            reglas.MAX_DISPONIBILIDAD,
        )
    )


# ------------------------------------------------------------------ permisos

def test_la_bandeja_es_solo_del_dueño(client, crear_usuario, crear_post,
                                      crear_busqueda, postulante, login):
    """Server-side y no CSS: el que no es dueño no ve los datos, ni escribiendo
    la URL a mano."""
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)
    db_postulacion = Postulacion(
        busqueda_id=busqueda.id, postulante_id=postulante.id,
        nombre="Ana Secreta", contacto="2614445566",
        experiencia="Dos años.", disponibilidad="Mañanas",
    )
    from db import db as _db
    _db.session.add(db_postulacion)
    _db.session.commit()

    login(postulante.id)
    respuesta = client.get(f"/personal/{busqueda.id}/postulantes",
                           follow_redirects=True)
    assert "Ana Secreta" not in respuesta.get_data(as_text=True)


def test_no_se_publica_una_busqueda_en_un_emprendimiento_ajeno(
    client, crear_usuario, crear_post, postulante, login
):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    login(postulante.id)

    client.post(
        f"/personal/emprendimiento/{post.id}/buscar",
        data={"puesto": "Ayudante", "modalidad": Modalidades.PRESENCIAL,
              "descripcion": "Lo que sea."},
        follow_redirects=True,
    )
    assert consultas.busqueda_activa_de(post.id) is None


def test_no_se_cierra_una_busqueda_ajena(client, crear_usuario, crear_post,
                                         crear_busqueda, postulante, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    login(postulante.id)
    client.post(f"/personal/{busqueda.id}/cerrar", follow_redirects=True)
    assert consultas.busqueda_activa_de(post.id) is not None


def test_el_dueño_no_se_postula_a_su_propio_aviso(client, db, crear_usuario,
                                                  crear_post, crear_busqueda,
                                                  login):
    dueña = crear_usuario(username="dueña")
    dueña.phone, dueña.location = "2614445566", "Mendoza"
    db.session.commit()
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    login(dueña.id)
    client.post(
        f"/personal/{busqueda.id}/postular",
        data={"nombre": "Yo", "contacto": "x", "experiencia": "y",
              "disponibilidad": "z"},
        follow_redirects=True,
    )
    assert consultas.postulacion_de(busqueda.id, dueña.id) is None


# --------------------------------------------------------- el perfil completo

def test_sin_telefono_ni_ubicacion_no_se_puede_postular(client, db, crear_usuario,
                                                        crear_post,
                                                        crear_busqueda, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    incompleto = crear_usuario(username="incompleto")
    login(incompleto.id)
    respuesta = client.post(
        f"/personal/{busqueda.id}/postular",
        data={"nombre": "Ana", "contacto": "x", "experiencia": "y",
              "disponibilidad": "z"},
        follow_redirects=True,
    )
    assert consultas.postulacion_de(busqueda.id, incompleto.id) is None
    texto = respuesta.get_data(as_text=True)
    assert "el teléfono" in texto and "la ubicación" in texto


def test_un_espacio_no_es_un_telefono(crear_usuario, db):
    """Vacio y NULL cuentan igual: "   " no completa el perfil."""
    user = crear_usuario(username="espacios")
    user.phone, user.location = "   ", "Mendoza"
    db.session.commit()
    assert reglas.perfil_completo(user) is False

    user.phone = "2614445566"
    db.session.commit()
    assert reglas.perfil_completo(user) is True


# ------------------------------------------------- cerrar, reabrir, postular

def test_cerrar_no_borra_las_postulaciones(client, db, crear_usuario, crear_post,
                                           crear_busqueda, postulante, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)
    db.session.add(Postulacion(
        busqueda_id=busqueda.id, postulante_id=postulante.id,
        nombre="Ana", contacto="2614445566",
        experiencia="Dos años.", disponibilidad="Mañanas",
    ))
    db.session.commit()

    login(dueña.id)
    client.post(f"/personal/{busqueda.id}/cerrar", follow_redirects=True)

    assert consultas.busqueda_activa_de(post.id) is None
    assert len(consultas.postulaciones_de(busqueda.id)) == 1
    assert BusquedaPersonal.query.get(busqueda.id).cerrada_at is not None


def test_reabrir_crea_una_fila_nueva_y_no_reactiva_la_vieja(
    client, db, crear_usuario, crear_post, crear_busqueda, postulante, login
):
    """El punto fino de todo el diseño.

    Si reabrir reactivara la fila cerrada, quien ya se habia postulado a la
    busqueda anterior quedaria bloqueado por el UNIQUE de postulaciones frente
    a un aviso que nunca vio, y el mensaje ademas le diria "ya te postulaste".
    Cerrar termina la vida de esa fila; lo que sigue es otra busqueda.
    """
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    vieja = crear_busqueda(post.id, puesto="Ayudante")
    db.session.add(Postulacion(
        busqueda_id=vieja.id, postulante_id=postulante.id,
        nombre="Ana", contacto="2614445566",
        experiencia="Dos años.", disponibilidad="Mañanas",
    ))
    db.session.commit()

    login(dueña.id)
    client.post(f"/personal/{vieja.id}/cerrar", follow_redirects=True)
    client.post(
        f"/personal/emprendimiento/{post.id}/buscar",
        data={"puesto": "Otro puesto", "modalidad": Modalidades.REMOTO,
              "descripcion": "Otra cosa."},
        follow_redirects=True,
    )

    nueva = consultas.busqueda_activa_de(post.id)
    assert nueva is not None
    assert nueva.id != vieja.id, "reabrir tiene que crear una fila nueva"
    assert BusquedaPersonal.query.get(vieja.id).activa is False

    # Y por eso el que ya se habia postulado puede postularse de nuevo.
    login(postulante.id)
    client.post(
        f"/personal/{nueva.id}/postular",
        data={"nombre": "Ana", "contacto": "2614445566",
              "experiencia": "Dos años.", "disponibilidad": "Mañanas"},
        follow_redirects=True,
    )
    assert consultas.postulacion_de(nueva.id, postulante.id) is not None


def test_no_se_puede_postular_a_una_busqueda_cerrada(client, crear_usuario,
                                                     crear_post, crear_busqueda,
                                                     postulante, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    cerrada = crear_busqueda(post.id, activa=False)

    login(postulante.id)
    client.post(
        f"/personal/{cerrada.id}/postular",
        data={"nombre": "Ana", "contacto": "x", "experiencia": "y",
              "disponibilidad": "z"},
        follow_redirects=True,
    )
    assert consultas.postulacion_de(cerrada.id, postulante.id) is None


def test_postularse_no_abre_ninguna_conversacion(client, crear_usuario,
                                                 crear_post, crear_busqueda,
                                                 postulante, login):
    """El chat lo abre el emprendedor cuando decide, no la postulacion."""
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    login(postulante.id)
    client.post(
        f"/personal/{busqueda.id}/postular",
        data={"nombre": "Ana", "contacto": "2614445566",
              "experiencia": "Dos años.", "disponibilidad": "Mañanas"},
        follow_redirects=True,
    )
    assert consultas.postulacion_de(busqueda.id, postulante.id) is not None
    assert Message.query.count() == 0


# --------------------------------------------------------------- la ficha

def test_la_seccion_aparece_y_desaparece_con_el_toggle(client, crear_usuario,
                                                       crear_post,
                                                       crear_busqueda, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id, puesto="Ayudante de cocina")

    assert "Ayudante de cocina" in client.get(f"/blog/{post.id}").get_data(as_text=True)

    login(dueña.id)
    client.post(f"/personal/{busqueda.id}/cerrar", follow_redirects=True)
    assert "Ayudante de cocina" not in client.get(f"/blog/{post.id}").get_data(as_text=True)


# ------------------------------------------------------------- la señal debil

def test_no_me_interesa_suma_uno_y_no_guarda_quien(client, crear_usuario,
                                                   crear_post, crear_busqueda,
                                                   postulante, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    login(postulante.id)
    client.post(f"/personal/{busqueda.id}/no-me-interesa", follow_redirects=True)

    assert BusquedaPersonal.query.get(busqueda.id).vistas_sin_postulacion == 1
    # La señal es anonima: no aparece ninguna fila con nombre.
    assert Postulacion.query.count() == 0


def test_no_me_interesa_pide_sesion(client, crear_usuario, crear_post,
                                    crear_busqueda):
    """Sin sesion el numero seria ruido puro: un bot o el propio emprendedor
    mirando su ficha lo inflarian sin costo, y estos numeros alimentan las
    metricas con las que despues se decide."""
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    busqueda = crear_busqueda(post.id)

    client.post(f"/personal/{busqueda.id}/no-me-interesa", follow_redirects=True)
    assert BusquedaPersonal.query.get(busqueda.id).vistas_sin_postulacion == 0


def test_una_busqueda_cerrada_no_suma_vistas(client, crear_usuario, crear_post,
                                             crear_busqueda, postulante, login):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    cerrada = crear_busqueda(post.id, activa=False)

    login(postulante.id)
    client.post(f"/personal/{cerrada.id}/no-me-interesa", follow_redirects=True)
    assert BusquedaPersonal.query.get(cerrada.id).vistas_sin_postulacion == 0


def test_el_contador_se_suma_en_la_base_y_no_en_python(db, crear_usuario,
                                                       crear_post,
                                                       crear_busqueda):
    """Dos incrementos seguidos sobre un objeto con el valor viejo en memoria.

    Si el +1 se resolviera leyendo en Python, el segundo pisaria al primero y
    el contador quedaria en 1. Con el UPDATE atomico queda en 2, que es lo que
    se prueba: el que resuelve la suma es el motor.
    """
    user = crear_usuario()
    post = crear_post(user.id)
    busqueda = crear_busqueda(post.id)
    # El id aparte: despues del expunge_all el objeto queda desprendido de la
    # sesion y leerle cualquier atributo intenta refrescarlo y explota.
    busqueda_id = busqueda.id

    consultas.contar_vista_sin_postulacion(busqueda_id)
    consultas.contar_vista_sin_postulacion(busqueda_id)

    # Sin vaciar el identity map, lo que se lee abajo es el objeto que ya esta
    # en memoria y no lo que quedo en la base.
    db.session.expunge_all()
    assert BusquedaPersonal.query.get(busqueda_id).vistas_sin_postulacion == 2


# ------------------------------------------------------------- el conteo

def test_el_conteo_agrupado_cuenta_por_busqueda(db, crear_usuario, crear_post,
                                                crear_busqueda):
    dueña = crear_usuario(username="dueña")
    post = crear_post(dueña.id)
    una = crear_busqueda(post.id, puesto="Una", activa=False)
    otra = crear_busqueda(post.id, puesto="Otra")

    for i in range(3):
        persona = crear_usuario(username=f"gente{i}")
        db.session.add(Postulacion(
            busqueda_id=una.id, postulante_id=persona.id,
            nombre=f"P{i}", contacto="x", experiencia="y", disponibilidad="z",
        ))
    db.session.commit()

    conteo = consultas.conteo_de_postulaciones([una.id, otra.id])
    assert conteo == {una.id: 3}
    assert conteo.get(otra.id, 0) == 0


def test_el_conteo_vacio_no_consulta(db):
    """Sin ids seria un `IN ()`: una consulta que ya sabemos que no devuelve
    nada. La bandeja vacia es un caso normal."""
    assert consultas.conteo_de_postulaciones([]) == {}
