from flask import Flask
from config import DATABASE_DATABASE_URI
from db import db
from dotenv import load_dotenv
from views.auth import auth
from views.blog import blog
import os
from flask_migrate import Migrate

load_dotenv()

app= Flask(__name__)#inicializar flask

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATION"] = False
app.secret_key = os.getenv("SECRET_KEY")

db.init_app(app)
migrate = Migrate(app,db)

with app.app_context():
    db.drop_all()
    db.create_all()

#importar vistas
app.register_blueprint(auth)
app.register_blueprint(blog)


if __name__ == "__main__":#para arrancar la app
    app.run(debug=True) #-- arrancar la app(debug = para que se vaya actualizando)