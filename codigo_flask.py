# codigo_flask.py — SpainRoom pagos (Stripe) + util + CORS + health
import os
from math import radians, sin, cos, sqrt, atan2
from urllib.parse import urljoin

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# ======================
# CORS
# ======================
ALLOWED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "https://frontend-pagos.vercel.app",  # ← tu front en Vercel
]

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
    r"/create-checkout-session": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
    r"/healthz": {"origins": "*"}
})

# ======================
# Utils
# ======================
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2*atan2(sqrt(a), sqrt(1-a))
    return R*c

def _abs_url(origin: str, path: str) -> str:
    if not path: return origin or ""
    if path.startswith(("http://", "https://")): return path
    base = (origin or "").rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))

# ======================
# Health
# ======================
@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

# ======================
# Geocode demo (no imprescindible)
# ======================
@app.get("/api/geocode")
def geocode():
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Falta parámetro address"}), 400
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": address, "format": "json", "limit": 1},
                         headers={"User-Agent": "SpainRoom/1.0"}, timeout=12)
        r.raise_for_status()
        results = r.json()
        if not results: return jsonify({"error": "No se pudo geocodificar"}), 404
        data = results[0]
        return jsonify({"lat": float(data["lat"]), "lng": float(data["lon"])})
    except Exception:
        return jsonify({"error": "No se pudo geocodificar"}), 500

# ======================
# Pagos (Stripe)
#   - Compatibilidad con DOS rutas:
#       1) POST /create-checkout-session     (Flask original)
#       2) POST /api/payments/create-checkout-session (compat front)
#   - GET en ambas rutas: mensaje informativo (evita "Method Not Allowed")
# ======================
def _create_checkout_session_impl(data, origin):
    amount_eur   = int(data.get("amount") or 150)
    currency     = (data.get("currency") or "eur").lower()
    success_path = data.get("success_path") or "/?reserva=ok"
    cancel_path  = data.get("cancel_path")  or "/?reserva=error"
    success_url  = _abs_url(origin, success_path)
    cancel_url   = _abs_url(origin, cancel_path)
    stripe_key   = (os.getenv("STRIPE_SECRET_KEY") or "").strip()

    if not stripe_key:
        # Demo segura (sin clave Stripe): redir
