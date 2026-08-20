"""Las decisiones de negocio del dominio, sin saber que existe HTTP.

Ninguna funcion de aca usa request, flash, redirect ni abort: devuelven un bool
o un dato, y quien decide como se le cuenta eso al usuario es vistas.py.
"""

# Cuantos eventos ya vencidos se muestran en el desplegable del perfil.
MAX_EVENTOS_PASADOS = 5


def es_el_dueño(user, visitante):
    """Si quien mira el perfil es el dueño.

    De esto depende que se calculen o no las metricas y la lista de "Sigo a":
    son datos del dueño, con el mismo criterio de privacidad que views_count en
    un post. No se calculan cuando mira otro, asi que no hay forma de que se
    filtren por un error en el template.
    """
    return bool(visitante and visitante.id == user.id)


def puede_seguir(user, visitante):
    """Nadie se sigue a si mismo.

    No es solo cosmetico: sin esto queda una fila que hace que el usuario se
    vea a si mismo en su propia lista de "Sigo a".
    """
    return bool(visitante) and visitante.id != user.id


def horario_del_dia(cerrado, abre, cierra):
    """Como queda guardado un dia del panel de horarios: (cerrado, abre, cierra).

    Un dia sin horas cargadas se guarda como cerrado: deja la fila completa en
    vez de a medias, y el indicador de "abierto ahora" la lee igual.
    """
    cerrado = cerrado or not (abre and cierra)
    return cerrado, None if cerrado else abre, None if cerrado else cierra
