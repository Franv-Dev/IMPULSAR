"""Que significa que un perfil este "completo" para participar de algo.

Vive en services/ y no en un dominio porque lo preguntan dos: la busqueda de
personal (para postularse, app/personal/) y las oportunidades (para publicar
una, app/oportunidades/). Es una sola regla y tiene que tener una sola
definicion: duplicada, alcanza con que alguien sume un campo en un lado para
que los dos flujos pidan cosas distintas por el mismo motivo, y el que pide de
menos no avisa nunca -- es el mismo problema que ya costo caro cuando la misma
regla vivia en dos archivos.
"""

# Telefono y ubicacion, y no el perfil entero: son los dos datos sin los cuales
# del otro lado no se puede contestar ni saber si sirve por distancia. Pedir
# mas (bio, avatar, redes) seria un peaje que no ayuda a la decision.
CAMPOS_DE_PERFIL_COMPLETO = ("phone", "location")

# Como se nombra cada campo cuando hay que decirle a alguien que le falta. Va
# con articulo porque el mensaje lo concatena ("completá el teléfono y la
# ubicación").
ETIQUETAS_DE_PERFIL = {"phone": "el teléfono", "location": "la ubicación"}


def perfil_completo(user):
    """Si esa persona tiene lo minimo cargado.

    Vacio y NULL cuentan igual: un telefono que es "   " no es un telefono. Por
    eso se compara el strip() y no la presencia de la columna.
    """
    if user is None:
        return False
    return all(
        (getattr(user, campo, None) or "").strip()
        for campo in CAMPOS_DE_PERFIL_COMPLETO
    )


def falta_de_perfil(user):
    """Que campos le faltan, para poder decirselo con nombre y no en general.

    "Completá tu perfil" obliga a ir a buscar que falta; "completá el teléfono"
    se resuelve de una.
    """
    return [
        ETIQUETAS_DE_PERFIL[campo]
        for campo in CAMPOS_DE_PERFIL_COMPLETO
        if not (getattr(user, campo, None) or "").strip()
    ]
