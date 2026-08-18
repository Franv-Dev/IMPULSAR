"""Los datos que carga el seed: quienes son y que venden.

Es contenido, no logica: se toca para agregar un emprendimiento o cambiar un
precio. Quien los escribe en la base es carga.py.
"""

from datetime import time

from app.blog.modelo_post import Categorias
from app.servicios.modelo import Rubros
from app.servicios.modelo_solicitud import EstadosSolicitud

# El dominio de mail marca a los usuarios que creo el seed: es lo que le
# permite a borrar() reconocerlos. La otra marca es el prefijo del nombre de
# las imagenes (ver imagenes.PREFIJO_IMAGEN).
EMAIL_SEED = "@seed.impulsar.test"

# La misma para todos, y escrita aca a proposito: son datos de prueba de una
# base de desarrollo, no hay nada que proteger y hace falta poder entrar.
PASSWORD = "impulsar123"

# Maipu, Mendoza. Las coordenadas van a mano y no por geocoding: el seed no
# tiene por que depender de una API externa para correr.
CENTRO = (-32.9833, -68.7833)


# Los usernames van sin tilde y de una sola palabra a proposito: el login
# busca por username exacto (ver views/auth.login), asi que "Lucía Herrera"
# obligaria a escribir el nombre completo con tilde para entrar a probar.
EMPRENDEDORES = ["Lucia", "Joaquin", "Carla", "Diego", "Valentina"]

CLIENTES = ["Nicolas", "Camila", "Bruno"]

# (dueño, titulo, categoria, descripcion, direccion, color de la foto)
EMPRENDIMIENTOS = [
    ("Lucia", "Huerta La Semilla", Categorias.ALIMENTOS,
     "Verduras agroecológicas de estación, cosechadas el mismo día que las "
     "entregamos. Bolsón semanal a domicilio en Maipú y alrededores.",
     "Ozamis 1200, Maipú, Mendoza", (86, 140, 74)),
    ("Lucia", "Conservas del Valle", Categorias.ALIMENTOS,
     "Dulces, escabeches y conservas hechos con fruta y verdura de la zona. "
     "Sin conservantes, en frascos de vidrio retornables.",
     "San Martín 850, Maipú, Mendoza", (176, 96, 60)),
    ("Joaquin", "Tejidos Andinos", Categorias.INDUMENTARIA,
     "Ruanas, chales y bufandas tejidos a telar con lana de oveja y llama. "
     "Cada pieza es única y lleva entre dos y cinco días de trabajo.",
     "Maza 340, Maipú, Mendoza", (120, 92, 160)),
    ("Joaquin", "Zapatillas Pintadas", Categorias.INDUMENTARIA,
     "Zapatillas de lona intervenidas a mano, con diseños a pedido. "
     "También restauramos y repintamos las que ya tenés.",
     "Vergara 90, Maipú, Mendoza", (60, 130, 176)),
    ("Carla", "Velas Aroma Sur", Categorias.HOGAR,
     "Velas de soja con esencias naturales, en frascos reutilizados. "
     "Armamos combos para regalo y velas personalizadas para eventos.",
     "Alsina 455, Maipú, Mendoza", (200, 150, 70)),
    ("Carla", "Cerámica Maipú", Categorias.ARTESANIAS,
     "Vajilla de gres hecha a torno: tazas, platos y fuentes para uso diario. "
     "Aptas para horno y lavavajillas. También damos talleres los sábados.",
     "Pescara 1100, Maipú, Mendoza", (150, 110, 95)),
    ("Diego", "Bicicletería El Piñón", Categorias.SERVICIOS,
     "Service completo, armado de ruedas y puesta a punto de cambios. "
     "Retiramos y entregamos la bici a domicilio sin costo dentro de Maipú.",
     "Urquiza 620, Maipú, Mendoza", (70, 70, 80)),
    ("Diego", "Reparación de Notebooks", Categorias.TECNOLOGIA,
     "Cambio de pantallas, teclados y baterías, limpieza y cambio de pasta "
     "térmica. Diagnóstico sin cargo y presupuesto antes de tocar nada.",
     "Godoy Cruz 210, Maipú, Mendoza", (55, 110, 130)),
    ("Valentina", "Cosmética Natural Ruda", Categorias.OTROS,
     "Jabones, bálsamos y aceites hechos con ingredientes de origen vegetal. "
     "Sin testeo en animales y con envases que recibimos de vuelta.",
     "Terrada 75, Maipú, Mendoza", (110, 150, 120)),
    ("Valentina", "Tostado Sur", Categorias.ALIMENTOS,
     "Café de especialidad tostado acá, en lotes chicos. Vendemos en grano o "
     "molido a tu método, y prestamos molinillo a los clientes del barrio.",
     "Sáenz Peña 1450, Maipú, Mendoza", (120, 80, 55)),
]

