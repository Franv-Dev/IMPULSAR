"""Borra del disco la foto de una fila que se borro de la base.

Existe porque hasta ahora nada limpiaba el archivo. Las cuatro llamadas a
borrar_de_disco que hay en vistas.py son todas de rollback -- deshacen lo que
escribio un intento que despues fallo -- y ninguna cubre el borrado de una fila
que ya estaba guardada. El caso peor no es el borrado directo sino la cascada:
borrar un Post se lleva sus Service, y cada Service se lleva sus ServiceRequest
y VerificationRequest, sin que ninguna vista se entere de que habia fotos.

POR QUE UN EVENTO DEL ORM Y NO UNA LLAMADA EN CADA VISTA. Justamente por la
cascada: las filas que se borran ahi nunca pasan por una vista de este dominio.
Registrarlo en el modelo hace que valga para cualquier camino que use el ORM
-- borrado directo, cascada desde Service, cascada desde Post, cascada desde
User -- sin que quien escriba la proxima vista tenga que acordarse.

LIMITE CONOCIDO Y ACEPTADO: un evento de mapper corre cuando el ORM procesa la
instancia en el flush, asi que NO se dispara con SQL crudo (un
"DELETE FROM service_requests ...", un Query.delete() masivo, un DELETE hecho a
mano en el cliente de MySQL) ni con la cascada del motor (ON DELETE CASCADE
resolviendo la FK del lado de la base sin que el ORM cargue la fila). En esos
casos el archivo queda huerfano igual que antes. Es la misma limitacion que ya
se documento para clave_pendiente en app/blog/modelo_reporte.py, y la misma
distincion que quedo a la vista con reviews.post_id: lo que el ORM garantiza no
es lo que garantiza la base. Cubrirlo de verdad pediria un trigger en el motor,
que es otro alcance; hoy todos los borrados de estas tablas pasan por el ORM.

POR QUE NO SE BORRA EN EL after_delete MISMO. after_delete corre durante el
flush, y un flush todavia se puede deshacer: si la transaccion hace rollback
mas adelante, la fila vuelve y el archivo ya no esta. Es el problema simetrico
del huerfano y molesta mas, porque deja una fila apuntando a la nada. Por eso el
evento de la instancia solo ANOTA el nombre, y el borrado real se hace en el
after_commit de la sesion, cuando ya no hay vuelta atras. Si en el medio hay un
rollback, la lista se descarta y el archivo se queda donde estaba.
"""

from flask import current_app
from sqlalchemy import event
from sqlalchemy.orm import Session

from db import db
from services.uploads import borrar_de_disco, carpeta_privada


# Las fotos anotadas por el flush de cada sesion, esperando a que confirme.
# Va contra la Session y no en una variable de modulo porque dos requests
# concurrentes tienen sesiones distintas y no se tienen que pisar la lista.
_PENDIENTES = "_fotos_a_borrar_al_confirmar"


def _anotar(session, nombre):
    if nombre:
        session.info.setdefault(_PENDIENTES, []).append(nombre)


def registrar(modelo):
    """Engancha el borrado de la foto al after_delete de ese modelo.

    Se llama desde el modulo del modelo, abajo de la clase, que es donde ya
    vive el otro listener del paquete (_sincronizar_clave_pendiente en
    modelo_reporte.py).
    """

    @event.listens_for(modelo, "after_delete")
    def _anotar_la_foto(mapper, connection, target):  # noqa: ARG001
        _anotar(db.session, target.foto)

    return modelo


@event.listens_for(Session, "after_commit")
def _borrar_las_anotadas(session):
    """Ya no hay vuelta atras: se van los archivos de las filas que se fueron."""
    nombres = session.info.pop(_PENDIENTES, None)
    if not nombres:
        return

    # carpeta_privada() lee la config, asi que necesita contexto de app. Un
    # commit siempre ocurre dentro de uno (request o script con app_context),
    # pero si alguien confirma fuera de contexto, perder el archivo es mejor
    # que romperle el commit: ya esta hecho y no se puede deshacer.
    if not current_app:
        return
    borrar_de_disco(carpeta_privada(), nombres)


@event.listens_for(Session, "after_rollback")
@event.listens_for(Session, "after_soft_rollback")
def _olvidar_las_anotadas(session, previous_transaction=None):  # noqa: ARG001
    """Se deshizo el borrado de las filas, asi que las fotos se quedan."""
    session.info.pop(_PENDIENTES, None)
