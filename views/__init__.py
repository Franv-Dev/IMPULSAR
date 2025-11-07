
from .auth import auth          
from .blog import blog          
from .posts_api import posts_api  
from .profile import profile


def register_blueprints(app):

    app.register_blueprint(auth)
    app.register_blueprint(blog)
    app.register_blueprint(posts_api)
    app.register_blueprint(profile)
