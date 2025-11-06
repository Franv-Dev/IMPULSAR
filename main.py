from flask import Flask, redirect, url_for, render_template
from config import DATABASE_DATABASE_URI
from db import db
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
import os


# Blueprints
from views.auth import auth
from views.blog import blog
from views.posts_api import posts_api
from views.about import about
from views.contact import contact
from views.terms import terms
from views.privacy import privacy


# Cargar variables de entorno (.env)
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Configuración de base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_DATABASE_URI
# OJO: es TRACK_MODIFICATIONS (plural)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Secret key para sesiones
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
jwt = JWTManager(app)

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)

# Registrar blueprints
app.register_blueprint(auth)
app.register_blueprint(blog)
app.register_blueprint(posts_api)
app.register_blueprint(about)
app.register_blueprint(contact)
app.register_blueprint(terms)
app.register_blueprint(privacy)

@app.route("/")
def index():
    return render_template("home.html")


if __name__ == "__main__":
    # Si querés crear tablas automáticamente en desarrollo, podés descomentar esto:
    with app.app_context():
        db.create_all()
        app.run(debug=True)
