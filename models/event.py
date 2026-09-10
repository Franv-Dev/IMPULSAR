from db import db, utcnow


class TiposEvento:
    """Los cuatro tipos de evento que la cartelera deja filtrar.

    Strings en un solo lugar, igual que Categorias en modelo_post.py y Roles en
    models/user.py: no se repiten sueltos por vistas y plantillas.

    LA TAXONOMIA ES CERRADA Y ESO ES LO CARO, no la columna: una vez que hay
    eventos etiquetados, agregar o partir un tipo obliga a re-etiquetar lo
    cargado, y sacarlo deja filas apuntando a un valor que ya no existe. Los
    cuatro salen del canvas de disenio-eventos/ y se decidieron con Tomas antes
    de escribir la migracion.

    NO HAY "otros", al reves que Categorias. Un emprendimiento siempre es de
    algun rubro aunque no encaje, asi que ahi el cajon de sastre tiene sentido;
    un evento que no es ninguna de estas cuatro cosas no existe todavia, y
    ofrecer "Otros" desde el dia uno garantiza que la mitad caiga ahi y que la
    taxonomia no sirva para filtrar, que es justamente para lo que esta.
    """

    FERIA = "feria"
    TALLER = "taller"
    POPUP = "popup"
    ENCUENTRO = "encuentro"

    TODOS = (FERIA, TALLER, POPUP, ENCUENTRO)

    ETIQUETAS = {
        FERIA: "Feria",
        TALLER: "Taller",
        POPUP: "Pop-up",
        ENCUENTRO: "Encuentro",
    }


class Event(db.Model):
    """Un evento o feria que un emprendimiento anuncia.

    Es informacion con fecha, no una reserva: no hay cupo, ni inscripcion, ni
    disponibilidad. Un cartel que dice "el sabado estamos en la feria de la
    plaza".

    La fecha es hora local de Argentina, igual que los horarios de atencion y
    por la misma razon: una feria es "el sabado a las 10" en el reloj de la
    puerta del local, no un instante en UTC (ver services/eventos.py). Por eso
    `fecha` es Date y no DateTime, y la hora va aparte.
    """

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" a nivel de base y no solo en el ORM: en MySQL el
    # default es RESTRICT y borrar un emprendimiento con eventos cargados
    # fallaria con IntegrityError. Es el mismo bug que ya aparecio en reports,
    # favorites, messages y post_images (ver migraciones d09128dd029c,
    # b30b4ba8d199 y c8a4f1e07d36).
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    titulo = db.Column(db.String(120), nullable=False)
    # Corta a proposito: es lo que entra en una tarjeta de la cartelera, no la
    # descripcion larga del emprendimiento.
    descripcion = db.Column(db.String(300), nullable=True)
    # Indexada porque todas las consultas filtran y ordenan por fecha (los
    # proximos del perfil y la cartelera de /eventos).
    fecha = db.Column(db.Date, nullable=False, index=True)
    # Opcional: "la feria es el sabado" es un evento valido sin hora.
    hora = db.Column(db.Time, nullable=True)
    # Donde es. Texto libre y no una direccion estructurada (ni lat/lng, ni
    # relacion a nada): lo que se anuncia es "Plaza San Martin" o "el patio de
    # la escuela", no un domicilio que haya que geocodificar.
    #
    # Columna propia y NO heredada de Post.address_street a proposito: la feria
    # de una panaderia normalmente no es en la panaderia. Mostrar la direccion
    # del emprendimiento como lugar del evento seria un dato equivocado con
    # cara de dato real, que es peor que no tenerlo.
    #
    # Nullable porque los eventos que ya estaban cargados no tienen lugar y no
    # hay de donde sacarselo: cuando falta, la tarjeta no muestra la linea.
    lugar = db.Column(db.String(120), nullable=True)
    # Que clase de evento es (ver TiposEvento). Indexada porque la cartelera
    # filtra por esto, igual que fecha.
    #
    # NULLABLE, y no con un default: los eventos que ya estaban cargados NO
    # tienen tipo y no hay de donde sacarselo. Ponerles "feria" a todos seria
    # etiquetar de mentira lo que quiza era un taller, que es peor que no
    # etiquetarlo: NULL se lee como "no lo dijo" y la tarjeta no dibuja el chip.
    # El formulario si lo pide para los nuevos, asi que el NULL se agota solo.
    tipo = db.Column(db.String(20), nullable=True, index=True)
    # Si se entra sin pagar. Booleano y no un precio: lo que la cartelera
    # necesita responder es "¿puedo pasar sin plata?", no cuanto sale.
    #
    # NOT NULL con default False, al reves que `tipo`, y la asimetria es a
    # proposito: el chip solo se dibuja cuando es True, asi que False no afirma
    # nada -- es "no dice" -- mientras que un tipo equivocado si afirma algo
    # falso. Marcarle "entrada libre" a un taller pago, en cambio, seria
    # prometer gratis lo que se cobra.
    entrada_libre = db.Column(
        db.Boolean, nullable=False, default=False, server_default="0"
    )
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"<Event post_id={self.post_id} {self.fecha} {self.titulo}>"

    @property
    def tipo_label(self):
        """"Feria", o cadena vacia si el evento no tiene tipo cargado.

        Vacia y no "Otros": un evento viejo sin tipo no es de un quinto tipo,
        simplemente no se sabe. Quien lo dibuja pregunta por el valor y decide
        si pone el chip. Mismo criterio que Post.category_label, salvo que ahi
        el default no puede faltar.
        """
        return TiposEvento.ETIQUETAS.get(self.tipo, "")

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora": self.hora.strftime("%H:%M") if self.hora else None,
            "lugar": self.lugar,
            "tipo": self.tipo,
            "tipo_label": self.tipo_label,
            "entrada_libre": self.entrada_libre,
        }
