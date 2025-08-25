import os
from datetime import datetime, date
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import text as _text
from config import Config

db = SQLAlchemy()

# ---------- MODELOS ----------
class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)

    # Campos usados por el frontend / traza
    price_eur = db.Column(db.Integer)
    city = db.Column(db.String(120))
    images = db.Column(db.Text)                       # guarda "img1.jpg,img2.jpg"
    size_m2 = db.Column(db.Integer)
    features = db.Column(db.Text)

    # La traza mostraba "availableFrom" (respetamos el nombre tal cual)
    availableFrom = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Bloque cédula
    cedula_status = db.Column(db.String(50))          # e.g. "pending/verified/rejected"
    cedula_ref = db.Column(db.String(120))
    cedula_expiry = db.Column(db.Date)
    cedula_locked = db.Column(db.Boolean, default=False)
    cedula_verification = db.Column(db.String(120))   # e.g. "auto/manual"
    cedula_doc_url = db.Column(db.String(500))
    cedula_doc_hash = db.Column(db.String(120))
    cedula_issuer = db.Column(db.String(120))
    cedula_issue_date = db.Column(db.Date)
    cedula_last_check = db.Column(db.Date)
    cedula_reason = db.Column(db.String(255))


# --------- helper: serializar Room en JSON ----------
def room_to_json(r: Room):
    return {
        "id": r.id,
        "title": r.title,
        "price_eur": r.price_eur or 0,
        "city": r.city,
        "images": [] if not r.images else r.images.split(","),  # texto -> lista
        "size_m2": r.size_m2,
        "features": r.features,
        "availableFrom": r.availableFrom.isoformat() if r.availableFrom else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "cedula": {
            "status": r.cedula_status,
            "ref": r.cedula_ref,
            "expiry": r.cedula_expiry.isoformat() if r.cedula_expiry else None,
            "locked": bool(r.cedula_locked),
            "verification": r.cedula_verification,
            "doc_url": r.cedula_doc_url,
            "doc_hash": r.cedula_doc_hash,
            "issuer": r.cedula_issuer,
            "issue_date": r.cedula_issue_date.isoformat() if r.cedula_issue_date else None,
            "last_check": r.cedula_last_check.isoformat() if r.cedula_last_check else None,
            "reason": r.cedula_reason,
        }
    }


# --------- control de roles (solo equipo SpainRoom puede editar cédula) ---------
ALLOWED_EDITOR_ROLES = {"admin", "spainroom"}  # propietarios quedan fuera

def require_role(*roles):
    roles_lc = {r.lower() for r in roles}
    role = (request.headers.get("X-User-Role") or "").lower()
    if role not in roles_lc:
        return jsonify({"error": "No autorizado", "needed": sorted(list(roles_lc)), "got": role}), 403


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # CORS para /api/*  — Permite local y tu dominio Vercel (cámbialo por el real)
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "https://TU-FRONTEND.vercel.app"
            ]
        }
    })

    # ---- LOG de la URI y ping de DB al arrancar ----
    print(">>> SQLALCHEMY_DATABASE_URI =", app.config.get("SQLALCHEMY_DATABASE_URI"))
    with app.app_context():
        try:
            pong = db.session.execute(_text("SELECT 1")).scalar()
            app.logger.info("DB PING -> %s", pong)
        except Exception as e:
            app.logger.error("DB PING FAILED: %s", e)

    @app.get("/")
    def root():
        return jsonify(ok=True, service="SpainRoom backend")

    # ---- Health DB ----
    @app.get("/health/db")
    def health_db():
        try:
            db.session.execute(_text("SELECT 1"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}, 500

    # ---- Listado de habitaciones ----
    @app.get("/api/rooms")
    def list_rooms():
        qs = Room.query.order_by(Room.created_at.desc()).all()
        return jsonify([room_to_json(r) for r in qs])

    # ---- Detalle de habitación por ID ----
    @app.get("/api/rooms/<int:room_id>")
    def get_room(room_id: int):
        r = Room.query.get_or_404(room_id)
        return jsonify(room_to_json(r))

    # ---- Endpoints de cédula (con control de rol) ----
    @app.post("/api/rooms/<int:room_id>/cedula")
    def update_cedula(room_id: int):
        # Solo admin/spainroom pueden modificar
        unauthorized = require_role(*ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        room = Room.query.get_or_404(room_id)
        data = request.get_json(force=True, silent=True) or {}

        mapping = {
            "status": "cedula_status",
            "ref": "cedula_ref",
            "expiry": "cedula_expiry",
            "locked": "cedula_locked",
            "verification": "cedula_verification",
            "doc_url": "cedula_doc_url",
            "doc_hash": "cedula_doc_hash",
            "issuer": "cedula_issuer",
            "issue_date": "cedula_issue_date",
            "reason": "cedula_reason",
        }

        for k_req, k_model in mapping.items():
            if k_req in data:
                val = data[k_req]
                if k_model in ("cedula_expiry", "cedula_issue_date") and isinstance(val, str):
                    try:
                        val = datetime.strptime(val, "%Y-%m-%d").date()
                    except ValueError:
                        return jsonify(error=f"Formato de fecha inválido en {k_req} (YYYY-MM-DD)"), 400
                setattr(room, k_model, val)

        room.cedula_last_check = date.today()
        db.session.commit()
        return jsonify({"ok": True, "room_id": room.id})

    @app.post("/api/rooms/<int:room_id>/cedula/verify")
    def verify_cedula(room_id: int):
        # Solo admin/spainroom pueden verificar
        unauthorized = require_role(*ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        room = Room.query.get_or_404(room_id)
        if not room.cedula_doc_url:
            return jsonify({"error": "No hay documento cargado"}), 400

        room.cedula_status = "verified"
        room.cedula_verification = room.cedula_verification or "auto"
        room.cedula_last_check = date.today()
        db.session.commit()

        return jsonify({"ok": True, "doc_url": room.cedula_doc_url})

    return app


app = create_app()

if __name__ == "__main__":
    print("Starting SpainRoom backend on http://127.0.0.1:5000 ...")
    # Recuerda: define DATABASE_URL para Postgres o se usará SQLite (app.db)
    app.run(host="127.0.0.1", port=5000, debug=True)
