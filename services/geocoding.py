"""Geocodificacion de direcciones con la API de MapTiler.

Antes esta logica estaba duplicada en views/blog.py y app/perfil/vistas.py, con
la diferencia de que la version de blog acotaba la busqueda a Mendoza y la de
profile no. Se unifica aca usando el criterio mas preciso para las dos, que es
el que corresponde: IMPULSAR es una plataforma de emprendimientos locales.
"""

import logging

import requests

logger = logging.getLogger(__name__)

# Caja aproximada de la provincia de Mendoza (oeste, sur, este, norte).
MENDOZA_BBOX = "-70.9,-36.5,-66.5,-31.5"

# Contexto que se le agrega a la direccion escrita por el usuario. Sin esto,
# "San Martin 500" puede resolver a cualquier ciudad del pais.
DEFAULT_CONTEXT = "Mendoza, Argentina"

DEFAULT_COUNTRY = "AR"

# Segundos que esperamos a MapTiler antes de rendirnos. Sin timeout, si la API
# se cuelga la request del usuario queda esperando indefinidamente y se van
# agotando los workers del servidor.
DEFAULT_TIMEOUT = 5


def get_coordinates_from_address(
    address,
    api_key,
    *,
    context=DEFAULT_CONTEXT,
    bbox=MENDOZA_BBOX,
    country=DEFAULT_COUNTRY,
    timeout=DEFAULT_TIMEOUT,
):
    """Convierte una direccion escrita en texto a una tupla (latitud, longitud).

    Devuelve (None, None) si la direccion esta vacia, si MapTiler no encuentra
    resultados o si la llamada falla. Nunca lanza excepciones: el que llama
    decide que hacer cuando no hay coordenadas.
    """
    if not address or not address.strip():
        return None, None

    if not api_key:
        logger.warning("No hay MAPTILER_KEY configurada; se omite el geocoding.")
        return None, None

    full_address = f"{address.strip()}, {context}" if context else address.strip()
    encoded_address = requests.utils.quote(full_address)

    url = f"https://api.maptiler.com/geocoding/{encoded_address}.json"
    params = {"key": api_key, "limit": 1}
    if country:
        params["country"] = country
    if bbox:
        params["bbox"] = bbox

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        logger.warning("MapTiler no respondio en %ss para: %s", timeout, full_address)
        return None, None
    except requests.exceptions.RequestException as exc:
        logger.warning("Error consultando MapTiler para '%s': %s", full_address, exc)
        return None, None
    except ValueError:
        logger.warning("MapTiler devolvio una respuesta que no es JSON valido.")
        return None, None

    features = (data or {}).get("features") or []
    if not features:
        logger.info("MapTiler no encontro resultados para: %s", full_address)
        return None, None

    # MapTiler devuelve el centro como [longitud, latitud], en ese orden.
    coords = features[0].get("center")
    if not coords or len(coords) != 2:
        logger.warning("MapTiler devolvio un feature sin coordenadas validas.")
        return None, None

    longitude, latitude = coords[0], coords[1]
    return latitude, longitude
