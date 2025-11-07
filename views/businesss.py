from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort
from models.business import Business
from models.user import User
from views.auth import login_required
from db import db
from werkzeug.utils import secure_filename
import os
from sqlalchemy import func

business = Blueprint("business",__name__,url_prefix="/business")

# Configuración
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user(id):
    """Obtener usuario por ID o devolver 404."""
    return User.query.get_or_404(id)

@business.route("/")
def index():
    business = Business.query.all() 
    business = list(reversed(business))
    return render_template('blog/index.html',business = business, get_user=get_user )

@business.route("/create", methods=("GET", "POST"))
@login_required

def create():
    if request.method == "POST":
        localname = request.form.get("localname", "").strip()
        adress = request.form.get("adress", "")
        body = request.form.get("body", "descripcion").strip() or "descripcion"
        owner = request.form.get("owner", "").strip()
        file = request.files.get("image")

        error = None
        filename = None

        if not localname:
            error = "Se requiere nombre del emprendimiento"
        elif not adress:
            error = "Se requiere una dirección"
        elif not body:
            error = "Se requiere un cuerpo"
        

        
        if error is None and Business.query.filter_by(adress=adress).first():
            error = f"La direccion:{adress} ya se encuentra registrado"

        if file and file.filename != "":
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(current_app.root_path, 'static/uploads', filename)
                file.save(upload_path)
            else:
                error = "Formato de imagen no permitido (usa png, jpg, jpeg o gif)"
        if error is None:
            business = Business(
                localname=username,
                adress=email,
                owner=g.user.id 
                image = filename
            )
            db.session.add(user)
            db.session.commit()
            flash("Creacion exitosa.")
            return redirect(url_for('profile.view_profile'))

        flash(error)

    return render_template('profile.html')

def get_business(id,check_author = True):
    business = Business.query.get(id)
    if business is None:
        abort(404, f"id {id} de la publicacion no existe")
    
    if check_author and business.owner != g.user.id:
        abort(404)

    return business

@business.route("/update/<int:id>", methods=("GET","POST"))

@login_required
def update(id):
    business = get_business(id)

    if request.method == "POST":
        business.localname = request.form.get("localname")
        business.adress = request.form.get("adress")
        business.body = request.form.get("body")
        
        file = request.files.get("image")
        
        error = None
        if not business.localname:
            error = "Se requiere un nombre"
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.root_path, 'static/uploads', filename))
            business.image = filename 
        
        if error is not None:
            flash(error)
        else:
            db.session.add(post)
            db.session.commit()
            return redirect(url_for('blog.index'))
    
        flash(error)
    return render_template('blog/update.html', business = business)

@business.route('delete/<int:id>')
@login_required

def delete(id):
    business = get_business(id)
    db.session.delete(business)
    db.session.commit()

    return redirect(url_for('blog.index'))