"""Oportunidades: alguien que necesita un servicio y lo pide en publico.

Es el primer flujo del proyecto que NO cuelga de un emprendimiento. Las
solicitudes de presupuesto (app/servicios/), los turnos (app/turnos/) y las
busquedas de personal (app/personal/) arrancan todas en la ficha de un Post:
esta arranca en un usuario cualquiera y la ve todo el mundo.

    reglas.py             las decisiones, sin saber que existe HTTP
    consultas.py          todo lo que le pregunta a la base
    formulario.py         la frontera con request.form
    modelo_oportunidad.py Oportunidad (la necesidad publicada, con su estado)
    modelo_propuesta.py   Propuesta (lo que ofrece un emprendimiento)

SE LLAMA Oportunidad Y NO Solicitud: "solicitud" ya es ServiceRequest, el
pedido privado de presupuesto sobre un servicio puntual. Dos cosas parecidas
con el mismo nombre en el mismo codigo se confunden una sola vez y para
siempre.

LOS PERMISOS SON ASIMETRICOS y es lo que mas se olvida leyendo este paquete:
publicar una oportunidad lo puede hacer cualquier usuario con el perfil
completo (telefono y ubicacion, el mismo criterio que postularse, definido una
sola vez en services/perfiles.py); mandar una propuesta solo alguien que tenga
un emprendimiento, y la manda desde ese emprendimiento. Pedir un servicio no
requiere ser nadie; ofrecerlo si.

TRES ESTADOS Y NO UN BOOLEANO. abierta recibe propuestas; cerrada ya eligio
pero se desanda; finalizada se termino y no vuelve. La diferencia entre las dos
ultimas es toda la gracia, y esta en el docstring de Oportunidad junto con por
que alcanzan una columna y dos timestamps sin tabla de log.

EL CHAT NO ES DE ACA. La conversacion ya se identifica por (post_id, client_id)
en messages, asi que aceptar una propuesta redirige a messages.conversation y
no crea ninguna tabla ni ningun mensaje: el hilo aparece cuando alguien
escribe.

No reexporta nada, igual que el resto de los paquetes de app/ (ver el caso de
import circular documentado en app/servicios/__init__.py).
"""
