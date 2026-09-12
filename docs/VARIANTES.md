# Variantes de producto

Un producto puede venderse por combinación de **talle × color**, cada una con su
stock y, si el vendedor quiere, con su propio precio.

Esto existe para que el que audite después no tenga que reconstruir el diseño
leyendo el diff. El detalle largo de cada decisión vive en los docstrings de
`models/producto_variante.py`; acá está el mapa y los porqués que no se ven
mirando una tabla sola.

## Lo primero: son opcionales

**Un producto sin variantes se comporta exactamente como antes de esta tanda.**
No se agregó ninguna columna a `products`. Su precio sigue siendo
`products.precio` y su disponibilidad el booleano `products.disponible` de
siempre.

`Product.tiene_variantes` es la pregunta que parte en dos todo lo que sigue, y se
contesta mirando si hay filas, no un flag aparte —un flag sería un segundo lugar
donde decir lo mismo, y podría quedar diciendo que sí con la matriz vacía.

## Las dos tablas

| tabla | qué guarda |
|---|---|
| `producto_variante_opciones` | qué talles y qué colores maneja **ese** producto |
| `producto_variantes` | una fila por combinación realmente generada |

El vendedor carga dos listas (los talles y los colores que maneja) y el sistema
genera la matriz completa como filas editables.

### Por qué una sola tabla de opciones, con un campo `tipo`

Un talle y un color tienen exactamente la misma forma —una etiqueta corta que
pertenece a un producto y que se ordena— y se usan en el mismo lugar, en el mismo
momento y de la misma manera: son los dos ejes de la misma matriz. Dos tablas
chicas serían el mismo modelo, la misma FK, el mismo UNIQUE, el mismo endpoint y
los mismos tests escritos dos veces, y el día que aparezca un tercer eje
(material, sabor) serían tres.

Es al revés que el caso de `product_favorites`, que sí es una tabla aparte de
`favorites`: allá las dos cosas se guardan igual pero **se miran distinto** (una
es "esta gente me interesa" y la otra "esta cosa a este precio"). Acá no.

El precio de la decisión es que el `tipo` hay que validarlo, porque la columna
sola aceptaría cualquier cosa. Eso lo sostiene el CHECK
`ck_producto_variante_opciones_tipo` y no la buena memoria de cada vista.

### Por qué no hay catálogo global de talles ni de colores

Se evaluó. Una tabla compartida entre productos necesitaría su ABM, su
normalización (`Rojo` / `rojo` / `ROJO`) y una pantalla de administración, y a
cambio hoy no daría nada: no existe ningún filtro del catálogo por color ni por
talle, que es lo único que justificaría compartir el vocabulario. Cada producto
guarda sus valores como texto, que además es lo que el vendedor escribe.

El día que se quiera filtrar "todo lo que hay en rojo", eso es una tabla nueva y
una migración de datos, no un rediseño de ésta.

## El UNIQUE compuesto, y por qué el eje vacío es `''` y no `NULL`

`UNIQUE(product_id, talle, color)` es lo que impide dos veces la misma
combinación. Es constraint de base y no validación en Python: la generación de la
matriz chequea antes para no duplicar, pero entre ese SELECT y el INSERT hay una
ventana por la que pasan dos requests simultáneos (el doble click que manda dos
POST, o dos pestañas del mismo formulario).

Cuando un producto usa un solo eje (talles y ningún color, que es el caso más
común), el otro se guarda como **cadena vacía y nunca como NULL**. No es
cosmético: en los dos motores un UNIQUE **ignora** las filas que tienen un NULL
en alguna de sus columnas —es la misma propiedad que el proyecto aprovecha a
favor en `cupo_pendiente`, `cupo_activa` y `cupo_aceptada`—, así que con NULL la
regla dejaría de aplicar justo en ese caso y se podrían cargar dos filas "M" sin
que la base dijera nada.

## Generar la matriz nunca pisa lo editado

Guardar las listas de talles y colores **agrega** las combinaciones que faltan y
no toca las que ya existen: el stock, el precio y el `activo` que el vendedor
venía editando sobreviven a que vuelva a tocar las listas. Sacar un talle de la
lista tampoco borra sus filas —las apaga—, por lo mismo que el punto siguiente.

## `activo`: curación manual, no regla automática

No toda combinación generada existe de verdad (el XXL no se fabricó en verde). El
sistema no tiene forma de deducirlo, así que lo dice el vendedor apagando esa
fila. Se apaga y no se borra por dos motivos: la fila puede tener historia, y la
matriz la volvería a generar en el próximo guardado de opciones.

Una combinación apagada no se puede elegir ni consultar, tenga el stock que
tenga.

## Precio: `precio_override` en NULL significa "hereda"

NULL es "usá el precio del producto", **no** "gratis" —por eso la columna es
nullable y el cero es un precio válido y distinto (el CHECK es `>= 0`, igual que
el de `products.precio`: un producto gratis es una oferta real).

El precio que se le cobra al cliente se lee siempre por `ProductoVariante.precio_efectivo`,
que devuelve el override si lo hay y si no el del producto. Es una property y no
una columna copiada al generar la fila: si se copiara, subir el precio del
producto no se reflejaría en las variantes que nunca se tocaron, que es
justamente lo que "hereda" tiene que significar.

## Stock

- Por combinación, entero y no negativo (garantizado por la base).
- `Product.stock_total` es la suma de las **activas**, o `None` si el producto no
  tiene variantes. `None` y no cero es la diferencia que importa: cero es "tiene
  variantes y no queda ninguna", `None` es "este producto no maneja stock".
- Las apagadas no suman aunque tengan stock cargado: el vendedor dijo que esa
  combinación no existe.

## Dónde aterriza "no se puede comprar"

**Este proyecto no tiene carrito ni compra** (`models/product.py`: "es catálogo y
no tienda"; `templates/products/detalle.html`: "NO HAY «COMPRAR»"). La acción de
una ficha es *consultar*, y termina en el chat interno.

Así que la validación de "combinación activa y con stock suficiente" aterriza
donde este proyecto sí decide algo: **el selector de la ficha**. Sólo se pueden
elegir combinaciones comprables (`activo = True` y `stock > 0`), y la consulta al
vendedor viaja con la combinación elegida. El chequeo se rehace en el servidor
con la fila traída de la base, porque el POST se escribe a mano.
