"""Carga datos de prueba en la base, para poder navegar la app con contenido.

No es un one-off: se puede volver a correr. Todo lo que crea queda marcado
(los usuarios con el dominio de EMAIL_SEED, las imagenes con el prefijo
PREFIJO_IMAGEN), asi que `--reset` y `--borrar` saben exactamente que sacar.

    python -m scripts.seed            # carga, si todavia no hay datos de seed
    python -m scripts.seed --reset    # borra los de antes y vuelve a cargar
    python -m scripts.seed --borrar   # solo borra

QUE BORRA EXACTAMENTE --borrar (y --reset antes de recargar)

No es solo "lo que creo el seed". Borra los usuarios de seed, sus
emprendimientos y todo lo que cuelga de esos emprendimientos, y eso incluye
filas de usuarios REALES que apunten a contenido del seed:

- la resenia que un usuario tuyo le dejo a un emprendimiento del seed,
- el favorito que marco sobre uno de ellos,
- los mensajes de esa conversacion,
- el reporte que hizo sobre uno de esos posts,
- y el follow a un usuario del seed (en cualquiera de las dos direcciones).

No hay forma de evitarlo: si se va el emprendimiento, la resenia que apunta a
el no puede quedar. Lo que si esta garantizado es lo otro: nada que no
referencie contenido del seed se toca, ni un usuario real, ni sus
emprendimientos, ni sus resenias sobre emprendimientos reales.

Las fotos son imagenes generadas (un degrade con las iniciales), no fotos de
verdad: son para ver como queda la maqueta, no para simular contenido real.

Del disco borra exactamente los archivos que nombran las filas de seed de la
base a la que esta conectado (Post.image, PostImage.filename y Product.foto),
uno por uno. No barre el directorio buscando el prefijo, y la diferencia
importa: static/uploads es una sola carpeta para todas las bases, asi que un
glob de seed_* apuntando a una base se llevaba tambien las imagenes de otra
base sembrada aparte, dejandola con las filas apuntando a archivos que ya no
estaban. Por lo mismo, cada corrida les pone un sufijo propio al nombre (ver
CORRIDA): dos bases sembradas por separado no comparten un solo archivo.

Corre contra la base que diga el entorno, igual que la app: por defecto la de
desarrollo del .env. Si esa base no esta en localhost, pide confirmacion
antes de tocar nada (ver _confirmar_si_no_es_local, en __main__.py).

COMO ESTA DIVIDIDO

- datos.py    las tablas literales: quienes son los usuarios, que venden.
- imagenes.py los PNG placeholder y como se nombran.
- borrado.py  borrar(), que saca lo que dejo una corrida anterior.
- carga.py    cargar(), que escribe todo lo de datos.py en la base.
- __main__.py las guardas de host y el parseo de argumentos.
"""

import os
import sys

# El paquete vive en scripts/, asi que la raiz del proyecto no esta en el path
# cuando se lo invoca desde otro lado.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
