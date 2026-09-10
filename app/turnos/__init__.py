"""Turnos: reservar una hora concreta contra un servicio puntual.

Es el hermano del flujo de solicitudes de presupuesto (app/servicios/), y la
diferencia es de que se lleva el cliente: una solicitud termina en un precio y
una charla, un turno termina en una hora del reloj apartada para el. Por eso
vive en su propio paquete y no adentro de app/servicios/: comparte el Service
del que cuelga, pero no comparte ni el modelo, ni las reglas, ni las pantallas.

    reglas.py       las decisiones de negocio, sin saber que existe HTTP
                    (el corte de un rango en slots vive aca, y es pura
                    aritmetica de horas: no toca la base)
    consultas.py    todo lo que le pregunta a la base, incluida la que junta
                    el horario del dueño con los turnos ya tomados
    modelo_turno.py Turno

Todavia no hay vistas.py ni templates: esta tanda (2a) es la base de datos y el
calculo, y las pantallas vienen en la 2b.

DE DONDE SALE LA DISPONIBILIDAD: no hay un sistema de disponibilidad propio. Los
slots se cortan del Horario de atencion que el dueño del emprendimiento ya
cargo en su perfil (app/perfil/modelo_horario.py). Un turno no puede caer en una
hora en la que el local esta cerrado, y no hay dos lugares donde el vendedor
tenga que decir cuando atiende.

No reexporta nada, igual que app/servicios/ y app/perfil/ (ver el caso de
import circular documentado en app/servicios/__init__.py).
"""
