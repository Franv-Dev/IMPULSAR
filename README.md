
# 🌟 IMPULSAR – Plataforma de Gestión y Promoción de Emprendimientos

**IMPULSAR** es una aplicación web desarrollada con **Flask (Python)** y **MySQL**, diseñada para fortalecer el ecosistema emprendedor local.  
El sistema permite a los usuarios **crear, administrar y difundir emprendimientos**, gestionando imágenes, ubicaciones, eventos y datos de contacto de forma simple, moderna y escalable.

---

## 🧭 Descripción general

IMPULSAR busca brindar un **espacio digital para potenciar la visibilidad de los emprendedores**, promoviendo el desarrollo local mediante herramientas de autogestión y acceso abierto.  

A través de una interfaz clara y un backend modular, los usuarios pueden registrar emprendimientos, publicar productos o servicios, agregar información de contacto, y participar en eventos o ferias.  
Por su parte, los administradores pueden gestionar usuarios, validar contenido y mantener actualizada la base de datos del ecosistema.

---

## 🎯 Objetivos del proyecto

### 🏁 Objetivo general
Desarrollar un sistema integral que centralice la información de los emprendimientos y mejore su difusión en un entorno digital accesible y seguro.

### 🎯 Objetivos específicos
- Implementar una **API REST** modular con Flask.  
- Diseñar un **frontend sin frameworks externos** (HTML, CSS, JS puros).  
- Integrar **autenticación de usuarios y roles (Administrador / Emprendedor / Visitante)**.  
- Permitir la **carga de imágenes, ubicaciones y descripciones** de los emprendimientos.  
- Incorporar una sección de **eventos y ferias con calendario interactivo**.  
- Administrar publicaciones desde un **panel interno seguro**.

---

## 🧩 Tecnologías utilizadas

| Categoría | Herramientas |
|------------|--------------|
| **Backend** | Python, Flask, SQLAlchemy, Flask-JWT-Extended |
| **Frontend** | HTML5, CSS3, JavaScript, Jinja2 |
| **Base de datos** | MySQL |
| **Entorno** | Flask CLI, dotenv, WSGI |
| **Control de versiones** | Git / GitHub |

---

## ⚙️ Arquitectura del sistema

El proyecto sigue un modelo **MVC simplificado (Modelo – Vista – Controlador)** con **Blueprints de Flask**, asegurando escalabilidad y claridad en la estructura.
IMPULSAR/
│
├── main.py # Punto de entrada principal
├── db.py # Configuración de conexión con MySQL
│
├── models/ # Modelos de base de datos
│ ├── user.py # Clase User (usuarios del sistema)
│ └── post.py # Clase Post (publicaciones de emprendedores)
│
├── routes/ # Rutas y controladores (Blueprints)
│ ├── auth.py # Registro, login, JWT y sesiones
│ └── main.py # Rutas principales y vistas HTML
│
├── static/ # Recursos estáticos (CSS, JS, imágenes)
│ ├── css/
│ ├── js/
│ └── img/
│
├── templates/ # Plantillas HTML (vistas)
│ ├── base.html
│ ├── index.html
│ ├── login.html
│ ├── register.html
│ ├── dashboard.html
│ └── perfil.html
│
├── .env # Variables de entorno
├── requirements.txt # Dependencias del proyecto
└── README.md

---

## 🔐 Roles y autenticación

- **Administrador:** gestiona usuarios, publicaciones y eventos.  
- **Emprendedor:** crea y modifica sus publicaciones, carga imágenes y medios de contacto.  
- **Visitante:** explora emprendimientos y eventos.

El sistema usa dos métodos de autenticación:
- **Sesiones tradicionales:** para navegación en vistas HTML.
- **JWT (JSON Web Tokens):** para acceso API y servicios externos.

---

## 🌎 Funcionalidades principales

✅ Registro e inicio de sesión de usuarios  
✅ Creación, edición y eliminación de publicaciones  
✅ Carga de imágenes, descripciones y datos de contacto  
✅ Geolocalización de emprendimientos  
✅ Calendario de eventos y ferias locales  
✅ Panel administrativo con control de roles  
✅ API REST conectada a la base de datos MySQL  

---

## 🧠 Diseño y modularización

- **Modelos:** gestionan la lógica de datos.  
- **Rutas (Blueprints):** organizan las funcionalidades en módulos.  
- **Templates:** renderizan las vistas con Jinja2.  
- **Static:** contiene los estilos, scripts y recursos multimedia.  

Esta separación permite mantener el código limpio, escalable y fácil de mantener.

---

🛠️ Instalación y ejecución

 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/usuario/IMPULSAR.git
cd IMPULSAR

2️⃣ Crear entorno virtual e instalar dependencias

python -m venv venv
venv\Scripts\activate     # En Windows
source venv/bin/activate  # En Linux/Mac
pip install -r requirements.txt

3️⃣ Configurar variables de entorno
FLASK_APP=main.py
FLASK_ENV=development
SECRET_KEY=tu_clave_secreta
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=impulsar_db
DB_HOST=localhost

4️⃣ Crear la base de datos
CREATE DATABASE impulsar_db;

5️⃣ Ejecutar la aplicación
flask run

💡 Futuras mejoras

Implementar buscador inteligente por categorías y ubicación.

Incorporar panel de métricas para emprendimientos destacados.

Agregar sistema de notificaciones internas y mensajes.

Optimizar carga de imágenes y miniaturas.

Añadir integración con APIs externas (mapas, ferias provinciales, etc.).

👩‍💻 Equipo de desarrollo

Proyecto desarrollado por el equipo de IMPULSAR:

Integrante	Rol principal
🧑‍💻 Franco Villarroel	Desarrollo Backend / Base de datos
👨‍💻 Tomás Muñoz	Desarrollo Frontend / Diseño UI
👨‍💻 Leandro Briceño	Integración y Testing
👨‍💻 Mateo Gómez	Coordinación general / Arquitectura y Documentación

📍 Proyecto académico desarrollado en el marco del desarrollo de sistemas web con Flask y MySQL.

🧾 Licencia

Este proyecto se distribuye bajo licencia MIT, de libre uso y modificación para fines educativos o de desarrollo.

