"""Mueve a la carpeta privada las fotos que dejaron de ser publicas.

    python -m scripts.mover_uploads_privados            # muestra lo que haria
    python -m scripts.mover_uploads_privados --aplicar  # lo hace

Contexto: hasta esta tanda, la foto de una solicitud de presupuesto y el
documento de un pedido de verificacion se guardaban en static/uploads, la misma
carpeta que los avatares y las portadas. Ahora se guardan en la carpeta privada
(ver PRIVATE_UPLOAD_FOLDER en config.py), que cuelga de la raiz del repo y no de
static/. Las que ya estaban subidas siguen del lado publico, asi que sin este
script las dos rutas protegidas les darian 404 despues del deploy.

POR QUE LEE LA BASE Y NO MUEVE POR PATRON. Los nombres de archivo no dicen de
donde salieron: todos se arman igual (uuid + secure_filename), asi que un
`mv static/uploads/*.png` se llevaria de paso los avatares, las portadas y las
fotos de los emprendimientos, que tienen que seguir siendo publicas. La unica
fuente que sabe cuales son las privadas son las dos columnas foto de
ServiceRequest y VerificationRequest, asi que el script mueve exactamente esos
nombres y ninguno mas.

ES IDEMPOTENTE: si un archivo ya esta del lado privado, lo cuenta como hecho y
sigue. Se puede correr dos veces sin romper nada, que es lo que hace falta
cuando un deploy se corta por la mitad.

NO BORRA FILAS NI TOCA LA BASE. Solo mueve archivos: la columna guarda el
nombre, no la carpeta, asi que despues de mover no hay nada que actualizar. Si
algo sale mal, el arreglo es mover los archivos de vuelta.
"""

import argparse
import os
import shutil
import sys

from app.servicios.modelo_solicitud import ServiceRequest
from app.servicios.modelo_verificacion import VerificationRequest
from main import create_app
from services.uploads import carpeta_privada, carpeta_uploads


def _nombres_privados():
    """Los nombres de archivo que dejaron de ser publicos, sin repetidos.

    Se consultan solo las columnas foto y no las filas enteras: son dos SELECT
    de una columna en vez de traer dos tablas a memoria para leerles un campo.
    """
    from db import db

    filas = (
        db.session.query(ServiceRequest.foto).filter(ServiceRequest.foto.isnot(None)).all()
        + db.session.query(VerificationRequest.foto)
        .filter(VerificationRequest.foto.isnot(None))
        .all()
    )
    return sorted({nombre for (nombre,) in filas if nombre})


def mover(aplicar):
    """Mueve (o simula mover) las fotos privadas. Devuelve el codigo de salida."""
    origen = carpeta_uploads()
    destino = carpeta_privada()

    nombres = _nombres_privados()
    if not nombres:
        print("No hay fotos privadas registradas en la base. Nada que mover.")
        return 0

    print(f"Origen : {origen}")
    print(f"Destino: {destino}")
    print(f"Fotos privadas segun la base: {len(nombres)}\n")

    movidas = ya_estaban = faltantes = 0
    for nombre in nombres:
        ruta_origen = os.path.join(origen, nombre)
        ruta_destino = os.path.join(destino, nombre)

        if os.path.exists(ruta_destino):
            ya_estaban += 1
            continue

        if not os.path.exists(ruta_origen):
            # La fila apunta a un archivo que ya no esta. No es un error del
            # script: las rutas protegidas ya devuelven 404 para este caso.
            print(f"  FALTA    {nombre}")
            faltantes += 1
            continue

        if aplicar:
            os.makedirs(destino, exist_ok=True)
            # move y no copy: dejar el original del lado publico seria dejar
            # justamente el archivo que esta tanda vino a sacar de ahi.
            shutil.move(ruta_origen, ruta_destino)
        print(f"  {'MUEVE   ' if aplicar else 'MOVERIA '} {nombre}")
        movidas += 1

    print(
        f"\n{'Movidas' if aplicar else 'Se moverian'}: {movidas} | "
        f"ya estaban del lado privado: {ya_estaban} | "
        f"sin archivo en disco: {faltantes}"
    )
    if not aplicar and movidas:
        print("\nEsto fue una simulacion. Volve a correrlo con --aplicar.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="mueve los archivos de verdad (sin esto solo muestra que haria)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        return mover(args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