# titulo del emprendimiento -> productos (nombre, precio, disponible, descripcion)
PRODUCTOS = {
    "Huerta La Semilla": [
        ("Bolsón semanal chico", "6500.00", True,
         "Seis variedades de verdura de estación, para una o dos personas."),
        ("Bolsón semanal grande", "9800.00", True,
         "Diez variedades, alcanza para una familia de cuatro."),
        ("Docena de huevos de campo", "4200.00", True, None),
        ("Plantines de aromáticas", "1500.00", False,
         "Albahaca, perejil y romero. Vuelven en primavera."),
    ],
    "Conservas del Valle": [
        ("Dulce de durazno 400g", "3800.00", True, "Fruta de temporada, poca azúcar."),
        ("Berenjenas en escabeche", "4500.00", True, None),
        ("Tomate triturado 700g", "2900.00", True, None),
        ("Dulce de membrillo 500g", "4100.00", False, "Se agotó, vuelve en otoño."),
    ],
    "Tejidos Andinos": [
        ("Ruana de lana de oveja", "78000.00", True,
         "Tejida a telar, talle único. Colores naturales sin teñir."),
        ("Bufanda de llama", "32000.00", True, None),
        ("Chal calado", "45000.00", True, "Ideal para entretiempo."),
    ],
    "Velas Aroma Sur": [
        ("Vela de soja lavanda", "7200.00", True, "Frasco de 200g, 30 horas de duración."),
        ("Combo tres velas", "19000.00", True, "Lavanda, cítricos y vainilla."),
        ("Vela personalizada para evento", "9500.00", True,
         "Con etiqueta a tu gusto, mínimo diez unidades."),
    ],
    "Cerámica Maipú": [
        ("Taza de gres", "12500.00", True, "Apta para horno y lavavajillas."),
        ("Juego de cuatro platos", "48000.00", True, None),
        ("Taller de torno (2 horas)", "25000.00", True,
         "Sábados a la mañana, cupo de seis personas."),
    ],
    "Tostado Sur": [
        ("Café en grano 250g", "8900.00", True, "Blend de la casa, tueste medio."),
        ("Café molido 250g", "8900.00", True, "Decinos tu método y lo molemos así."),
        ("Bolsa de 1kg", "31000.00", True, None),
    ],
}

# titulo -> eventos (titulo, dias desde hoy, hora, descripcion)
EVENTOS = [
    ("Huerta La Semilla", "Feria agroecológica de la plaza", 6, time(9, 0),
     "Con toda la verdura de la semana y plantines a precio de feria."),
    ("Cerámica Maipú", "Taller abierto de torno", 13, time(10, 30),
     "Para quienes nunca tocaron el torno. Se llevan lo que hagan."),
    ("Tostado Sur", "Cata de café de especialidad", 3, time(18, 0),
     "Probamos tres orígenes distintos. Cupo limitado."),
    ("Tejidos Andinos", "Muestra de telar en el Museo", 21, None,
     "Exposición de piezas grandes, entrada libre."),
    ("Velas Aroma Sur", "Feria navideña", -18, time(17, 0),
     "Estuvimos con los combos de regalo."),
    ("Conservas del Valle", "Jornada de cosecha y conserva", -40, time(8, 30),
     "Vinimos con los frascos del año pasado."),
]

# emprendimiento -> servicios (titulo, rubro, descripcion, zona, precio o None)
# El precio en None es el caso de "a presupuestar", que es la diferencia con
# los productos: se cotiza contra el caso de cada cliente.
SERVICIOS = {
    "Bicicletería El Piñón": [
        ("Service completo de bicicleta", Rubros.OTROS,
         "Ajuste de cambios y frenos, centrado de ruedas y limpieza de transmisión.",
         "Maipú y alrededores", "18000.00"),
        ("Armado de rueda a medida", Rubros.OTROS,
         "Rayos, llanta y maza a elección. Se cotiza según los materiales.",
         "Maipú", None),
    ],
    "Reparación de Notebooks": [
        ("Cambio de pantalla", Rubros.INFORMATICA,
         "Traé el equipo o lo retiramos. El precio depende del modelo.",
         "Todo el Gran Mendoza", None),
        ("Limpieza y cambio de pasta térmica", Rubros.INFORMATICA,
         "Para equipos que se apagan solos o andan muy calientes.",
         "Todo el Gran Mendoza", "25000.00"),
    ],
}

