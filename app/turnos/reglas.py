"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort, y ninguna toca la
base: devuelven un bool o un dato. Esa separacion es la que hace que el corte de
slots se pueda probar sin levantar ni un request ni una sesion de SQLAlchemy
(ver tests/test_turnos.py).
"""

# Como se reconoce el choque contra el UNIQUE de la doble reserva. Los dos
# motores dicen algo distinto: MySQL nombra la constraint ("Duplicate entry
# '3-2026-09-15-15:00:00-1' for key 'uq_turnos_slot_activo'") y SQLite no la
# nombra, lista las columnas ("UNIQUE constraint failed: turnos.service_id,
# turnos.fecha, ..."), asi que se buscan las dos formas. cupo_activo no
# participa de ninguna otra constraint, asi que alcanza para distinguirla.
#
# Son constantes propias y no una funcion generica con la tabla por parametro,
# por lo mismo que en app/servicios/reglas.py: el nombre de la tabla es
# justamente lo que distingue un choque del otro.
_CONSTRAINT_SLOT = "uq_turnos_slot_activo"
_COLUMNA_SLOT = "turnos.cupo_activo"


def es_slot_duplicado(error):
    """Si ese IntegrityError es el del UNIQUE de la doble reserva.

    Analoga a servicios.reglas.es_pendiente_duplicada, y se mira por el mismo
    motivo: un IntegrityError a secas tambien lo levanta, por ejemplo, la FK del
    servicio si el prestador lo borra justo en el medio, y ahi el cliente veria
    "ese horario ya lo tomo otra persona", que es mentira, y el error real se
    perderia sin dejar rastro.
    """
    texto = str(getattr(error, "orig", error))
    return _CONSTRAINT_SLOT in texto or _COLUMNA_SLOT in texto
