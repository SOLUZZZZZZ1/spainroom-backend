# codigo_flask.py — SpainRoom util + pagos (CORS + demo Stripe fallback)
import os
from math import radians, sin, cos, sqrt, atan2
from urllib.parse import urljoin

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# =========================================
# App & CORS
# =========================================
app = Flask(__name__)

# Orígenes permitidos para desarrollo y prod (ajusta tu dominio final de front si lo tienes)
ALLOWED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    # añade tu dominio de frontend público si lo tienes, ej.:
    # "https://spainroom-frontend.vercel.app",
]

CORS(app, resources={
    r"/api/*": {"origins": ALLOWED_ORIGINS, "methods": ["GET", "POST", "OPTIONS"]},
    r"/create-checkout-session": {"origins": ALLOWED_ORIGINS, "methods": ["POST", "OPTIONS"]},
    r"/healthz": {"origins": "*"}
})

# =========================================
# Utilidades
# =========================================
def calcular_distancia(lat1, lon1, lat2, lon2):
    """Distancia Haversine en km."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2*atan2(sqrt(a), sqrt(1-a))
    return R*c

def _abs_url(origin: str, path: str) -> str:
    """Construye URL absoluta para success/cancel si nos pasan un path relativo."""
    if not path:
        return origin or ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    # path relativo → origin/path
    return urljoin(origin.rstrip("/") + "/", path.lstrip("/"))

# =========================================
# Health
# =========================================
@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

# =========================================
# 1) Geocodificación (Nominatim)
# =========================================
@app.get("/api/geocode")
def geocode():
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Falta parámetro address"}), 400

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "SpainRoom/1.0"}
    r = requests.get(url, params={"q": address, "format": "json", "limit": 1}, headers=headers, timeout=15)

    if r.status_code != 200 or not r.json():
        return jsonify({"error": "No se pudo geocodificar"}), 500

    data = r.json()[0]
    return jsonify({"lat": float(data["lat"]), "lng": float(data["lon"])})

# =========================================
# 2) Búsqueda de empleos (mock con distancia real)
# =========================================
@app.get("/api/jobs/search")
def search_jobs():
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius_km", 2))
        keyword = (request.args.get("q") or "").lower()
    except Exception:
        return jsonify({"error": "Parámetros inválidos"}), 400

    # Base ficticia (coordenadas alrededor de lat/lng)
    ofertas = [
        {"id": 1, "titulo": "Camarero/a",     "empresa": "Bar Central",     "lat": lat + 0.010, "lng": lng + 0.010},
        {"id": 2, "titulo": "Dependiente/a",  "empresa": "Tienda Local",    "lat": lat + 0.015, "lng": lng + 0.000},
        {"id": 3, "titulo": "Administrativo/a","empresa": "Gestoría",       "lat": lat - 0.020, "lng": lng - 0.010},
        {"id": 4, "titulo": "Carpintero/a",   "empresa": "Taller Madera",   "lat": lat + 0.030, "lng": lng + 0.020},
    ]

    resultados = []
    for o in ofertas:
        dist = calcular_distancia(lat, lng, o["lat"], o["lng"])
        if dist <= radius:
            if not keyword or keyword in o["titulo"].lower():
                resultados.append({
                    "id": o["id"],
                    "titulo": o["titulo"],
                    "empresa": o["empresa"],
                    "distancia_km": round(dist, 2)
                })

    return jsonify(resultados)

# =========================================
# 3) Pagos — /create-checkout-session
#    - Si STRIPE_SECRET_KEY no está → DEMO (redirige al success)
#    - Si está → crea sesión de Stripe y devuelve URL de Checkout
# =========================================
@app.post("/create-checkout-session")
def create_checkout
