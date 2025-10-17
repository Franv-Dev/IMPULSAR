from flask import Blueprint, jsonify
from models.post import Post

posts_api = Blueprint("posts_api", __name__, url_prefix="/api/posts")

@posts_api.get("/")
def list_posts():
    posts = Post.query.order_by(Post.created.desc()).all()
    return jsonify([p.serialize() for p in posts]), 200

@posts_api.get("/<int:post_id>")
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify(post.serialize()), 200