# (cliente, servicio, descripcion, zona, estado, precio de respuesta, mensaje)
# Una de cada estado, para poder ver el panel del prestador con las tres.
SOLICITUDES = [
    ("Nicolas", "Cambio de pantalla",
     "Se me rompió la pantalla de una Lenovo ideapad 3. ¿La reparan?",
     None, EstadosSolicitud.PENDIENTE, None, None),
    ("Camila", "Service completo de bicicleta",
     "La bici hace ruido en los cambios y los frenos rozan. Es una rodado 29.",
     "Coquimbito", EstadosSolicitud.RESPONDIDA, "18000.00",
     "La dejamos como nueva. Traela un martes y te la entrego el jueves."),
    ("Bruno", "Armado de rueda a medida",
     "Quiero armar una rueda trasera para uso urbano, algo resistente.",
     None, EstadosSolicitud.CERRADA, "62000.00",
     "Con maza Shimano y llanta doble pared queda en ese precio."),
]

# (autor del review, emprendimiento, rating, comentario, respuesta del dueño)
RESENIAS = [
    ("Nicolas", "Huerta La Semilla", 5,
     "El bolsón llegó impecable y todo durísimo de fresco. Ya van tres semanas seguidas.",
     "¡Gracias Nicolás! La semana que viene sumamos acelga."),
    ("Camila", "Huerta La Semilla", 4,
     "Muy buena calidad. Solo que la entrega llegó un rato más tarde de lo pactado.", None),
    ("Bruno", "Tejidos Andinos", 5,
     "La ruana es una obra de arte. Se nota el trabajo que tiene atrás.", None),
    ("Camila", "Velas Aroma Sur", 5,
     "Compré el combo para regalar y quedó bárbaro. El aroma dura muchísimo.",
     "Gracias Camila, un gusto."),
    ("Nicolas", "Bicicletería El Piñón", 4,
     "Dejó la bici andando como nueva y me la trajo a casa. Recomendable.", None),
    ("Bruno", "Tostado Sur", 5,
     "El mejor café que conseguí en Maipú. Además te explican cómo prepararlo.", None),
    ("Camila", "Cerámica Maipú", 3,
     "Las tazas son lindas pero una llegó con una falla en el esmalte.",
     "Perdón Camila, escribinos y te la cambiamos sin cargo."),
]

# (cliente, emprendimiento, [(quien escribe, texto), ...], cuantos quedan sin leer)
CONVERSACIONES = [
    ("Nicolas", "Huerta La Semilla", [
        ("cliente", "Hola! Hacen entrega en Coquimbito?"),
        ("dueño", "Hola Nicolás! Sí, los martes y viernes a la tarde."),
        ("cliente", "Genial. Anotame un bolsón grande para el viernes."),
        ("dueño", "Listo, queda anotado. Te aviso cuando salga el reparto."),
    ], 0),
    ("Camila", "Cerámica Maipú", [
        ("cliente", "Buenas! Queda lugar en el taller del sábado?"),
        ("dueño", "Hola Camila! Quedan dos lugares."),
        ("cliente", "Perfecto, reservame uno."),
    ], 1),
    ("Bruno", "Reparación de Notebooks", [
        ("cliente", "Hola, se me rompió la pantalla de una Lenovo. Reparan ese modelo?"),
        ("cliente", "Es una ideapad 3, por si sirve el dato."),
    ], 2),
]

# usuario -> emprendimientos que marca como favoritos
FAVORITOS = {
    "Nicolas": ["Huerta La Semilla", "Tostado Sur", "Bicicletería El Piñón"],
    "Camila": ["Velas Aroma Sur", "Cerámica Maipú"],
    "Bruno": ["Tejidos Andinos"],
}

# usuario -> a quienes sigue
SEGUIMIENTOS = {
    "Nicolas": ["Lucia", "Valentina"],
    "Camila": ["Carla"],
    "Bruno": ["Joaquin", "Valentina"],
    "Lucia": ["Carla"],
}

# usuario -> horarios (dia_semana, abre, cierra) o (dia, None, None) si cierra
HORARIOS = {
    "Lucia": [(0, time(9, 0), time(13, 0)), (1, time(9, 0), time(13, 0)),
              (2, time(9, 0), time(13, 0)), (3, time(9, 0), time(13, 0)),
              (4, time(9, 0), time(17, 0)), (5, time(9, 0), time(12, 0)),
              (6, None, None)],
    "Carla": [(0, None, None), (1, time(15, 0), time(20, 0)),
              (2, time(15, 0), time(20, 0)), (3, time(15, 0), time(20, 0)),
              (4, time(15, 0), time(20, 0)), (5, time(10, 0), time(13, 0)),
              (6, None, None)],
    "Diego": [(0, time(8, 30), time(18, 0)), (1, time(8, 30), time(18, 0)),
              (2, time(8, 30), time(18, 0)), (3, time(8, 30), time(18, 0)),
              (4, time(8, 30), time(18, 0)), (5, None, None), (6, None, None)],
}
