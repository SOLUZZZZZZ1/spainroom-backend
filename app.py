import os, io, uuid, base64, json, sqlite3
from contextlib import closing
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageOps
from urllib.parse import urlparse

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
DB_PATH = os.environ.get("DB_PATH", "rooms.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024
TARGET_RATIO = 4 / 3
SIZES = [1600, 1200, 800, 400]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app, resources={r"/api/*": {"origins": "*"}})

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(db()) as conn, conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
          id TEXT PRIMARY KEY,
          title TEXT,
          price_eur INTEGER,
          city TEXT,
          size_m2 INTEGER,
          features TEXT,
          availableFrom TEXT,
          images TEXT,
          created_at TEXT,
          updated_at TEXT
        )
        """)
init_db()

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def center_crop_to_ratio(img: Image.Image, ratio: float = TARGET_RATIO) -> Image.Image:
    w, h = img.size
    current = w / h
    if abs(current - ratio) < 1e-3:
        return img
    if current > ratio:
        new_w = int(h * ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))

def to_webp_bytes(img: Image.Image, quality: int = 82) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()

def to_jpg_bytes(img: Image.Image, quality: int = 84) -> bytes:
    buf = io.BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()

def tiny_placeholder(img: Image.Image, width: int = 20) -> str:
    ph = ImageOps.fit(img, (width, int(width / TARGET_RATIO)), method=Image.LANCZOS)
    b = io.BytesIO()
    ph.save(b, format="JPEG", quality=30)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode("utf-8")

def process_image_file(file_storage, room_id: str) -> dict:
    if not file_storage.filename or not allowed_file(file_storage.filename):
        raise ValueError("invalid file type")
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img)
    img = center_crop_to_ratio(img)

    base_name = f"{room_id}-{uuid.uuid4().hex}"
    placeholder = tiny_placeholder(img)

    out = {"url": None, "placeholder": placeholder, "srcset": {}}
    for w in SIZES:
        resized = ImageOps.contain(img, (w, int(w / TARGET_RATIO)), method=Image.LANCZOS)
        webp_name = f"{base_name}-{w}.webp"
        with open(os.path.join(UPLOAD_DIR, webp_name), "wb") as fh:
            fh.write(to_webp_bytes(resized))
        jpg_name = f"{base_name}-{w}.jpg"
        with open(os.path.join(UPLOAD_DIR, jpg_name), "wb") as fh:
            fh.write(to_jpg_bytes(resized))
        out["srcset"][str(w)] = f"/uploads/{webp_name}"
        if out["url"] is None:
            out["url"] = f"/uploads/{webp_name}"
    return out

@app.get("/uploads/<path:filename>")
def uploads(filename: str):
    return send_from_directory(UPLOAD_DIR, filename, conditional=True)

@app.post("/api/upload-room-photo")
def upload_room_photo():
    if "file" not in request.files:
        return jsonify({"error": "file required"}), 400
    room_id = request.form.get("room_id") or str(uuid.uuid4())
    try:
        img_obj = process_image_file(request.files["file"], room_id)
        return jsonify(img_obj), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

def _is_under_uploads(path: str) -> bool:
    abs_up = os.path.abspath(UPLOAD_DIR)
    abs_p = os.path.abspath(path)
    return abs_p.startswith(abs_up + os.sep)

def delete_image_variants(img_obj: dict):
    urls = set()
    if img_obj.get("url"):
        urls.add(img_obj["url"])
    for _k, u in (img_obj.get("srcset") or {}).items():
        urls.add(u)
    for u in urls:
        filename = urlparse(u).path.split("/uploads/", 1)[1]
        webp_path = os.path.join(UPLOAD_DIR, filename)
        jpg_path = webp_path.rsplit(".", 1)[0] + ".jpg"
        for path in (webp_path, jpg_path):
            if _is_under_uploads(path) and os.path.exists(path):
                os.remove(path)

# CRUD Rooms (GET, POST, PUT, DELETE) ...
# (el código sigue igual al que te pasé, completo)
