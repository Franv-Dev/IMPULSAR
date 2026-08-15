"""Leer y mostrar precios.

Vive aparte del modelo por lo mismo que services/horarios.py: el formulario
recibe texto escrito por una persona ("1.500,50") y la columna guarda un
Decimal, y esa traduccion no es de la vista ni del modelo.

Todo el modulo trabaja con Decimal y nunca con float: en binario 0.1 no es
exactamente 0.1, asi que un precio pasado por float vuelve con centavos de
diferencia y cualquier suma arrastra el error.
"""

import re
from decimal import Decimal, InvalidOperation

# Digitos con, a lo sumo, una parte decimal. Sin signo, sin exponente.
_NUMERO_LLANO = re.compile(r"\d+(\.\d+)?")

# Tope del Numeric(10, 2) de la columna: 8 digitos enteros y 2 decimales. Si
# se pasa, la base lo rechazaria con un error de rango que no le dice nada al
# usuario, asi que se corta antes con un mensaje entendible.
PRECIO_MAXIMO = Decimal("99999999.99")

CENTAVOS = Decimal("0.01")


def parsear_precio(texto):
    """Convierte lo que escribio el usuario en un Decimal.

    Devuelve (precio, error): uno de los dos siempre es None.

    Acepta las dos formas en que se escribe un precio en Argentina, con coma
    decimal ("1500,50") y con punto ("1500.50"), y tolera los puntos de miles
    ("1.500,50"). Sin esto, alguien que escribe la coma termina cargando un
    precio distinto del que quiso, sin ningun aviso.
    """
    texto = (texto or "").strip()
    if not texto:
        return None, "Se requiere un precio."

    # Se saca el simbolo por si lo escribieron: "$1500" es un precio valido
    # para cualquiera que lo lea.
    texto = texto.replace("$", "").replace(" ", "")

    if "," in texto:
        # Con coma presente, la coma es el separador decimal y los puntos son
        # de miles ("1.500,50").
        texto = texto.replace(".", "").replace(",", ".")

    # Se exige un numero escrito de la forma llana antes de pasarlo a Decimal.
    # Decimal() de por si acepta cosas que nadie quiso escribir como precio y
    # que serian una sorpresa cara: "1e5" son cien mil pesos, y "NaN" e "Inf"
    # entran como valores validos.
    if not _NUMERO_LLANO.fullmatch(texto):
        return None, "El precio no es válido. Escribí solo números, por ejemplo 1500 o 1500,50."

    try:
        precio = Decimal(texto)
    except InvalidOperation:
        return None, "El precio no es válido. Escribí solo números, por ejemplo 1500 o 1500,50."

    if precio <= 0:
        return None, "El precio tiene que ser mayor que cero."
    if precio.as_tuple().exponent < -2:
        return None, "El precio puede tener como máximo dos decimales."
    if precio > PRECIO_MAXIMO:
        return None, "Ese precio es demasiado alto."

    # Se normaliza a dos decimales para que "1500" y "1500,00" queden iguales
    # en la base y el formulario de edicion siempre muestre lo mismo.
    return precio.quantize(CENTAVOS), None


def formatear(precio):
    """El precio como se muestra: "$ 1.500,50", con separadores argentinos."""
    if precio is None:
        return ""
    # El format de Python usa la convencion inglesa (1,500.50); se dan vuelta
    # los separadores en un paso, con un marcador intermedio para no pisar uno
    # con el otro.
    texto = f"{Decimal(precio):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"$ {texto}"


def texto_para_formulario(precio):
    """El precio como se precarga en el input al editar ("1500.50").

    Con punto y sin separador de miles: es lo que espera un <input> numerico y
    lo que parsear_precio vuelve a leer sin ambiguedad.
    """
    return "" if precio is None else f"{Decimal(precio):.2f}"
