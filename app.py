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
# Configuración básica
# =========================

db = SQLAlchemy()

ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EDITOR_ROLES = {"admin", "spainroom"}  # cabecera X-User-Role

BASE_DIR = os.path.dirname(__file__)
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Certificado cliente (para sedes) - opcional
CLIENT_CERT = os.getenv("CEDULA_CLIENT_CERT")
CLIENT_KEY = os.getenv("CEDULA_CLIENT_KEY")
CLIENT_P12 = os.getenv("CEDULA_CLIENT_P12")
CLIENT_P12_PASS = os.getenv("CEDULA_CLIENT_P12_PASS")

# =========================
# Helpers / Utilidades
# =========================

def require_role(req, *roles):
    """Devuelve respuesta 403 si el rol no está permitido. Usa cabecera X-User-Role."""
    role = (req.headers.get("X-User-Role") or "").strip().lower()
    if role in roles:
        return None
    return jsonify(error="Forbidden: role required", required=list(roles)), 403


def compute_sha256(fp):
    sha = hashlib.sha256()
    for chunk in iter(lambda: fp.read(8192), b""):
        sha.update(chunk)
    fp.seek(0)
    return sha.hexdigest()


def is_image_mime(mime: str) -> bool:
    return mime in {"image/jpeg", "image/png"}


