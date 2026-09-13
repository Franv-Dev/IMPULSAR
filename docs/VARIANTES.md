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
nullable y el cero es un valor distinto de NULL para la base (el CHECK es `>= 0`,
igual que el de `products.precio`).

Ojo con una asimetría heredada, que no es un descuido de esta tanda: **por la
interfaz no se puede cargar cero**, porque `services/precios.parsear_precio`
corta en `<= 0`. O sea que la base acepta el cero y el formulario no, exactamente
igual que ya pasaba con `products.precio`. El CHECK está en `>= 0` para no
contradecir al de products y para que el día que el parser cambie de opinión no
haga falta una migración; el que decide qué se puede escribir es el parser.

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

## El catálogo: precio "desde" y disponibilidad reales

La ficha fue consciente de las variantes desde el primer día; la tarjeta del
catálogo no, y quedó anotado acá como pendiente propio. Esta tanda lo cierra:
la tarjeta muestra el precio más barato de las combinaciones encendidas —con
«desde» sólo si no valen todas lo mismo— y el cartel de "sin stock" mira si
queda alguna combinación pedible, no sólo el interruptor del producto.

El motivo por el que fue una tanda aparte y no una línea al final de la
anterior sigue siendo el mismo: el catálogo es la pantalla más visitada del
proyecto, y preguntarle a cada producto por sus variantes para pintar la
tarjeta son **dos consultas por tarjeta** (las variantes y las opciones son
dos relaciones lazy), o sea veinticuatro extra en una grilla de doce.

### La consulta, y por qué tiene esta forma

`services.variantes.con_resumen_de_variantes()` le suma a la consulta que ya
arma el catálogo dos subconsultas **agrupadas** traídas con `outerjoin`, y
cinco columnas: cuántos ejes tiene cargados el producto, cuántas combinaciones
activas, cuántas **comprables**, y el mínimo y el máximo del precio efectivo
entre esas comprables. Es el mismo idiom que
`services.ratings.query_posts_con_rating`.

**Comprable es activa Y con stock**, que es `ProductoVariante.comprable`
escrito en SQL, y de esa única condición salen las dos mitades de la tarjeta:
el precio y el cartel de "sin stock". El mínimo no se calcula entre todas las
activas: la combinación más barata que se quedó sin stock no se puede pedir,
así que su precio no es una oferta, y anunciarlo dejaría a la tarjeta
prometiendo un número que la ficha —a un click, y con el mismo criterio en
`Product.precio_desde`— no puede cumplir. Escrita una sola vez, además, no hay
forma de que la tarjeta diga "desde $9.000" y "sin stock" al mismo tiempo, cada
mitad mirando otra cosa.

Las **activas** se cuentan igual, y por separado: son lo que distingue el
producto que tiene la matriz cargada y hoy no vende nada (agotado) del que no
usa variantes (precio base), que es la misma pregunta que contesta
`Product.tiene_variantes`.

**El GROUP BY vive adentro de cada subconsulta y la consulta de afuera no se
agrupa.** Agrupar afuera era más corto y está mal por dos motivos, los dos
medidos y no teóricos:

- el `joinedload` del emprendimiento mete las columnas de `posts` en el
  SELECT, y agrupando por `products.id` eso es el error 1055 de MySQL en
  `ONLY_FULL_GROUP_BY`: las columnas de `posts` no dependen funcionalmente de
  la PK de `products`;
- el paginado cuenta con un `COUNT` sobre la consulta, y con `GROUP BY` ese
  COUNT cuenta grupos y no filas, o sea que el "18 productos" del encabezado
  y la cantidad de páginas dejarían de decir la verdad.

**Son dos subconsultas y no una** porque la de variantes sola no alcanza para
saber si el producto usa variantes: el que tiene la matriz entera apagada y el
que nunca las usó dan los dos "ninguna activa", y son casos distintos —agotado
el primero, precio base el segundo—. Los distingue si hay **ejes** cargados,
que es exactamente la pregunta que contesta `Product.tiene_variantes`.

El precio de cada combinación es `COALESCE(precio_override, products.precio)`,
que es `ProductoVariante.precio_efectivo` escrito en SQL: NULL en el override
significa "hereda", nunca cero.

### Lo que costó, medido

Una página de 12 tarjetas, con productos con variantes (tres combinaciones cada
uno) mezclados en partes iguales con productos sin variantes. **Todos los
números de la tabla son contra SQLite en memoria**, mediana de 25 corridas, con
el identity map vaciado antes de cada una —sin eso los objetos ya cargados no
vuelven a la base y el número es falso—. Las tres formas posibles de la misma
pantalla:

