"""Tests del renderizado minimo y seguro de la bio (services/formatting.py)."""

from markupsafe import Markup

from services.formatting import render_biography


def test_texto_vacio_devuelve_markup_vacio():
    assert render_biography(None) == Markup("")
    assert render_biography("") == Markup("")


def test_saltos_de_linea_se_convierten_en_br():
    resultado = render_biography("Primera línea\nSegunda línea")

    assert "Primera línea<br>Segunda línea" in resultado


def test_negrita_basica():
    resultado = render_biography("Hola **mundo** genial")

    assert "<strong>mundo</strong>" in resultado


def test_dos_negritas_separadas_no_se_mezclan():
    resultado = render_biography("**uno** y **dos**")

    assert "<strong>uno</strong>" in resultado
    assert "<strong>dos</strong>" in resultado
    assert "uno</strong> y <strong>dos" in resultado


def test_link_http_se_convierte_en_a():
    resultado = render_biography("Visitá [mi tienda](https://ejemplo.com/tienda)")

    assert '<a href="https://ejemplo.com/tienda"' in resultado
    assert ">mi tienda</a>" in resultado
    assert 'rel="noopener noreferrer nofollow"' in resultado


def test_link_con_esquema_no_http_no_se_convierte():
    """javascript:/data: no deben poder convertirse en <a href>."""
    resultado = render_biography("[click](javascript:alert(1))")

    assert "<a " not in resultado
    # El texto queda escapado, tal cual, sin ejecutarse como HTML.
    assert "javascript:alert(1)" in resultado


def test_el_html_crudo_se_escapa_y_no_se_ejecuta():
    resultado = render_biography("<script>alert('xss')</script>")

    assert "<script>" not in resultado
    assert "&lt;script&gt;" in resultado


def test_intento_de_inyeccion_via_atributo_del_link_se_escapa():
    """El texto del link puede traer comillas: no debe poder cerrar el atributo href."""
    resultado = render_biography('[a"onmouseover="alert(1)](https://ejemplo.com)')

    # La comilla que trajo el usuario queda escapada (&#34;), nunca como
    # comilla literal que pudiera cerrar un atributo antes de tiempo.
    assert 'onmouseover="' not in resultado
    assert "&#34;" in resultado


def test_texto_plano_sin_formato_se_muestra_igual():
    resultado = render_biography("Hola, soy panadero de toda la vida.")

    assert "Hola, soy panadero de toda la vida." in resultado
