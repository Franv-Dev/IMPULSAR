"""Freno de intentos fallidos, para que un login no se pueda probar a fuerza bruta.

Cuenta fallos por clave y, pasado un maximo, bloquea esa clave un rato. Lo usa
el login (los dos, el de formulario y el de la API); no esta atado a ellos, la
clave es un string cualquiera que arma quien llama.

POR QUE A MANO Y NO Flask-Limiter
---------------------------------
Flask-Limiter es la opcion estandar y lo primero que se evaluo, pero limita
REQUESTS por ventana, no FALLOS consecutivos: con `@limit("6/10minutes")` el
sexto login del dia se rechaza aunque los cinco anteriores hayan sido
correctos, que es exactamente lo que no se quiere (molesta al usuario legitimo
y no frena mas al atacante). Se puede acomodar con `deduct_when=`, pero para
ese punto lo que queda de la libreria es un contador con ventana, que es lo que
hay aca en cincuenta lineas. Sumado a eso: el proyecto pinea hasta las
dependencias indirectas en requirements.txt (Flask-Limiter arrastra `limits` y
`deprecated`), y el "reset al login exitoso" tampoco viene de fabrica. La
decision es reversible: si algun dia hacen falta limites por endpoint en toda
la app, ahi Flask-Limiter gana y este modulo se tira.

LIMITACION CONOCIDA: EL ESTADO ES DEL PROCESO
---------------------------------------------
El contador vive en un diccionario en memoria. Con varios workers (gunicorn -w
4, por ejemplo) cada uno lleva el suyo, asi que el limite efectivo se multiplica
por la cantidad de workers: cinco fallos pasan a ser veinte antes del primer
bloqueo. Sigue cortando la fuerza bruta (que necesita miles de intentos, no
veinte), pero no es exacto. El dia que el deploy tenga mas de un worker, lo que
cambia es este modulo y nada mas: las funciones de abajo son la unica puerta, y
detras puede haber igual de bien un Redis compartido.
"""

import threading
import time

# clave -> lista de instantes (monotonicos) en que fallo. Se poda sola: los
# fallos mas viejos que la ventana se descartan al consultarla, y la clave
# entera se borra cuando se cumple el bloqueo.
_fallos = {}

# El diccionario lo tocan varios hilos a la vez (el servidor de desarrollo es
# threaded, y gunicorn con hilos tambien): sin el lock, dos requests
# simultaneas pueden leer y escribir la misma lista y perderse un fallo.
_candado = threading.Lock()

# Tope de claves vivas, para que una fuerza bruta con IPs rotativas no haga
# crecer el diccionario sin fin. Al pasarse se podan las claves ya vencidas, y
# si aun asi no baja se descartan las mas viejas: perder un contador viejo es
# aceptable, quedarse sin memoria no.
MAXIMO_DE_CLAVES = 10_000


def _podar(clave, ventana, ahora):
    """Deja en la clave solo los fallos de la ventana. Devuelve esa lista.

    Se llama con el candado tomado.
    """
    recientes = [t for t in _fallos.get(clave, ()) if ahora - t < ventana]
    if recientes:
        _fallos[clave] = recientes
    else:
        _fallos.pop(clave, None)
    return recientes


def segundos_de_bloqueo(clave, maximo, bloqueo, ventana):
    """Cuantos segundos faltan para que `clave` pueda volver a intentar.

    Cero si esta libre. Se consulta ANTES de verificar la contrasenia: asi un
    bloqueado ni siquiera paga el hash, que es lo unico que hoy le pone precio
    al ataque.
    """
    ahora = time.monotonic()
    # La ventana que se usa para podar nunca puede ser mas corta que el
    # bloqueo. Si lo fuera, los fallos se olvidarian antes de que la espera
    # termine y el bloqueo se levantaria solo: medido, con bloqueo=60 y
    # ventana=1 la clave decia 60 segundos y 1,2 segundos despues decia 0. Hoy
    # config.py los pone 600 y 900, pero eso es una convencion que nadie
    # sostiene; asi la invariante la sostiene la funcion.
    ventana = max(ventana, bloqueo)
    with _candado:
        recientes = _podar(clave, ventana, ahora)
        if len(recientes) < maximo:
            return 0

        # El bloqueo corre desde el ultimo fallo, no desde el primero.
        restante = bloqueo - (ahora - recientes[-1])
        if restante <= 0:
            # Cumplida la espera se arranca de cero, y no con el contador al
            # borde: si no, el primer fallo despues del bloqueo volveria a
            # bloquear enseguida y la cuenta quedaria practicamente muerta.
            _fallos.pop(clave, None)
            return 0

        # Hacia arriba: devolver 0.4 segundos como "0" diria "ya podes" cuando
        # todavia no.
        return int(restante) + 1


def registrar_fallo(clave, ventana):
    """Anota un intento fallido de `clave`."""
    ahora = time.monotonic()
    with _candado:
        recientes = _podar(clave, ventana, ahora)
        _fallos[clave] = recientes + [ahora]
        if len(_fallos) > MAXIMO_DE_CLAVES:
            _limitar_tamanio(ventana, ahora)


def _limitar_tamanio(ventana, ahora):
    """Poda el diccionario cuando se pasa de MAXIMO_DE_CLAVES.

    Se llama con el candado tomado.
    """
    vencidas = [c for c, ts in _fallos.items() if ahora - ts[-1] >= ventana]
    for clave in vencidas:
        del _fallos[clave]

    if len(_fallos) > MAXIMO_DE_CLAVES:
        # Todavia sobra: se van las de fallo mas viejo, que son las que menos
        # probablemente sigan bajo ataque.
        por_antiguedad = sorted(_fallos, key=lambda c: _fallos[c][-1])
        for clave in por_antiguedad[: len(_fallos) - MAXIMO_DE_CLAVES]:
            del _fallos[clave]


def limpiar(clave):
    """Borra el contador de `clave`. Se llama cuando el intento salio bien."""
    with _candado:
        _fallos.pop(clave, None)


def reiniciar():
    """Vacia todo. Para los tests, que si no se contagian entre si."""
    with _candado:
        _fallos.clear()
