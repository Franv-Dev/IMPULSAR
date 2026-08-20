"""Servicios de un emprendimiento y las solicitudes de presupuesto sobre ellos.

Los flujos viven en el mismo paquete porque son la misma feature vista desde
varios lados: el prestador carga lo que hace, el cliente pide presupuesto sobre
eso, y un admin verifica las credenciales del prestador para ese servicio.
Comparten el blueprint, el prefijo /servicios y los templates. La unica parte
que no vive aca son las rutas del admin, que estan en views/admin.py con el
resto del panel (y le piden las consultas a este paquete).

    vistas.py               las rutas (HTTP: request, flash, redirect, render)
    reglas.py               las decisiones de negocio, sin saber que existe HTTP
    consultas.py            todo lo que le pregunta a la base
    formulario.py           parseo y validacion de lo que manda el navegador
    modelo.py               Service
    modelo_solicitud.py     ServiceRequest
    modelo_verificacion.py  VerificationRequest
    templates/servicios/    las plantillas del blueprint

No reexporta nada, por la misma razon que app/__init__.py y que el
views/__init__.py que se limpio en el paso anterior, y esta vez con la prueba
al lado: la primera version de este archivo hacia `from app.servicios.vistas
import servicios`, y con eso la app no arrancaba.

El ciclo, en el orden en que pasa de verdad (se reproduce con `import
app.blog.modelo_post`, que entonces era models.post, o con cualquier cosa que lo
importe, como main): el modulo de Post empieza a ejecutarse y pide
app.servicios.modelo para poder resolver su relacion `servicios`; para eso Python
corre primero este __init__, que importaba vistas, que importa consultas, que
importa el modulo de Post... y ese esta a medio ejecutar, todavia sin definir la
clase Post, asi que el import falla ahi. El modulo incompleto es el de Post, no
app.servicios.modelo: `import app.servicios.modelo` a secas funcionaba, porque
en ese orden el de Post arranca y termina de una.

Quien quiera el blueprint lo pide donde vive: `from app.servicios.vistas import
servicios`.
"""
