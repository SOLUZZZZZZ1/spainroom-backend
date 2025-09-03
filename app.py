# -*- coding: utf-8 -*-
import os
import io
import re
import hashlib
import shutil
import threading
import time
from datetime import datetime, date
from typing import Optional

import requests
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
# Config externos (ej. Cédula)
# =========================
CEDULA_API_URL = os.getenv("CEDULA_API_URL", "")
CEDULA_API_KEY = os.getenv("CEDULA_API_KEY", "")
CLIENT_CERT = os.getenv("CEDULA_CLIENT_CERT")
CLIENT_KEY = os.getenv("CEDULA_CLIENT_KEY")
CLIENT_P12 = os.getenv("CEDULA_CLIENT_P12")
CLIENT_P12_PASS = os.getenv("CEDULA_CLIENT_P12_PASS")

# =========================
# App Factory
# =========================
def create_app() -> Flask:
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)

    # DB URI por defecto: SQLite local en /instance/app.db
    default_uri = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

    # CORS (ajusta orígenes para prod si quieres)
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

    # Inicializar DB
    db.init_app(app)

    # ---- Blueprints opcionales (no rompen si faltan) ----

    # Pagos (Stripe)
    try:
        from payments import bp_pay
        app.register_blueprint(bp_pay)
    except Exception as e:
        print(f"[WARN] Payments module not loaded: {e}")

    # Oportunidades (contacto)
    try:
        from opportunities import bp_opp
        app.register_blueprint(bp_opp)
    except Exception as e:
        print(f"[WARN] Opportunities module not loaded: {e}")

    # Voice Bot (ES/EN)
    try:
        from voice_bot import bp_voice
        app.register_blueprint(bp_voice)
    except Exception as e:
        print(f"[WARN] Voice module not loaded: {e}")

    # Crear tablas y seed
    with app.app_context():
        db.create_all()
        _maybe_seed()

    # --------- Rutas Salud ---------
    @app.get("/health")
    def health():
        return jsonify(ok=True, service="spainroom-backend")

    @app.get("/health/db")
    def health_db():
        try:
            db.session.execute(db.select(Room).limit(1)).first()
            return jsonify(ok=True, db=True)
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 500

    # --------- Rooms (demo) ---------
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

    # --------- Subida de archivos (PDF/JPG/PNG) ---------
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

        # guarda hash y url
        file_url = f"/uploads/{room_id}/{filename}"
        r.photo = file_url
        db.session.commit()
        return jsonify(ok=True, file_url=file_url, file_hash=file_hash(path))

    # --------- Servir uploads ---------
    @app.get("/uploads/<path:relpath>")
    def serve_uploads(relpath: str):
        # relpath puede ser "123/archivo.pdf" o "archivo.pdf"
        safe_rel = os.path.normpath(relpath).replace("\\", "/").lstrip("/")
        base = UPLOAD_DIR
        # si contiene subcarpeta (ej. por room_id)
        if "/" in safe_rel:
            first, rest = safe_rel.split("/", 1)
            return send_from_directory(os.path.join(base, first), rest)
        return send_from_directory(base, safe_rel)

    # --------- Cédula (endpoints demo) ---------
    @app.post("/api/cedula/check/start")
    def cedula_check_start():
        data = request.get_json(silent=True) or {}
        room_id = int(data.get("room_id", 0))
        if room_id <= 0:
            return jsonify(error="room_id requerido"), 400

        chk = CedulaCheck(room_id=room_id, status="pending")
        db.session.add(chk)
        db.session.commit()
        return jsonify(ok=True, check_id=chk.id)

    @app.get("/api/cedula/check/<int:check_id>")
    def cedula_check_status(check_id: int):
        chk = CedulaCheck.query.get_or_404(check_id)
        return jsonify({
            "id": chk.id,
            "room_id": chk.room_id,
            "status": chk.status,
            "created_at": chk.created_at.isoformat(),
            "updated_at": chk.updated_at.isoformat(),
            "notes": chk.notes,
            "source_doc_url": chk.source_doc_url,
            "source_doc_hash": chk.source_doc_hash,
        })

    @app.post("/api/cedula/check/<int:check_id>/attach")
    def cedula_attach_doc(check_id: int):
        chk = CedulaCheck.query.get_or_404(check_id)
        if "file" not in request.files:
            return jsonify(error="No file part"), 400
        f = request.files["file"]
        if f.filename == "":
            return jsonify(error="No selected file"), 400
        if not allowed_file(f.filename):
            return jsonify(error="Invalid extension"), 400

        filename = secure_filename(f.filename)
        save_dir = os.path.join(UPLOAD_DIR, "cedula")
        os.makedirs(save_dir, exist_ok=True)
        canon_name = f"cedula_{check_id}_{int(time.time())}_{filename}"
        canon_path = os.path.join(save_dir, canon_name)
        orig_path = os.path.join(save_dir, filename)
        f.save(orig_path)
        shutil.copyfile(orig_path, canon_path)

        canon_url = f"/uploads/{canon_name}"
        chk.source_doc_url = canon_url
        chk.source_doc_hash = file_hash(canon_path)
        db.session.commit()
        return jsonify(ok=True, check_id=chk.id, source_doc_url=canon_url, source_doc_hash=chk.source_doc_hash)

    # --------- Background demo (re-checker) ---------
    def background_rechecker(flask_app):
        with flask_app.app_context():
            while True:
                pendings = CedulaCheck.query.filter_by(status="pending").all()
                for chk in pendings:
                    # aquí iría la lógica real de verificación con CEDULA_API_URL
                    chk.status = "ok"
                    chk.updated_at = datetime.utcnow()
                    db.session.commit()
                time.sleep(300)

    threading.Thread(target=background_rechecker, args=(app,), daemon=True).start()

    return app

# =========================
# Main local
# =========================
if __name__ == "__main__":
    app = create_app()
    print(f">>> SQLALCHEMY_DATABASE_URI = {app.config['SQLALCHEMY_DATABASE_URI']}")
    # Ejecuta en 5001 para frontend Vite (5173)
    app.run(host="127.0.0.1", port=5001, debug=True)
