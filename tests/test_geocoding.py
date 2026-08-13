"""Tests del servicio de geocoding.

No se llama a MapTiler de verdad: se simula (mock) la respuesta de requests,
asi los tests son rapidos, no gastan cuota de la API y funcionan sin internet.
"""

from unittest.mock import patch, MagicMock

import pytest
import requests

from services.geocoding import get_coordinates_from_address


def _fake_response(payload):
    """Arma una respuesta simulada de requests con el JSON que le pasemos."""
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_direccion_vacia_no_llama_a_la_api():
    with patch("services.geocoding.requests.get") as mock_get:
        assert get_coordinates_from_address("", "una-key") == (None, None)
        assert get_coordinates_from_address("   ", "una-key") == (None, None)
        mock_get.assert_not_called()


def test_sin_api_key_no_llama_a_la_api():
    with patch("services.geocoding.requests.get") as mock_get:
        assert get_coordinates_from_address("San Martin 500", "") == (None, None)
        mock_get.assert_not_called()


def test_devuelve_latitud_y_longitud_en_el_orden_correcto():
    """MapTiler devuelve [longitud, latitud]; nosotros devolvemos (lat, lon)."""
    payload = {"features": [{"center": [-68.85, -32.89]}]}

    with patch("services.geocoding.requests.get", return_value=_fake_response(payload)):
        latitud, longitud = get_coordinates_from_address("San Martin 500", "una-key")

    assert latitud == -32.89
    assert longitud == -68.85


def test_se_envia_timeout_y_contexto_local():
    payload = {"features": [{"center": [-68.85, -32.89]}]}

    with patch("services.geocoding.requests.get", return_value=_fake_response(payload)) as mock_get:
        get_coordinates_from_address("San Martin 500", "una-key")

    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 5, "La llamada debe tener timeout para no colgar el servidor"
    assert kwargs["params"]["country"] == "AR"
    assert kwargs["params"]["bbox"], "Debe acotar la busqueda a Mendoza"


def test_timeout_no_rompe_la_vista():
    with patch("services.geocoding.requests.get", side_effect=requests.exceptions.Timeout):
        assert get_coordinates_from_address("San Martin 500", "una-key") == (None, None)


def test_error_de_red_no_rompe_la_vista():
    with patch("services.geocoding.requests.get", side_effect=requests.exceptions.ConnectionError):
        assert get_coordinates_from_address("San Martin 500", "una-key") == (None, None)


def test_respuesta_sin_resultados():
    with patch("services.geocoding.requests.get", return_value=_fake_response({"features": []})):
        assert get_coordinates_from_address("direccion inexistente", "una-key") == (None, None)


def test_respuesta_con_feature_sin_coordenadas():
    payload = {"features": [{"place_name": "algo"}]}

    with patch("services.geocoding.requests.get", return_value=_fake_response(payload)):
        assert get_coordinates_from_address("San Martin 500", "una-key") == (None, None)
