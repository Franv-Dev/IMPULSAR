from flask import (
    render_template,Blueprint,flash,request,session,url_for,redirect,g
)
from models.user import User
from werkzeug.security import check_password_hash,generate_password_hash # -- encriptar contraseña
from db import db

import functools

auth = Blueprint("auth",__name__,url_prefix="/auth")

#Registrar un Usuario
@auth.route("/register", methods=("GET","POST"))

def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        rol = request.form.get("rol")
        email = request.form.get("email")
        if not username:
            error = "Se requiere nombre de usuario"
        elif not password:
            error = "Se requiere una contraseña"
        elif not rol:
            error = "debe ingresar un rol"
        
        
        user = User(
            username,
            generate_password_hash(password),#encripta contraseña
            rol,
            email
            )
        error = None

        
        user_name = User.query.filter_by(username = username).first() # filtrar si el usuario ya existe
        user_email = User.query.filter_by(email = email).first()

        if user_email != None:
            error = f"El email: {user_email} ya se encuentra registrado"

        if user_name != None:
            error = f"El usuario {username} ya se encuentra registrado"
            
        if error == None:
            error = f"El usuario {username} ya se encuentra registrado"
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('auth.login'))
        
        flash(error)

    return render_template('auth/register.html')

#Iniciar Sesion
@auth.route("/login", methods=("GET","POST"))

def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        
        error = None
        
        user = User.query.filter_by(username = username).first()
        

        if user is None:
            error = "El usuario  es incorrecto"
        elif not check_password_hash(user.password, password):
            error = "La contraseña incorrecta"

        if error == None:
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for('blog.index'))
        
        flash(error)

    return render_template('auth/login.html')

@auth.before_app_request

def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get_or_404(user_id)

#cerrar sesion
@auth.route('/logout')

def logout():
    session.clear()
    return redirect(url_for('blog.index'))

def login_required(view):
    @functools.wraps(view) #
    def wrapped_vew(**kwargs):
        
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    
    return wrapped_vew