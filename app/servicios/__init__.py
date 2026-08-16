"""Servicios de un emprendimiento y las solicitudes de presupuesto sobre ellos.

Los dos flujos viven en el mismo paquete porque son la misma feature vista de
los dos lados: el prestador carga lo que hace, el cliente pide presupuesto
sobre eso. Comparten el blueprint, el prefijo /servicios y los templates.

    vistas.py             las rutas (HTTP: request, flash, redirect, render)
    reglas.py             las decisiones de negocio, sin saber que existe HTTP
    consultas.py          todo lo que le pregunta a la base
    formulario.py         parseo y validacion de lo que manda el navegador
    modelo.py             Service
    modelo_solicitud.py   ServiceRequest
    templates/servicios/  las plantillas del blueprint

No reexporta nada, por la misma razon que app/__init__.py y que el
views/__init__.py que se limpio en el paso anterior, y esta vez con la prueba
al lado: la primera version de este archivo hacia `from app.servicios.vistas
import servicios`, y con eso cualquiera que importara app.servicios.modelo
arrastraba las vistas, que importan consultas, que importa models.post, que
importa app.servicios.modelo... o sea el modulo a medio inicializar del que
habia salido. Reventaba al arrancar. Quien quiera el blueprint lo pide donde
esta: `from app.servicios.vistas import servicios`.
"""
