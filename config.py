"""Configuracion de la aplicacion, separada por entorno.

Antes era un script plano con variables sueltas, asi que no habia forma de
tener valores distintos para desarrollo, testing y produccion sin duplicar
codigo. Ahora cada entorno es una clase que hereda de Config.

Cual se usa lo decide la variable de entorno FLASK_ENV (development por
defecto), o el parametro que se le pase a create_app().
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

from services.uploads import MAX_IMAGE_BYTES

load_dotenv()


def _raiz_del_proyecto():
    """La carpeta del repo, encontrada subiendo hasta dar con static/.

    No se usa current_app.root_path (que es la carpeta del modulo que crea la
    Flask) ni el directorio de este archivo: los dos dan por sentado donde vive
    el codigo, y el codigo se va a mudar a un paquete. Lo que no se mueve es
    static/ y las carpetas hermanas (migrations/, scripts/, tests/), asi que la
    raiz se busca por ahi y el resultado no cambia aunque config.py termine tres
    niveles mas adentro.
    """
    actual = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(actual, "static")):
            return actual
        padre = os.path.dirname(actual)
        if padre == actual:
            raise RuntimeError(
                "No se encontro la raiz del proyecto: ninguna carpeta padre de "
                f"{__file__} tiene un static/. Se puede fijar a mano con la "
                "variable de entorno RAIZ_PROYECTO."
            )
        actual = padre


# Se puede fijar a mano, que es lo que necesita un deploy donde el codigo y los
# archivos subidos no viven juntos (un volumen montado aparte, por ejemplo).
RAIZ_PROYECTO = os.getenv("RAIZ_PROYECTO") or _raiz_del_proyecto()


def _build_database_uri():
    """Arma la URI de conexion a MySQL a partir de las variables de entorno.

    Si existe DATABASE_URL se usa tal cual: es lo que suelen inyectar los
    servicios de deploy (Render, Railway) y tiene prioridad.
    """
    url_completa = os.getenv("DATABASE_URL")
    if url_completa:
        return url_completa

    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME", "")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


class Config:
    """Valores comunes a todos los entornos."""

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rutas absolutas, calculadas desde la raiz del repo y no desde donde vive
    # el modulo que crea la app. Antes cada vista se armaba la suya con
    # current_app.root_path (habia seis copias): si el codigo se muda a un
    # paquete, root_path deja de ser la raiz y las imagenes ya subidas quedan
    # colgadas. Se pasan explicitas a Flask en create_app().
    STATIC_FOLDER = os.path.join(RAIZ_PROYECTO, "static")
    TEMPLATES_FOLDER = os.path.join(RAIZ_PROYECTO, "templates")
    # Donde se guardan las imagenes que suben los usuarios. Se lee con
    # services.uploads.carpeta_uploads(), que es el unico lugar que la arma.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER") or os.path.join(STATIC_FOLDER, "uploads")
    # Donde van las subidas que NO son publicas: hoy la foto de una solicitud de
    # presupuesto y el documento de un pedido de verificacion (una matricula con
    # nombre y numero real). Se leen con services.uploads.carpeta_privada().
    #
    # HERMANA de static/ y no una subcarpeta de UPLOAD_FOLDER, que es lo que
    # parecia natural: Flask sirve static_folder RECURSIVAMENTE, asi que
    # static/uploads/privado/doc.png se bajaria por /static/uploads/privado/doc.png
    # sin pasar por ninguna vista. La proteccion de estas dos fotos ya esta en el
    # codigo (ver app/servicios/vistas.py), y esto es la segunda capa: que el
    # archivo tampoco este donde un nginx puesto adelante, o un listado de
    # directorio, lo puedan alcanzar sin preguntarle nada a la app.
    PRIVATE_UPLOAD_FOLDER = os.getenv("PRIVATE_UPLOAD_FOLDER") or os.path.join(
        RAIZ_PROYECTO, "uploads_privados"
    )

    MAPTILER_KEY = os.getenv("MAPTILER_KEY")

    # Tamanio maximo de subida: sin esto un archivo enorme puede agotar la
    # memoria y el disco del servidor.
    MAX_CONTENT_LENGTH = MAX_IMAGE_BYTES

    # Cuanto dura el token de la API. Antes estaba hardcodeado en api_login.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    # Cantidad de emprendimientos por pagina en los listados.
    POSTS_POR_PAGINA = 9

    @classmethod
    def init_app(cls, app):
        """Gancho para validaciones propias de cada entorno."""


class DevelopmentConfig(Config):
    """Para trabajar en tu maquina.

    Tiene claves por defecto a proposito, para que el proyecto arranque recien
    clonado sin configurar nada. Nunca se usan en produccion (ver
    ProductionConfig, que directamente no arranca sin claves reales).
    """

    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "clave-solo-para-desarrollo")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-solo-para-desarrollo")


class TestingConfig(Config):
    """Para correr los tests: base en memoria y sin CSRF."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "clave-de-testing-suficientemente-larga-32b"
    JWT_SECRET_KEY = "jwt-de-testing-suficientemente-largo-32b"
    # Los tests postean formularios directamente; el CSRF se prueba aparte,
    # en su propio test, activandolo a mano.
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Para el servidor real."""

    DEBUG = False
    # Cookies de sesion mas seguras: solo por HTTPS, no accesibles desde JS y
    # no enviadas en requests que vienen de otro sitio.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def init_app(cls, app):
        """Corta el arranque si faltan claves.

        Antes estas claves tenian un valor por defecto hardcodeado: si te
        olvidabas de configurarlas en el servidor, la app arrancaba igual pero
        con una clave publica y conocida, y cualquiera podia falsificar tokens
        JWT o cookies de sesion. Es mejor no arrancar que arrancar inseguro.
        """
        faltantes = [
            nombre
            for nombre in ("SECRET_KEY", "JWT_SECRET_KEY")
            if not app.config.get(nombre)
        ]
        if faltantes:
            raise RuntimeError(
                "Faltan variables de entorno obligatorias en produccion: "
                + ", ".join(faltantes)
            )


# Nombre de entorno -> clase de configuracion.
CONFIGURACIONES = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(nombre=None):
    """Devuelve la clase de configuracion segun el nombre o FLASK_ENV."""
    nombre = nombre or os.getenv("FLASK_ENV") or "default"
    return CONFIGURACIONES.get(nombre, DevelopmentConfig)
