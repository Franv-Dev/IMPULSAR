# 🌟 IMPULSAR – Plataforma de Gestión y Promoción de Emprendimientos

**IMPULSAR** es una aplicación web desarrollada con **Flask (Python)** y **MySQL**, diseñada para fortalecer el ecosistema emprendedor local.  
El sistema permite a los usuarios **crear, administrar y difundir emprendimientos**, gestionando imágenes, ubicaciones, eventos y datos de contacto de forma simple, moderna y escalable.

---

## 🏙️ Descripción de la problemática regional

En la actualidad, muchos **emprendimientos locales carecen de presencia digital** o de herramientas tecnológicas que les permitan difundir sus productos y servicios de manera efectiva.  
Esto dificulta su visibilidad y limita el acceso a nuevos clientes, socios o ferias locales.

**IMPULSAR** surge como respuesta a esta problemática, brindando una plataforma gratuita y colaborativa que:

- Centraliza la información de los emprendimientos locales.  
- Permite a los usuarios crear perfiles con fotos, descripciones y contactos.  
- Facilita la conexión entre emprendedores, clientes y eventos del ecosistema local.  
- Promueve el desarrollo económico y la identidad regional a través de la tecnología.

---

## 👥 Integrantes del grupo

| Nombre | Rol principal |
|--------|----------------|
| 🧑‍💻 **Franco Villarroel** | Desarrollo Backend / Base de Datos |
| 👨‍💻 **Tomás Muñoz** | Desarrollo Frontend / Diseño UI |
| 👨‍💻 **Leandro Briceño** | Integración API y Testing |
| 👨‍💻 **Mateo Gómez** | Coordinación general / Arquitectura y Documentación |

📍 Proyecto académico desarrollado en el marco del desarrollo de sistemas web con **Flask y MySQL**.

---

## 🧭 Descripción general del sistema

IMPULSAR busca brindar un **espacio digital para potenciar la visibilidad de los emprendedores**, promoviendo el desarrollo local mediante herramientas de autogestión y acceso abierto.

A través de una interfaz moderna y un backend modular, los usuarios pueden:

- Registrar emprendimientos.  
- Publicar productos o servicios.  
- Agregar información de contacto, imágenes y ubicación.  
- Participar en eventos o ferias locales.

Los administradores, por su parte, pueden **gestionar usuarios, validar contenido y mantener actualizada la base de datos**.

---

## 🎯 Objetivos del proyecto

### 🏁 Objetivo general
Desarrollar un sistema integral que centralice la información de los emprendimientos locales y mejore su difusión en un entorno digital accesible y seguro.

### 🎯 Objetivos específicos
- Implementar una **API REST** modular con Flask.  
- Diseñar un **frontend propio (HTML, CSS, JS)** sin frameworks externos.  
- Integrar **autenticación con roles (Administrador / Emprendedor / Visitante)**.  
- Permitir **subida de imágenes y gestión de publicaciones**.  
- Incorporar **secciones de eventos y ferias** locales.  
- Garantizar la seguridad mediante **JWT y sesiones**.  

---

## 🧩 Tecnologías utilizadas

| Categoría | Tecnologías |
|------------|-------------|
| **Backend** | Python, Flask, SQLAlchemy, Flask-JWT-Extended |
| **Frontend** | HTML5, CSS3, JavaScript, Jinja2 |
| **Base de Datos** | MySQL |
| **Entorno** | Flask CLI, dotenv |
| **Pruebas** | Pytest |
| **Control de versiones** | Git / GitHub |

---

## 🔐 Roles y autenticación

- **Administrador:** gestiona usuarios y publicaciones.  
- **Emprendedor:** crea y edita sus emprendimientos.  
- **Visitante:** explora publicaciones sin iniciar sesión.  

El sistema combina dos mecanismos:
- **Sesiones tradicionales** (para el frontend).  
- **JWT (JSON Web Tokens)** (para la API REST).  

---

## ⚙️ Instalación, migraciones y ejecución

### 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/usuario/IMPULSAR.git
cd IMPULSAR
```

### 2️⃣ Crear entorno virtual
```bash
python -m venv venv
venv\Scripts\activate  # En Windows
source venv/bin/activate  # En Linux/Mac
```

### 3️⃣ Instalar dependencias
```bash
pip install -r requirements.txt
```

> Para desarrollo (incluye las herramientas de testing):
> ```bash
> pip install -r requirements-dev.txt
> ```

### 4️⃣ Configurar las variables de entorno
Copiá el archivo de ejemplo y completá los valores:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac
```

Para generar las claves de seguridad:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> En **desarrollo** podés dejar `SECRET_KEY` y `JWT_SECRET_KEY` vacías: hay valores
> por defecto. En **producción** son obligatorias y la app no arranca sin ellas,
> a propósito: arrancar con una clave conocida permitiría falsificar sesiones y tokens.

### 5️⃣ Crear la base de datos
```sql
CREATE DATABASE impulsar_db;
```

### 6️⃣ Aplicar migraciones
```bash
flask --app wsgi db upgrade
```

