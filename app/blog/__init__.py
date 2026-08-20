"""Emprendimientos: la publicacion, su galeria, las resenias, los favoritos y
los reportes de contenido.

Todo eso vive en el mismo paquete porque cuelga de la misma entidad: un Post.
Una resenia es sobre un emprendimiento, un favorito marca un emprendimiento, y
un reporte apunta a un emprendimiento o a una resenia. Comparten el blueprint,
el prefijo /blog y los templates.

    vistas.py           las rutas (HTTP: request, flash, redirect, render)
    reglas.py           las decisiones de negocio, sin saber que existe HTTP
    consultas.py        todo lo que le pregunta a la base
    formulario.py       parseo y validacion de lo que manda el navegador
    modelo_post.py      Post, Categorias, MAX_IMAGENES_POR_POST
    modelo_imagen.py    PostImage
    modelo_resenia.py   Review
    modelo_favorito.py  Favorite
    modelo_reporte.py   Report
    templates/blog/     las plantillas del blueprint

No reexporta nada, por la misma razon que app/servicios/__init__.py, que lo
tiene documentado con el ciclo completo al lado. Aca el riesgo es todavia mayor:
modelo_post.py es el modulo mas importado del proyecto (lo piden perfil,
servicios, eventos, mensajes, admin, la API y el seed), asi que un solo reexport
en este archivo pondria a vistas.py y consultas.py en el medio de cada una de
esas importaciones.

Quien quiera el blueprint lo pide donde vive: `from app.blog.vistas import blog`.
"""
