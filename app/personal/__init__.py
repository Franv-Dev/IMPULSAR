"""Busqueda de personal: un emprendimiento que busca a alguien para trabajar.

Es el tercer flujo que cuelga de un emprendimiento, despues de las solicitudes
de presupuesto (app/servicios/) y los turnos (app/turnos/), y como esos dos vive
en su propio paquete: comparte el Post del que cuelga, pero no comparte ni el
modelo, ni las reglas, ni las pantallas.

    reglas.py            las decisiones, sin saber que existe HTTP
    consultas.py         todo lo que le pregunta a la base
    formulario.py        la frontera con request.form
    modelo_busqueda.py   BusquedaPersonal (el aviso, con su toggle)
    modelo_postulacion.py Postulacion (lo que manda el que se postula)

DOS TABLAS Y NO CUATRO COLUMNAS EN posts: apagar el toggle y volver a
prenderlo no puede pisar el aviso anterior, y cada postulacion tiene que
apuntar a una busqueda PUNTUAL. Por eso reabrir crea una fila nueva y nunca
reactiva la vieja -- ver el docstring de BusquedaPersonal, que es donde esa
decision tiene consecuencias.

EL CHAT NO ES DE ACA. La conversacion entre el emprendedor y el postulante ya
existe como concepto: se identifica por (post_id, client_id) en messages, asi
que "Abrir chat" es un enlace a messages.conversation y no una tabla nueva. El
hilo aparece cuando alguien escribe, que es por lo que postularse no crea
ninguna conversacion.

No reexporta nada, igual que el resto de los paquetes de app/ (ver el caso de
import circular documentado en app/servicios/__init__.py).
"""
