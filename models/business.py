from db import db 

class Business(db.Model):
    id = db.Column(db.Integer,primary_key=True,autoincrement=True)
    localname =  db.String(100)
    adress = db.String(200)
    body = db.Column(db.Text)
    owner = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image = db.Column(db.String(100), nullable=True)

    def __init__(self,localname,adress,body,owner,image):
        self.localname = localname
        self.adress = adress
        self.body = body
        self.owner = owner
        self.imgage = image
    
    def __repr__(self):
        return f"Business:{self.localname}"
    
    def serialize(self):
        return {
            "localname " : self.localname,
            "adress" : self.adress,
            "body" : self.body,
            "owner" : self.owner,
            "image" : self.image
        }