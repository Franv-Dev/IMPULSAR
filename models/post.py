from db import db
from datetime import datetime
class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.Integer,db.ForeignKey("users.id"),nullable=False)
    title = db.Column(db.String(100))
    body = db.Column(db.Text)
    created = db.Column(db.DateTime,nullable=False,default = datetime.utcnow)
    image = db.Column(db.String(100),nullable=True)

    def __init__(self,author,title,body,image):
        self.author = author
        self.title = title
        self.body = body
        self.image = image
    
    def __repr__(self):#devuelve Informacion:String
        return f"Post: {self.title}"
            # Método para devolver JSON
    def serialize(self):
        return {
            "id": self.id,
            "author": self.author,  # ID del usuario autor
            "title": self.title,
            "body": self.body,
            "image": self.image,
            "created": self.created.isoformat() if self.created else None
        }