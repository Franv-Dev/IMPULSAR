"""Paginar contando con OTRA consulta, mas magra que la de las filas.

POR QUE EXISTE. El paginado de Flask-SQLAlchemy cuenta con la misma consulta
que trae las filas: `QueryPagination._query_count()` hace
`query.order_by(None).count()`, o sea `SELECT count(*)` envolviendo la consulta
entera como subconsulta. Mientras la consulta de las filas es la de siempre eso
esta bien y es una linea menos. Deja de estarlo cuando la consulta trae COLUMNAS
QUE EL CONTEO NO NECESITA y que cuestan: el catalogo le suma a cada fila las
cinco columnas agregadas de las variantes (ver services.variantes), que son dos
subconsultas GROUP BY sobre las tablas enteras. Contar filas no necesita saber
el precio minimo de cada producto, pero el COUNT las arrastraba igual.

LA DISTINCION QUE HAY QUE TENER CLARA AL ARMAR EL CONTEO, porque es donde esto
se puede romper en silencio: no todo lo que la consulta agrega es decorativo.

  - lo que FILTRA tiene que estar en los dos lados. Si una condicion decide
    QUE PRODUCTOS ENTRAN --el rango de precio del catalogo, por ejemplo-- y se
    cae del conteo, el total deja de ser la cantidad de resultados y la grilla
    dice "40 productos" mostrando 12 de otros 18. Un total que no coincide con
    lo que se puede paginar es peor que un total lento.
  - lo que solo SE MUESTRA (o lo que solo ORDENA) no va: las columnas
    agregadas, el joinedload del emprendimiento, la distancia en km, el
    `order_by`. Nada de eso cambia cuantas filas hay.

El test que sostiene esa regla es el que compara el total contra la cantidad
real de resultados, con y sin filtro; sin el, un conteo desalineado pasa la
suite entera en verde porque ninguna otra assertion mira el numero.

EL CONTEO ES UNA CONSULTA ESCALAR (un `func.count(...)`) y no una de entidades,
asi que se resuelve con `.scalar()` y sin subconsulta de por medio: es la misma
forma que ya usaba el contador de emprendimientos del encabezado del catalogo.
"""

from flask_sqlalchemy.pagination import QueryPagination


class _PaginacionConConteoAparte(QueryPagination):
    """La paginacion de siempre, con el total sacado de otra consulta.

    Hereda `_query_items` --las filas se piden igual, con LIMIT y OFFSET-- y
    reemplaza solo el conteo. Los dos van en `_query_args` para que `prev()` y
    `next()` sigan funcionando: la clase base rearma la pagina vecina con
    `type(self)(**self._query_args)`, asi que la consulta del conteo tiene que
    viajar ahi adentro y no en un atributo aparte.
    """

    def _query_count(self):
        # order_by(None) por lo mismo que la clase base: un ORDER BY heredado
        # en un COUNT no cambia el resultado, y en MySQL con
        # ONLY_FULL_GROUP_BY un conteo agrupado que arrastra el orden es el
        # error 1055.
        return self._query_args["conteo"].order_by(None).scalar() or 0


def paginar_con_conteo(consulta, conteo, pagina, por_pagina):
    """Pagina `consulta` pero saca el total de `conteo`.

    `conteo` es una consulta ESCALAR (un `func.count(...)`) con los MISMOS
    filtros que `consulta` y sin sus columnas de adorno. Armarla es
    responsabilidad de quien llama, porque es el unico que sabe cual de sus
    condiciones filtra y cual solo se muestra; el docstring del modulo explica
    donde esta el filo.

    `error_out=False` y `max_per_page=None` son los mismos valores con los que
    el proyecto venia llamando a `.paginate()`, asi que pedir una pagina que no
    existe sigue devolviendo una pagina vacia en vez de un 404 --de eso
    depende el parcial de paginacion, que con `?page=999` manda "Anterior" a la
    ultima pagina real-- y un `por_pagina` alto de la config sigue valiendo.
    """
    return _PaginacionConConteoAparte(
        query=consulta,
        conteo=conteo,
        page=pagina,
        per_page=por_pagina,
        error_out=False,
        max_per_page=None,
    )
