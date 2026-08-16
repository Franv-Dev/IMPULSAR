"""Punto de entrada estable para todo lo que invoca la app desde afuera.

    flask --app wsgi run
    flask --app wsgi db upgrade
    gunicorn wsgi:app

Existe para que esos comandos no dependan de en que modulo vive create_app. El
CI, el deploy y el README apuntan aca; cuando el codigo se mude a un paquete,
el unico cambio es el import de abajo y nada de lo de afuera se entera.

`app` se crea al importar porque es lo que espera un servidor WSGI. El CLI de
Flask usa esa misma instancia: cuando el modulo tiene un atributo `app`, lo toma
y no llama a la factory. create_app se reexporta igual, para quien quiera armar
una app con otra configuracion sin pasar por aca.
"""

from main import create_app

app = create_app()

__all__ = ["app", "create_app"]
