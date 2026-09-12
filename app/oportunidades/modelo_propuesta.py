from db import db, utcnow

# Tope de plazo_dias. Un año es la red de abajo y no la validacion: el mensaje
# entendible lo da el formulario, esto ataja lo que no pase por ahi.
MAX_PLAZO_DIAS = 365


class Propuesta(db.Model):
    """Lo que ofrece un emprendimiento sobre una oportunidad.

    Tres datos y un mensaje corto: precio, plazo y por que. Alcanza para
    decidir a quien abrirle el chat, que es todo lo que esta pantalla tiene que
    resolver.

    LA MANDA UN EMPRENDIMIENTO, NO UN USUARIO. Por eso la columna es post_id y
    no propone_id, igual que Service: quien propone es el emprendimiento, que
    es lo que el publicador va a mirar para decidir (nombre, ficha, reseñas).
    El permiso se resuelve con post.author, que es la misma pregunta de
    siempre. De ahi sale tambien la asimetria del dominio: publicar una
    oportunidad lo puede hacer cualquier usuario con el perfil completo, pero
    proponer solo alguien que tenga un emprendimiento.

    VARIAS PROPUESTAS DEL MISMO EMPRENDIMIENTO ESTAN PERMITIDAS, a diferencia
    de Postulacion, que tiene un UNIQUE (busqueda_id, postulante_id). No es un
    olvido: "hablamos por chat y te bajo el precio" es el caso real, y una
    segunda propuesta es informacion nueva, no un duplicado. Lo que se hace con
    eso es de presentacion (ver consultas.propuestas_de), no de la base.

    UNA SOLA ACEPTADA A LA VEZ, y lo garantiza la base y no la vista: el UNIQUE
    es (oportunidad_id, cupo_aceptada), donde cupo_aceptada vale 1 mientras la
    propuesta esta aceptada y NULL cuando no. En los dos motores un UNIQUE
    ignora las filas con NULL, asi que la regla aplica solo a la aceptada y las
    demas pueden ser todas las que hagan falta. Es el mismo unique parcial
    portable de service_requests.cupo_pendiente y busquedas_personal.cupo_activa,
    reusado por tercera vez y no reinventado.

    Lo que tapa es concreto: sin el, el doble click en "Aceptar" manda dos POST
    que pasan los dos el chequeo previo y aceptan los dos, y el publicador
    termina con dos emprendedores convencidos de que ganaron.
    """

    __tablename__ = "propuestas"

    __table_args__ = (
        # Ver "UNA SOLA ACEPTADA A LA VEZ" en el docstring.
        db.UniqueConstraint(
            "oportunidad_id", "cupo_aceptada", name="uq_propuestas_aceptada",
        ),
        # Mismo criterio que el resto de los precios del proyecto. Aca no
        # admite NULL, al reves que el presupuesto de la oportunidad: una
        # propuesta sin precio no se puede comparar con otra, que es lo unico
        # que esta pantalla tiene que hacer.
        db.CheckConstraint("precio > 0", name="ck_propuestas_precio_positivo"),
        db.CheckConstraint(
            "plazo_dias > 0 AND plazo_dias <= 365",
            name="ck_propuestas_plazo_razonable",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    oportunidad_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "oportunidades.id", ondelete="CASCADE",
            name="fk_propuestas_oportunidad_id_oportunidades",
        ),
        nullable=False, index=True,
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "posts.id", ondelete="CASCADE",
            name="fk_propuestas_post_id_posts",
        ),
        nullable=False, index=True,
    )

    precio = db.Column(db.Numeric(10, 2), nullable=False)
    # ENTERO Y NO TEXTO LIBRE, que es la decision menos obvia del modelo. El
    # sentido de esta pantalla es comparar propuestas entre si, y con texto
    # libre no se comparan: "2 semanas", "15 dias" y "quincena" son la misma
    # oferta y ni se ordenan ni se leen juntas. Un entero se ordena, se formatea
    # para mostrar, y de paso no tiene el problema de largo_de() sobre Text.
    # El costo es obligar a pensar en dias, que al lado de una columna que
    # promete comparacion y no la da es barato.
    plazo_dias = db.Column(db.Integer, nullable=False)
    # String(600) y no Text, por lo mismo que el resto de los textos del
    # proyecto: sobre el corre validar_largo (H4).
    mensaje = db.Column(db.String(600), nullable=False)

    aceptada = db.Column(
        db.Boolean, nullable=False, default=False, server_default="0", index=True,
    )
    # Vale 1 si aceptada, y NULL si no. No se toca a mano en ningun lado: lo
    # mantiene el listener de abajo, igual que cupo_activa y cupo_pendiente,
    # para que no pueda quedar desincronizado de `aceptada`.
    cupo_aceptada = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    # cascade="all, delete-orphan" del lado de la oportunidad: la FK ya borra en
    # la base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # oportunidad_id en NULL cuando se borra una Oportunidad desde la sesion, y
    # la columna es NOT NULL. Mismo caso que postulaciones, imagenes y eventos.
    oportunidad = db.relationship(
        "Oportunidad",
        backref=db.backref("propuestas", cascade="all, delete-orphan"),
    )
    # Del lado del post tambien cascadea en el ORM, por lo mismo: borrar un
    # emprendimiento se lleva las propuestas que mando.
    post = db.relationship(
        "Post",
        backref=db.backref("propuestas", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        estado = "aceptada" if self.aceptada else "pendiente"
        return (
            f"<Propuesta oportunidad_id={self.oportunidad_id} "
            f"post_id={self.post_id} {estado}>"
        )

    @property
    def plazo_label(self):
        """El plazo como se lee, no como se guarda.

        La columna es un entero para poder comparar y ordenar; esto es lo unico
        que sabe que "14" se dice "2 semanas". Vive en el modelo y no en el
        template porque lo muestran tres pantallas.
        """
        dias = self.plazo_dias
        if dias is None:
            return ""
        if dias >= 7 and dias % 7 == 0:
            semanas = dias // 7
            return "1 semana" if semanas == 1 else f"{semanas} semanas"
        return "1 día" if dias == 1 else f"{dias} días"

    def serialize(self):
        return {
            "id": self.id,
            "oportunidad_id": self.oportunidad_id,
            "post_id": self.post_id,
            # str y no float, por lo mismo que el resto de los precios.
            "precio": str(self.precio) if self.precio is not None else None,
            "plazo_dias": self.plazo_dias,
            "plazo_label": self.plazo_label,
            "mensaje": self.mensaje,
            "aceptada": self.aceptada,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@db.event.listens_for(Propuesta, "before_insert")
@db.event.listens_for(Propuesta, "before_update")
def _sincronizar_cupo_aceptada(mapper, connection, target):
    """Deriva cupo_aceptada de aceptada antes de cada INSERT y cada UPDATE.

    Va aca y no en cada vista que acepta o reabre: la columna solo existe para
    sostener el UNIQUE, y si mañana aparece otro lugar donde una propuesta
    cambia de estado y se olvida de actualizarla, el freno de la unica aceptada
    se cae en silencio. Es el mismo listener, y por el mismo motivo, que
    _sincronizar_cupo_pendiente y _sincronizar_cupo_activa.

    Cubre los cambios que pasan por el ORM, que hoy son todos: los eventos de
    mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), SQL crudo) no los dispara. Lo que no cambia es la
    garantia: la da el UNIQUE de la base, no este listener.

    El `is None` es porque los defaults de columna se aplican DESPUES de este
    evento: una propuesta creada sin pasar `aceptada` todavia la tiene en None
    aca, y su default es False.
    """
    if target.aceptada is None:
        target.aceptada = False
    target.cupo_aceptada = 1 if target.aceptada else None