def image_to_pdf(image_file, out_pdf_path, header_text=None):
    """Convierte una imagen (JPEG/PNG) a PDF A4. Requiere reportlab."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.lib.units import cm
    except Exception as e:
        raise RuntimeError("Falta reportlab: pip install reportlab") from e

    image_file.seek(0)
    img = ImageReader(image_file)
    w, h = img.getSize()

    pw, ph = A4
    margin = 1.5 * cm
    box_w = pw - 2 * margin
    box_h = ph - 3 * margin
    scale = min(box_w / w, box_h / h)
    draw_w, draw_h = w * scale, h * scale
    x = (pw - draw_w) / 2
    y = (ph - draw_h) / 2 - 0.5 * cm

    c = canvas.Canvas(out_pdf_path, pagesize=A4)
    if header_text:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, ph - margin, header_text)
    c.drawImage(img, x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor="c")
    c.showPage()
    c.save()


def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def sede_get(url, params=None, timeout=30):
    """
    Ejemplo de request mTLS si hay cert/clave en entorno.
    Si no hay cert configurado, lanza excepción para que el caller deje 'pending'.
    """
    if CLIENT_CERT and CLIENT_KEY:
        return requests.get(url, params=params, cert=(CLIENT_CERT, CLIENT_KEY), timeout=timeout)
    raise RuntimeError("Cliente mTLS no configurado (falta cert/clave)")


# Normalización y validación de Ref. Catastral
CAT_REF_REGEX = re.compile(r"^[A-Za-z0-9]{20}$")

def normalize_ref_catastral(s: str) -> str:
    return (s or "").strip().replace(" ", "").upper()

def validate_check_payload(data):
    addr = (data.get("address") or data.get("direccion") or "").strip()
    refc = normalize_ref_catastral(data.get("ref_catastral") or "")
    if not addr and not refc:
        return "Debes indicar dirección o referencia catastral."
    if refc and not CAT_REF_REGEX.match(refc):
        return "Referencia catastral inválida (debe tener 20 caracteres alfanuméricos, sin espacios)."
    return None


# =========================
# Modelos
# =========================

class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)

    # Datos básicos
    title = db.Column(db.String(200))
    price_eur = db.Column(db.Integer)
    city = db.Column(db.String(120))
    images = db.Column(db.String(1024))  # CSV "img1.jpg,img2.jpg"
    size_m2 = db.Column(db.Integer)
    features = db.Column(db.String(1024))
    availableFrom = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Cédula / LPO / 2ª ocupación
    cedula_status = db.Column(db.String(50))            # pending | submitted | verified | rejected
    cedula_ref = db.Column(db.String(120))
    cedula_expiry = db.Column(db.Date)
    cedula_locked = db.Column(db.Boolean, default=False)
    cedula_verification = db.Column(db.String(50))      # auto | manual
    cedula_doc_url = db.Column(db.String(500))          # canónica PDF
    cedula_doc_hash = db.Column(db.String(128))
    cedula_issuer = db.Column(db.String(120))
    cedula_issue_date = db.Column(db.Date)
    cedula_last_check = db.Column(db.Date)
    cedula_reason = db.Column(db.String(500))

    def _images_list(self):
        if not self.images:
            return []
        return [s.strip() for s in self.images.split(",") if s.strip()]

    def cedula_dict(self):
        return {
            "status": self.cedula_status or "pending",
            "ref": self.cedula_ref,
            "expiry": self.cedula_expiry.isoformat() if self.cedula_expiry else None,
            "locked": bool(self.cedula_locked),
            "verification": self.cedula_verification,
            "doc_url": self.cedula_doc_url,
            "doc_hash": self.cedula_doc_hash,
            "issuer": self.cedula_issuer,
            "issue_date": self.cedula_issue_date.isoformat() if self.cedula_issue_date else None,
            "last_check": self.cedula_last_check.isoformat() if self.cedula_last_check else None,
            "reason": self.cedula_reason,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "price_eur": self.price_eur,
            "city": self.city,
            "images": self._images_list(),
            "size_m2": self.size_m2,
            "features": self.features,
            "availableFrom": self.availableFrom.isoformat() if self.availableFrom else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "cedula": self.cedula_dict(),
        }


class Lead(db.Model):
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    city = db.Column(db.String(120))
    address = db.Column(db.String(240))
    message = db.Column(db.Text)
    doc_url = db.Column(db.String(500))
    doc_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CedulaCheck(db.Model):
    __tablename__ = "cedula_checks"
    id = db.Column(db.Integer, primary_key=True)
    # entrada del usuario
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    address = db.Column(db.String(240))
    ref_catastral = db.Column(db.String(30))
    city = db.Column(db.String(120))
    comunidad = db.Column(db.String(120))
    # estado del proceso
    status = db.Column(db.String(30), default="pending")  # pending | resolved
    # resultado
    has_cedula = db.Column(db.Boolean)
    issue_date = db.Column(db.Date)
    expiry = db.Column(db.Date)
    notes = db.Column(db.String(500))
    # documento obtenido por SpainRoom (opcional)
    source_doc_url = db.Column(db.String(500))
    source_doc_hash = db.Column(db.String(128))
    matched = db.Column(db.Boolean)  # cotejo dirección/RC con documento
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime)

# =========================
# Seed de pruebas (opcional)
# =========================

def _maybe_seed():
    """Crea 3 rooms demo si la tabla está vacía (solo para pruebas locales)."""
    if Room.query.count() > 0:
        return
    demo = [
        Room(
            title="Habitación 1 – Centro, luminosa",
            price_eur=420,
            city="Madrid",
            images="casa-diseno.jpg,room1.jpg",
            size_m2=12,
            features="Armario, Escritorio, WiFi, Llave propia",
            availableFrom=date.today(),
            cedula_status="verified",
            cedula_verification="auto",
            cedula_doc_url=None,
        ),
        Room(
            title="Habitación 2 – Barrio Salamanca",
            price_eur=480,
            city="Madrid",
            images="casa-diseno.jpg,room2.jpg",
            size_m2=14,
            features="Balcón, Smart TV, Llave propia",
            availableFrom=date.today(),
            cedula_status="pending",
        ),
        Room(
            title="Habitación 3 – Sol, reformada",
            price_eur=450,
            city="Madrid",
            images="casa-diseno.jpg,room3.jpg",
            size_m2=11,
            features="Cama 135x200, Escritorio, WiFi",
            availableFrom=date.today(),
            cedula_status="pending",
        ),
    ]
    db.session.add_all(demo)
    db.session.commit()

# =========================
# Resolución automática de CedulaCheck
# =========================

def resolve_cedula_check_automatically(check: CedulaCheck):
    """
    1) Normaliza RC o dirección.
    2) Si RC tiene formato inválido -> resolved/false.
    3) Heurística por CCAA: Cataluña queda pending (requiere buscador autonómico).
    4) Resto: dejamos pending para trámite SpainRoom (sede/ayto).
    """
    rc = normalize_ref_catastral(check.ref_catastral or "")
    if rc and not CAT_REF_REGEX.match(rc):
        check.status = "resolved"
        check.has_cedula = False
        check.notes = "RC inválida (formato)."
        check.resolved_at = datetime.utcnow()
        return

    # Placeholder: aquí integraríamos mTLS o scraping según CCAA
    comunidad = (check.comunidad or "").lower()
    if comunidad.startswith("catal"):
        check.status = "pending"
        check.notes = "Cataluña: pendiente consulta en cercador autonómico."
        return

    # Por defecto: pendiente; SpainRoom iniciará trámite automático con certificado
    check.status = "pending"
    check.notes = "Pendiente obtención en sede/ayto por SpainRoom."

# =========================
# App Factory
# =========================

def create_app() -> Flask:
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)

    # DB URI: por defecto SQLite en instance/app.db
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

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _maybe_seed()

    # --------- Rutas Salud ---------
    @app.get("/health")
    def health():
        return jsonify(ok=True, service="SpainRoom backend")

    @app.get("/health/db")
    def health_db():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify(ok=True)
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 500

    # --------- Servir uploads (dev) ---------
    @app.get("/uploads/<path:fname>")
    def get_upload(fname):
        return send_from_directory(UPLOAD_DIR, fname, as_attachment=False)

    # --------- API Rooms ---------
    @app.get("/api/rooms")
    def list_rooms():
        rooms = Room.query.order_by(Room.id.asc()).all()
        return jsonify([room.to_dict() for room in rooms])

    @app.get("/api/rooms/<int:room_id>")
    def get_room(room_id: int):
        room = Room.query.get_or_404(room_id)
        return jsonify(room.to_dict())

    # --------- Cedula: estado / descargar ---------
    @app.get("/api/rooms/<int:room_id>/cedula")
    def get_cedula(room_id: int):
        room = Room.query.get_or_404(room_id)
        return jsonify(room.cedula_dict())

    @app.get("/api/rooms/<int:room_id>/cedula/download")
    def download_cedula(room_id: int):
        room = Room.query.get_or_404(room_id)
        if not room.cedula_doc_url or not room.cedula_doc_url.startswith("/uploads/"):
            return jsonify(error="Sin documento canónico"), 404
        fname = room.cedula_doc_url.split("/uploads/")[-1]
        return send_from_directory(UPLOAD_DIR, fname, as_attachment=True)

    # --------- Cedula: subir (canónica PDF + original) ---------
    @app.post("/api/rooms/<int:room_id>/cedula/upload")
    def upload_cedula(room_id: int):
        unauthorized = require_role(request, *ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify(error="Falta archivo 'file'"), 400

        # Tamaño
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify(error="Archivo demasiado grande (máx 5MB)"), 413

        # MIME
        mime = file.mimetype or ""
        if mime not in ALLOWED_MIME:
            return jsonify(error="Formato no permitido (PDF/JPG/PNG)"), 415

        # Hash
        doc_hash = compute_sha256(file.stream)

        room = Room.query.get_or_404(room_id)

        ts = int(datetime.utcnow().timestamp())
        base_name = f"ROOM-{room_id}_{ts}"
        orig_ext = ".pdf" if mime == "application/pdf" else (".jpg" if mime == "image/jpeg" else ".png")
        orig_name = secure_filename(base_name + "_orig" + orig_ext)
        orig_path = os.path.join(UPLOAD_DIR, orig_name)

        # Guardar original
        file.stream.seek(0)
        file.save(orig_path)
        orig_url = f"/uploads/{orig_name}"

        # Canónica PDF
        canon_name = secure_filename(base_name + "_canon.pdf")
        canon_path = os.path.join(UPLOAD_DIR, canon_name)

        try:
            if is_image_mime(mime):
                short_hash = doc_hash[:10]
                header = f"SpainRoom · Room #{room_id} · {room.title or ''} · SHA256:{short_hash}"
                with open(orig_path, "rb") as imgf:
                    image_to_pdf(imgf, canon_path, header_text=header)
            else:
                shutil.copyfile(orig_path, canon_path)
        except Exception:
            shutil.copyfile(orig_path, canon_path)

        canon_url = f"/uploads/{canon_name}"

        # Persistimos en DB (apuntamos a la canónica PDF)
        room.cedula_doc_url = canon_url
        room.cedula_doc_hash = doc_hash
        room.cedula_status = "submitted"
        room.cedula_last_check = date.today()
        room.cedula_reason = None
        db.session.commit()

        return jsonify(ok=True,
                       room_id=room.id,
                       doc_url=canon_url,
                       doc_url_original=orig_url,
                       doc_hash=doc_hash)

    # --------- Cedula: verificar ---------
    @app.post("/api/rooms/<int:room_id>/cedula/verify")
    def verify_cedula(room_id: int):
        unauthorized = require_role(request, *ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        room = Room.query.get_or_404(room_id)
        if not room.cedula_doc_url:
            return jsonify(error="No hay documento cargado"), 400

        data = request.get_json(silent=True) or {}
        status = (data.get("status") or "verified").strip()  # verified | rejected | pending
        if status not in {"verified", "rejected", "pending"}:
            status = "verified"

        room.cedula_status = status
        room.cedula_verification = data.get("verification") or ("manual" if status == "verified" else None)
        room.cedula_reason = data.get("reason")
        room.cedula_last_check = date.today()

        issue = data.get("issue_date")
        expiry = data.get("expiry")
        room.cedula_issue_date = _parse_iso_date(issue) if issue else room.cedula_issue_date
        room.cedula_expiry = _parse_iso_date(expiry) if expiry else room.cedula_expiry

        db.session.commit()
        return jsonify(ok=True, room_id=room.id, status=room.cedula_status, last_check=room.cedula_last_check.isoformat())

    # --------- Owners: lead (con/ sin adjunto) ---------
    @app.post("/api/owners/lead")
    def create_owner_lead():
        doc_url = None
        doc_hash = None

        if request.content_type and "multipart/form-data" in request.content_type:
            form = request.form
            file = request.files.get("file")
            full_name = (form.get("nombre") or form.get("full_name") or "").strip()
            email = (form.get("email") or "").strip()
            phone = (form.get("telefono") or form.get("phone") or "").strip()
            city = (form.get("ciudad") or form.get("city") or "").strip()
            address = (form.get("direccion") or form.get("address") or "").strip()
            message = (form.get("mensaje") or form.get("message") or "").strip()
        else:
            data = request.get_json(silent=True) or {}
            file = None
            full_name = (data.get("nombre") or data.get("full_name") or "").strip()
            email = (data.get("email") or "").strip()
            phone = (data.get("telefono") or data.get("phone") or "").strip()
            city = (data.get("ciudad") or data.get("city") or "").strip()
            address = (data.get("direccion") or data.get("address") or "").strip()
            message = (data.get("mensaje") or data.get("message") or "").strip()

        if not full_name or not email:
            return jsonify(error="Nombre completo y email son obligatorios"), 400

        # Adjuntar cédula opcional
        if file and file.filename:
            # Tamaño
            file.stream.seek(0, os.SEEK_END)
            size = file.stream.tell()
            file.stream.seek(0)
            if size > MAX_FILE_SIZE:
                return jsonify(error="Archivo demasiado grande (máx 5MB)"), 413

            # MIME
            mime = file.mimetype or ""
            if mime not in ALLOWED_MIME:
                return jsonify(error="Formato no permitido (PDF/JPG/PNG)"), 415

            doc_hash = compute_sha256(file.stream)
            ts = int(datetime.utcnow().timestamp())
            base_name = f"LEAD-{ts}"
            orig_ext = ".pdf" if mime == "application/pdf" else (".jpg" if mime == "image/jpeg" else ".png")
            orig_name = secure_filename(base_name + "_orig" + orig_ext)
            orig_path = os.path.join(UPLOAD_DIR, orig_name)

            # Guardar original
            file.stream.seek(0)
            file.save(orig_path)
            # Canónica PDF
            canon_name = secure_filename(base_name + "_canon.pdf")
            canon_path = os.path.join(UPLOAD_DIR, canon_name)
            try:
                if is_image_mime(mime):
                    short_hash = doc_hash[:10]
                    header = f"SpainRoom · Lead · {full_name} · SHA256:{short_hash}"
                    with open(orig_path, "rb") as imgf:
                        image_to_pdf(imgf, canon_path, header_text=header)
                else:
                    shutil.copyfile(orig_path, canon_path)
                doc_url = f"/uploads/{canon_name}"
            except Exception:
                # fallback: original
                doc_url = f"/uploads/{orig_name}"

        # Guardar lead
        lead = Lead(
            full_name=full_name,
            email=email,
            phone=phone,
            city=city,
            address=address,
            message=message,
            doc_url=doc_url,
            doc_hash=doc_hash,
        )
        db.session.add(lead)
        db.session.commit()

        # TODO: enviar emails (propietario / SpainRoom) vía SMTP/SendGrid
        return jsonify(ok=True, lead_id=lead.id, doc_url=doc_url, doc_hash=doc_hash)

    # --------- Verificación de cédula: crear / consultar / resolver / adjuntar doc ---------
    @app.post("/api/cedula/check")
    def cedula_check_create():
        data = request.get_json(silent=True) or {}
        err = validate_check_payload(data)
        if err:
            return jsonify(error=err), 400

        check = CedulaCheck(
            full_name=(data.get("full_name") or data.get("nombre") or "").strip() or None,
            email=(data.get("email") or "").strip() or None,
            address=(data.get("address") or data.get("direccion") or "").strip() or None,
            ref_catastral=normalize_ref_catastral(data.get("ref_catastral") or ""),
            city=(data.get("city") or data.get("ciudad") or "").strip() or None,
            comunidad=(data.get("comunidad") or data.get("comunidad_autonoma") or "").strip() or None,
            status="pending",
        )
        db.session.add(check)
        db.session.commit()

        # Intento de resolución automática inicial
        resolve_cedula_check_automatically(check)
        db.session.commit()

        return jsonify(ok=True, check_id=check.id, status=check.status)

    @app.get("/api/cedula/check/<int:check_id>")
    def cedula_check_status(check_id: int):
        check = CedulaCheck.query.get_or_404(check_id)
        return jsonify({
            "ok": True,
            "check_id": check.id,
            "status": check.status,
            "input": {
                "full_name": check.full_name,
                "email": check.email,
                "address": check.address,
                "ref_catastral": check.ref_catastral,
                "city": check.city,
                "comunidad": check.comunidad,
            },
            "result": {
                "has_cedula": check.has_cedula,
                "issue_date": check.issue_date.isoformat() if check.issue_date else None,
                "expiry": check.expiry.isoformat() if check.expiry else None,
                "notes": check.notes,
                "matched": check.matched,
                "source_doc_url": check.source_doc_url,
                "source_doc_hash": check.source_doc_hash,
            }
        })

    @app.post("/api/cedula/check/<int:check_id>/resolve")
    def cedula_check_resolve(check_id: int):
        unauthorized = require_role(request, *ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        check = CedulaCheck.query.get_or_404(check_id)
        data = request.get_json(silent=True) or {}
        has = data.get("has_cedula")
        if has not in (True, False):
            return jsonify(error="has_cedula debe ser true o false"), 400

        check.has_cedula = bool(has)
        check.status = "resolved"
        check.issue_date = _parse_iso_date(data.get("issue_date"))
        check.expiry = _parse_iso_date(data.get("expiry"))
        check.notes = (data.get("notes") or "").strip() or None
        check.matched = data.get("matched") if isinstance(data.get("matched"), bool) else check.matched
        check.resolved_at = datetime.utcnow()

        db.session.commit()
        return jsonify(ok=True, check_id=check.id, status=check.status)

    @app.post("/api/cedula/check/<int:check_id>/attach-doc")
    def cedula_check_attach_doc(check_id: int):
        """SpainRoom adjunta documento oficial obtenido (PDF/JPG/PNG). Convierte a PDF y guarda hash."""
        unauthorized = require_role(request, *ALLOWED_EDITOR_ROLES)
        if unauthorized:
            return unauthorized

        chk = CedulaCheck.query.get_or_404(check_id)
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify(error="Falta archivo 'file'"), 400

        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify(error="Archivo demasiado grande (máx 5MB)"), 413

        mime = file.mimetype or ""
        if mime not in ALLOWED_MIME:
            return jsonify(error="Formato no permitido (PDF/JPG/PNG)"), 415

        doc_hash = compute_sha256(file.stream)
        ts = int(datetime.utcnow().timestamp())
        base_name = f"CHK-{chk.id}_{ts}"
        orig_ext = ".pdf" if mime == "application/pdf" else (".jpg" if mime == "image/jpeg" else ".png")
        orig_name = secure_filename(base_name + "_orig" + orig_ext)
        orig_path = os.path.join(UPLOAD_DIR, orig_name)

        # Guardar original
        file.stream.seek(0)
        file.save(orig_path)

        # Canónica PDF
        canon_name = secure_filename(base_name + "_canon.pdf")
        canon_path = os.path.join(UPLOAD_DIR, canon_name)
        try:
            if is_image_mime(mime):
                short_hash = doc_hash[:10]
                header = f"SpainRoom · CedulaCheck #{chk.id} · SHA256:{short_hash}"
                with open(orig_path, "rb") as imgf:
                    image_to_pdf(imgf, canon_path, header_text=header)
            else:
                shutil.copyfile(orig_path, canon_path)
        except Exception:
            shutil.copyfile(orig_path, canon_path)

        canon_url = f"/uploads/{canon_name}"
        chk.source_doc_url = canon_url
        chk.source_doc_hash = doc_hash
        # (opcional) marcar matched si se coteja externamente
        db.session.commit()

        return jsonify(ok=True, check_id=chk.id, source_doc_url=canon_url, source_doc_hash=doc_hash)

    # --------- Background re-checker (cada 5 minutos) ---------
    def background_rechecker(flask_app):
        with flask_app.app_context():
            while True:
                pendings = CedulaCheck.query.filter_by(status="pending").all()
                for chk in pendings:
                    try:
                        resolve_cedula_check_automatically(chk)
                    except Exception as e:
                        # anotar fallo, pero sin romper el loop
                        chk.notes = (chk.notes or "")[:400]
                        chk.notes = (chk.notes + f" | Reintento fallido: {e}")[:500]
                db.session.commit()
                time.sleep(300)  # 5 min

    threading.Thread(target=background_rechecker, args=(app,), daemon=True).start()

    return app

# =========================
# Main
# =========================

if __name__ == "__main__":
    app = create_app()
    print(f">>> SQLALCHEMY_DATABASE_URI = {app.config['SQLALCHEMY_DATABASE_URI']}")
    # Ejecuta en 5001 para frontend Vite (5173)
    app.run(host="127.0.0.1", port=5001, debug=True)
