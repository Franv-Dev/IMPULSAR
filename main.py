from flask import Flask,redirect,url_for
from config import DATABASE_DATABASE_URI
from db import db
from dotenv import load_dotenv
from views.auth import auth
from views.blog import blog
from flask_jwt_extended import JWTManager
import os
from flask_migrate import Migrate
from views.posts_api import posts_api



load_dotenv()

app= Flask(__name__)#inicializar flask

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATION"] = False
app.secret_key = os.getenv("SECRET_KEY")

db.init_app(app)
migrate = Migrate(app,db)
#Token JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
jwt = JWTManager(app)

#importar vistas
app.register_blueprint(auth)
app.register_blueprint(blog)
app.register_blueprint(posts_api)

@app.route("/")
def index():
    return redirect(url_for("blog.index"))


with app.app_context():
    db.drop_all()
    db.create_all()




if __name__ == "__main__":#para arrancar la app
    app.run(debug=True) #-- arrancar la app(debug = para que se vaya actualizando)