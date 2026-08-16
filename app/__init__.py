"""El codigo de la aplicacion, dividido en paquetes por dominio.

Cada dominio (app/servicios/, y los que vengan) es autocontenido: sus vistas,
sus reglas, sus consultas, su formulario, su modelo y sus templates viven
juntos, porque juntos es como se tocan. La alternativa era cortar por capas
horizontales (views/ + services/ + repositories/), pero este proyecto crece por
features enteras, y con capas horizontales cada feature nueva obliga a abrir
tres carpetas lejanas entre si.

Adentro de cada paquete si hay capas, y las dependencias van en un solo
sentido:

    vistas -> reglas -> consultas -> modelo

Una vista no toca db.session; una regla no conoce request ni flash. Lo que se
comparte de verdad, sin dueño posible (precios, uploads, slugs), no vive en
ningun dominio.

A proposito este __init__.py no importa nada: es el error que ya se pago en
views/__init__.py, donde reexportar blueprints importaba media app en cadena y
pisaba el nombre de los modulos.
"""
