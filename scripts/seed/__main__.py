"""Punto de entrada: guardas de host y parseo de argumentos.

    python -m scripts.seed [--reset | --borrar] [--forzar-host]
"""

import sys

from sqlalchemy.engine import make_url

from main import create_app

from scripts.seed.borrado import _usuarios_de_seed, borrar
from scripts.seed.carga import cargar
from scripts.seed.datos import CLIENTES, EMPRENDEDORES, PASSWORD


HOSTS_LOCALES = {"", "localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _confirmar_si_no_es_local(app):
    """Freno si la base no esta en esta maquina. Devuelve si seguir o no.

    El script borra filas y sube archivos: contra la base de desarrollo eso es
    lo que uno quiere, contra cualquier otra es un accidente. Y es un
    accidente facil, porque el destino sale del entorno (DATABASE_URL o el
    .env) y no de un argumento que uno escriba y vea.

    Con --forzar-host no pregunta: es para poder usarlo en un contenedor o en
    un CI, donde no hay nadie del otro lado para contestar.
    """
    host = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).host or ""
    if host.lower() in HOSTS_LOCALES:
        return True

    if "--forzar-host" in sys.argv:
        print(f"Base remota ({host}), pero se paso --forzar-host. Sigo.")
        return True

    print(
        f"\n  La base NO esta en esta maquina: {host}\n"
        "  Este script borra filas y escribe archivos. Si esa base es de\n"
        "  produccion o la comparte alguien mas, no la corras.\n"
    )
    try:
        respuesta = input(f"  Escribí el nombre del host ({host}) para seguir: ")
    except (EOFError, KeyboardInterrupt):
        # Sin nadie del otro lado que conteste, la respuesta segura es que no.
        # Se captura en vez de mirar sys.stdin.isatty() porque isatty() miente
        # segun como se haya invocado el script: dice que hay terminal y el
        # input() explota igual con EOFError.
        print("\n  Sin respuesta. Cortado, no se tocó nada.")
        print("  Si estás seguro, repetí el comando con --forzar-host.")
        return False

    if respuesta.strip() != host:
        print("  No coincide. Cortado, no se tocó nada.")
        return False
    return True


def main():
    reset = "--reset" in sys.argv
    solo_borrar = "--borrar" in sys.argv

    app = create_app("development")
    with app.app_context():
        destino = app.config["SQLALCHEMY_DATABASE_URI"].rsplit("@", 1)[-1]
        print(f"Base: {destino}")

        if not _confirmar_si_no_es_local(app):
            return

        if reset or solo_borrar:
            borrar(app)
        if solo_borrar:
            return

        if _usuarios_de_seed():
            print(
                "Ya hay datos de seed cargados. Corré con --reset para "
                "rehacerlos, o con --borrar para sacarlos."
            )
            return

        resumen = cargar(app)

    print("\nCargado:")
    for que, cuantos in resumen.items():
        print(f"  {cuantos:>3} {que}")
    print(f"\nTodos los usuarios entran con la contraseña: {PASSWORD}")
    print("  emprendedores: " + ", ".join(EMPRENDEDORES))
    print("  clientes:      " + ", ".join(CLIENTES))


if __name__ == "__main__":
    main()