| productos | vieja (precio base) | **agrupada (la elegida)** | correlacionada | lazy (N+1) |
|---|---|---|---|---|
| 10  | 1 consulta · 0,83 ms | **1 · 2,30 ms** | 1 · 1,75 ms | 21 · 5,43 ms |
| 40  | 1 consulta · 0,85 ms | **1 · 2,45 ms** | 1 · 2,57 ms | 25 · 5,75 ms |
| 80  | 1 consulta · 0,95 ms | **1 · 2,53 ms** | 1 · 5,65 ms | 25 · 5,75 ms |
| 200 | 1 consulta · 1,14 ms | **1 · 2,94 ms** | 1 · 24,70 ms | 25 · 5,96 ms |
| 400 | 1 consulta · 1,33 ms | **1 · 3,55 ms** | 1 · 93,07 ms | 25 · 6,17 ms |
| 800 | 1 consulta · 1,83 ms | **1 · 4,84 ms** | 1 · 361,18 ms | 25 · 6,65 ms |

(La columna de la correlacionada es de la misma medición hecha antes de que el
criterio pasara de "activas" a "comprables": es la forma de la consulta lo que
se estaba comparando, y esa no cambió. Las otras tres columnas son de la
consulta tal como quedó.)

**Contra MySQL real la agregada cuesta bastante más que ese número chico**: el
sobrecosto contra la consulta vieja es de **+6 ms con 10 productos** y **+43 ms
con 800**, o sea alrededor de diez veces lo que dice la tabla de SQLite. La
forma de la consulta es la misma y el ranking entre las cuatro también; lo que
cambia es la escala, y es la de MySQL la que corre en producción. La tabla
queda porque es la que compara las cuatro formas entre sí, pero el umbral de
"cuándo duele" hay que leerlo con estos dos números y no con los de arriba.

Las tres cosas que dicen estos números:

- **UNA consulta, siempre.** No hay N+1: el número no se mueve con cuántos
  productos trae la página ni con cuántos hay en el catálogo. Eso es lo que
  congela el test `test_el_catalogo_no_consulta_de_mas_por_cada_producto_con_variantes`,
  que compara el conteo con 5 y con 20 productos con variantes.
- **Cuesta entre 1,4 y 3 ms más que la consulta vieja en SQLite**, y ese costo crece con
  el tamaño del catálogo y no con el de la página, porque las subconsultas
  agregan la tabla entera antes de unirse —en MySQL, +6 ms a 10 productos y
  +43 ms a 800—. A 800 productos sigue siendo menos que el N+1 que reemplaza.
  El día que el catálogo sea diez veces más grande, esto es lo primero que hay
  que volver a medir, y **con los números de MySQL**: la salida conocida es
  acotar las subconsultas a los productos de la página.
- **La correlacionada, que parecía la solución obvia** (mirar sólo los doce
  productos de la página en vez de agregar la tabla entera), es la peor de
  todas apenas hay datos: el motor la evalúa por cada fila candidata antes del
  LIMIT, así que a 800 productos tarda 361 ms contra 4,9 ms de la agrupada. Se
  midió antes de elegir, no después.

### Lo que sigue desalineado, y es a propósito

Esta tanda arregla lo que la tarjeta **dice**. No toca lo que el catálogo
**filtra**, que son las otras dos cosas que este documento anotaba juntas:

- **`?disponibles=1`** (encendido por defecto) sigue filtrando por
  `products.disponible`, así que un producto con todas sus combinaciones en
  cero entra igual en la grilla —eso sí, ahora entra con el cartel de "sin
  stock" puesto, que antes tampoco tenía—;
- **`?precio_min` / `?precio_max`** siguen filtrando por el precio base,
  mientras la tarjeta ya muestra el "desde" de las combinaciones;
- **`?orden=precio_menor` / `precio_mayor`** ordenan por el precio base por lo
  mismo, así que una grilla ordenada por precio puede mostrar dos "desde" fuera
  de orden entre sí.

Las tres se arreglan con esta misma agregación movida al WHERE y al ORDER BY, y
son cambios de comportamiento del buscador (qué resultados devuelve una búsqueda
y en qué orden), no de lo que una tarjeta muestra. Por eso no van de arrastre
acá.

**La tarjeta y la ficha dicen el mismo precio**, y eso es deliberado: las dos
calculan el mínimo entre las combinaciones comprables —la tarjeta en SQL, la
ficha con `Product.precio_desde` en Python—. Un producto cuya combinación más
barata se quedó sin stock muestra el mismo número en las dos pantallas. Si
alguna vez hay que tocar uno de los dos criterios, hay que tocar los dos: el
que entra por el precio de una tarjeta lo hace para llegar a esa ficha.

Las otras dos pantallas que muestran tarjetas de producto —"Mis guardados" y el
catálogo dentro de la ficha del emprendimiento— siguen mostrando el precio
base: usan sus propias consultas y no pasaron por esta tanda, que es la del
catálogo. `con_resumen_de_variantes()` se les puede aplicar tal cual el día que
se toquen.
