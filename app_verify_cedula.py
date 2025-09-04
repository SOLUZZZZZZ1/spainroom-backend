# -*- coding: utf-8 -*-
import os
import hashlib
import shutil
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# =========================
# Paths & Const
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

db = SQLAlchemy()

# =========================
# Modelos
# =========================
class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    price = db.Column(db.Integer)
    city = db.Column(db.String(120))
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    photo = db.Column(db.String(300), nullable=True)

class CedulaCheck(db.Model):
    __tablename__ = "cedula_checks"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    status = db.Column(db.String(50), default="pending")  # pending/ok/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    source_doc_url = db.Column(db.String(300))
    source_doc_hash = db.Column(db.String(128))

# =========================
# Seed de demo
# =========================
def _maybe_seed():
    if Room.query.count() == 0:
        demo = [
            Room(title="Habitación centro Madrid", description="Luminoso y céntrico", price=400, city="Madrid", address="Calle Mayor, 1"),
            Room(title="Habitación en Valencia", description="Cerca de la playa", price=380, city="Valencia", address="Avenida del Puerto, 22"),
        ]
        db.session.add_all(demo)
        db.session.commit()

# =========================
# Utils
# =========================
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# =========================
# App Factory
# =========================
def create_app() -> Flask:
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)

    # DB
    default_uri = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

    # CORS
    CORS(
        app,
        resources={r"/*": {"origins": [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://*.vercel.app",
            "https://spainroom.es"
        ]}},
        supports_credentials=False,
    )

    db.init_app(app)

    # ===== Blueprints =====
    # Bot de voz (ES/EN)
    try:
        from voice_bot import bp_voice
        app.register_blueprint(bp_voice)
    except Exception as e:
        print(f"[WARN] Voice module not loaded: {e}")

    # Crear tablas + seed
    with app.app_context():
        db.create_all()
        _maybe_seed()

    # --------- Rutas Salud ---------
    @app.get("/health")
    def health():
        return jsonify(ok=True, service="spainroom-cedula-backend")

    # --------- Rooms ---------
    @app.get("/api/rooms")
    def list_rooms():
        city = (request.args.get("city") or "").strip()
        q = Room.query
        if city:
            q = q.filter(Room.city.ilike(f"%{city}%"))
        rooms = q.order_by(Room.created_at.desc()).all()
        return jsonify([{
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "price": r.price,
            "city": r.city,
            "address": r.address,
            "photo": r.photo,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        } for r in rooms])

    @app.get("/api/rooms/<int:room_id>")
    def get_room(room_id: int):
        r = Room.query.get_or_404(room_id)
        return jsonify({
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "price": r.price,
            "city": r.city,
            "address": r.address,
            "photo": r.photo,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        })

    # --------- Upload ---------
    @app.post("/api/rooms/<int:room_id>/upload")
    def upload_file(room_id: int):
        r = Room.query.get_or_404(room_id)
        if "file" not in request.files:
            return jsonify(error="No file part"), 400
        f = request.files["file"]
        if f.filename == "":
            return jsonify(error="No selected file"), 400
        if not allowed_file(f.filename):
            return jsonify(error="Invalid extension"), 400

        filename = secure_filename(f.filename)
        save_dir = os.path.join(UPLOAD_DIR, str(room_id))
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, filename)
        f.save(path)

        file_url = f"/uploads/{room_id}/{filename}"
        r.photo = file_url
        db.session.commit()
        return jsonify(ok=True, file_url=file_url, file_hash=file_hash(path))

    # --------- Serve uploads ---------
    @app.get("/uploads/<path:relpath>")
    def serve_uploads(relpath: str):
        safe_rel = os.path.normpath(relpath).replace("\\", "/").lstrip("/")
        base = UPLOAD_DIR
        if "/" in safe_rel:
            first, rest = safe_rel.split("/", 1)
            return send_from_directory(os.path.join(base, first), rest)
        return send_from_directory(base, safe_rel)

    return app

# =========================
# Main (solo local)
# =========================
if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5001, debug=True)