> No hace falta `flask db init`: la carpeta `migrations/` ya está en el repo.
> Usá `flask --app wsgi db migrate -m "descripción"` solo cuando cambies los modelos.

### 7️⃣ Ejecutar la aplicación
```bash
flask --app wsgi run
```

Abrí tu navegador en:  
👉 [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🚀 Ejemplo de uso de la API

### 1️⃣ Registro
**POST** `/auth/api/register`
```json
{
  "username": "franco",
  "email": "franco@example.com",
  "password": "123456"
}
```

### 2️⃣ Login
**POST** `/auth/api/login`
```json
{
  "email": "franco@example.com",
  "password": "123456"
}
```
**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "user": {
    "id": 1,
    "username": "franco",
    "email": "franco@example.com",
    "rol": "usuario"
  }
}
```

### 3️⃣ Crear emprendimiento
**POST** `/blog/create`  
Headers:
```
Authorization: Bearer <token>
```
Body:
```json
{
  "title": "Panificados San Luis",
  "body": "Emprendimiento familiar de panificación artesanal."
}
```

### 4️⃣ Obtener emprendimientos
**GET** `/api/posts/`

Parámetros opcionales:

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| `page` | Número de página | `1` |
| `per_page` | Resultados por página (máximo 50) | `9` |
| `q` | Texto a buscar en título y descripción | — |

**Respuesta:**
```json
{
  "items": [ { "id": 1, "title": "Panificados San Luis", "...": "..." } ],
  "page": 1,
  "per_page": 9,
  "pages": 3,
  "total": 25,
  "has_next": true,
  "has_prev": false
}
```

---

## 🧪 Cómo ejecutar las pruebas

La suite cubre autenticación, roles, CRUD de emprendimientos, permisos, reseñas,
geocoding, subida de imágenes, paginación y configuración de la app.

```bash
pytest -v
```

Los tests usan **SQLite en memoria**, así que no necesitás tener MySQL corriendo
ni configurar nada: la base se crea y se destruye en cada test.

```bash
pytest tests/test_blog.py            # solo un archivo
pytest -k resenia                    # solo los tests que coincidan con un nombre
```

Se ejecutan también automáticamente en cada push y Pull Request
(ver `.github/workflows/tests.yml`).

---

## 📘 Documentación de la API (Postman Collection)

Podés importar la colección de Postman para probar los endpoints REST:  
📁 `IMPULSAR_API.postman_collection.json`

Incluye ejemplos de:
- Registro y login JWT  
- CRUD de emprendimientos  
- Endpoints protegidos por rol  

---

## 🖼️ Capturas del frontend

| Vista | Descripción |
|-------|--------------|
| ![Inicio](static/docs/home.png) | Página principal con hero, buscador y cards dinámicas |
| ![Login](static/docs/login.png) | Formulario de inicio de sesión |
| ![Mis Emprendimientos](static/docs/mis_posts.png) | Panel del usuario con CRUD de publicaciones |
| ![Detalle](static/docs/detail.png) | Vista individual del emprendimiento |

---

## 🧩 Variables de entorno

Están documentadas en [`.env.example`](.env.example), que se copia como `.env`
(ver paso 4️⃣ de la instalación). Ese archivo nunca se sube al repositorio.

---

## 🏗️ Estructura del proyecto

```
main.py               create_app(): arma y configura la aplicación
config.py             Configuración por entorno (development/testing/production)
db.py                 Instancia de SQLAlchemy y utilidades comunes
models/               Modelos de datos (User, Post, Review)
views/                Blueprints: auth, blog, profile, api y páginas estáticas
services/             Lógica reutilizable: geocoding y subida de imágenes
templates/            Plantillas Jinja2
static/               CSS, JS, íconos e imágenes subidas
migrations/           Historial de migraciones de Alembic
tests/                Suite de pytest (conftest.py tiene las fixtures)
```

El proyecto usa el patrón **application factory**: la app no se crea al importar
el módulo sino dentro de `create_app()`, lo que permite levantarla con distintas
configuraciones (por ejemplo, SQLite en memoria para los tests).

---

## 🌐 (Opcional) Despliegue

IMPULSAR puede desplegarse en servicios como **Render**, **Railway** o **PythonAnywhere**.

Variables requeridas:
```
DATABASE_URL=mysql+pymysql://root:password@host:3306/impulsar_db
SECRET_KEY=clave-secreta
JWT_SECRET_KEY=clave-jwt
```

Para producción, con `--app` explícito para no depender del `.env` de la máquina:
```bash
flask --app wsgi run --host=0.0.0.0 --port=8080
```

---

## 💡 Futuras mejoras

- Buscador inteligente por categorías y ubicación.  
- Panel de métricas con estadísticas de visitas.  
- Sistema de notificaciones internas y mensajes.  
- Optimización de carga de imágenes y miniaturas.  
- Integración con APIs externas (Google Maps, ferias locales, etc.).  

---

## 🧾 Licencia

Este proyecto se distribuye bajo licencia **MIT**, permitiendo su uso y modificación para fines educativos y de desarrollo.
