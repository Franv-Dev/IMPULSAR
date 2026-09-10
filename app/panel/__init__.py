"""Panel del vendedor: la portada de lo que uno administra.

Hasta esta tanda las pantallas del dueño -- emprendimientos, catalogo,
servicios, presupuestos, agenda de turnos y reseñas -- eran seis paginas
sueltas, cada una colgada del menu de la cuenta y con su propia forma. Este
paquete las convierte en una seccion: un menu lateral compartido
(templates/partials/_menu_panel.html) y una portada que dice que hay que hacer
antes que cuanto se hizo.

    consultas.py    lo que la portada le pregunta a la base
    vistas.py       la ruta /panel

No hay modelo propio ni reglas: el panel no tiene entidad, es una vista de lo
que ya existe en los otros dominios. Por eso tampoco reexporta nada, igual que
app/turnos/ y app/servicios/.
"""
