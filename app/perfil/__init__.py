"""El perfil publico de un usuario y lo que cuelga de el.

Junta cuatro cosas que en la pantalla son una sola: la portada del emprendedor
(bio, contacto, foto, sus emprendimientos y sus eventos), sus horarios de
atencion, el seguir/dejar de seguir, y el listado de reseñas que recibio.

    vistas.py           las rutas (HTTP: request, flash, redirect, render)
    reglas.py           las decisiones de negocio, sin saber que existe HTTP
    consultas.py        todo lo que le pregunta a la base
    formulario.py       parseo y validacion de lo que manda el navegador
    modelo_horario.py   Horario   (era models/horario.py)
    modelo_follow.py    Follow    (era models/follow.py)
    templates/          profile.html y profile/*.html

User NO vive aca, y no es un olvido: es el modelo de la identidad, lo usan auth,
admin, mensajeria y medio proyecto, y el perfil es una de las cosas que se le
cuelgan, no su dueño. Le corresponde al dominio de cuentas, cuando exista.

No reexporta nada, ni el blueprint. Es la regla dura del proyecto mientras
models/post.py siga en la raiz importando modelos de app/: reexportar aca hace
que importar un modelo del paquete arrastre las vistas, que importan consultas,
que importan models.post, que esta a medio ejecutar. El caso completo esta en
app/servicios/__init__.py, donde se pago. El blueprint se pide donde vive:
`from app.perfil.vistas import profile`.
"""
