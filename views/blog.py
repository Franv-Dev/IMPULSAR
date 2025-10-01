from flask import (
    render_template,Blueprint,redirect,flash,g,request,url_for,current_app
)
from werkzeug.exceptions import abort
from models.post import Post
from models.user import User
from views.auth import login_required
from db import db
from werkzeug.utils import secure_filename
import os
blog = Blueprint('blog',__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} #archivos permitidos

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#obtener un usuario
def get_user(id):
    user = User.query.get_or_404(id) 
    return user


@blog.route("/")
def index():
    posts = Post.query.all() # me trae todas las publicaciones
    posts = list(reversed(posts))
    return render_template('blog/index.html',posts = posts, get_user=get_user )


#Registrar un Post
@blog.route("/blog/create", methods=("GET","POST"))

@login_required

def create():
    if request.method == "POST":
        title = request.form.get("title")
        body = request.form.get("body")
        file = request.files.get("image") 


        error = None
        filename = None

        if not title:
            error = "Se requiere un titulo"
        

        if file and file.filename != "":
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(current_app.root_path, 'static/uploads', filename)
                file.save(upload_path)
            else:
                error = "Formato de imagen no permitido (usa png, jpg, jpeg o gif)"

        if error is not None:
            flash(error)
        else:
            post = Post(g.user.id,title,body,filename)
            db.session.add(post)
            db.session.commit()
            return redirect(url_for('blog.index'))
    
        flash(error)
    return render_template('blog/create.html')

def get_post(id,check_author = True):
    post = Post.query.get(id)
    if post is None:
        abort(404, f"id {id} de la publicacion no existe")
    
    if check_author and post.author != g.user.id:
        abort(404)

    return post

#Update Post /actualizar
@blog.route("/blog/update/<int:id>", methods=("GET","POST"))

@login_required
def update(id):
    post = get_post(id)

    if request.method == "POST":
        post.title = request.form.get("title")
        post.body = request.form.get("body")
        
        file = request.files.get("image")
        
        error = None
        if not post.title:
            error = "Se requiere un titulo"
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.root_path, 'static/uploads', filename))
            post.image = filename 
        
        if error is not None:
            flash(error)
        else:
            db.session.add(post)
            db.session.commit()
            return redirect(url_for('blog.index'))
    
        flash(error)
    return render_template('blog/update.html', post = post)

#eliminar un post
@blog.route('/blog/delete/<int:id>')
@login_required

def delete(id):
    post = get_post(id)
    db.session.delete(post)
    db.session.commit()

    return redirect(url_for('blog.index'))