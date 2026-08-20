"""Paquete de vistas. A proposito no reexporta nada.

Antes este archivo importaba cuatro blueprints y definia un
register_blueprints() que no usaba nadie: main.py los registra uno por uno. Eso
tenia dos costos. Tocar cualquier cosa del paquete importaba media app en
cadena, que es como aparecen los imports circulares; y el atributo del paquete
quedaba pisado por el Blueprint, asi que `views.profile` era el blueprint y no
el modulo, y un test que queria parchear el modulo tenia que ir por sys.modules
para conseguirlo (ver tests/test_profile.py).

Si alguna vez hace falta un registro centralizado, va en main.py o en la
factory, no aca.
"""
