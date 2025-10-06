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

# Orígenes permitidos (ajusta si tienes dominio público del front)
ALLOWED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    # "https://tu-frontend.com",
]

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
    r"/create-checkout-session": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
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
    if path.startswith(("http://", "https://")):
        return path
    base = (origin or "").rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))

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
    try:
        r = requests.get(
            url,
            params={"q": address, "format": "json", "limit": 1},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return jsonify({"error": "No se pudo geocodificar"}), 404
        data = results[0]
        return jsonify({"lat": float(data["lat"]), "lng": float(data["lon"])})
    except Exception:
        return jsonify({"error": "No se pudo geocodificar"}), 500

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
        {"id": 1, "titulo": "Camarero/a",      "empresa": "Bar Central",   "lat": lat + 0.010, "lng": lng + 0.010},
        {"id": 2, "titulo": "Dependiente/a",   "empresa": "Tienda Local",  "lat": lat + 0.015, "lng": lng + 0.000},
        {"id": 3, "titulo": "Administrativo/a","empresa": "Gestoría",      "lat": lat - 0.020, "lng": lng - 0.010},
        {"id": 4, "titulo": "Carpintero/a",    "empresa": "Taller Madera", "lat": lat + 0.030, "lng": lng + 0.020},
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
def create_checkout_session():
    data = request.get_json(silent=True) or {}

    # Datos del front para construir URLs absolutas
    origin       = request.headers.get("Origin") or os.getenv("FRONTEND_ORIGIN", "http://localhost:5176")
    amount_eur   = int(data.get("amount") or 150)  # depósito en €
    currency     = (data.get("currency") or "eur").lower()
    success_path = data.get("success_path") or "/?reserva=ok"
    cancel_path  = data.get("cancel_path")  or "/?reserva=error"
    success_url  = _abs_url(origin, success_path)
    cancel_url   = _abs_url(origin, cancel_path)

    stripe_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()

    # Si no hay clave Stripe → DEMO (redirige al éxito)
    if not stripe_key:
        return jsonify(ok=True, demo=True, url=success_url)

    # Stripe real
    try:
        import stripe
        stripe.api_key = stripe_key
        amount_cents = int(amount_eur * 100)

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": "Depósito de reserva SpainRoom"},
                    "unit_amount": amount_cents
                },
                "quantity": 1
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=data.get("customer_email") or None,
            metadata=(data.get("metadata") or {}),
        )
        return jsonify(ok=True, url=session.url)
    except Exception as e:
        # Fallback demo para no bloquear el flujo si Stripe falla
        return jsonify(ok=True, demo=True, url=success_url, error=str(e))

# =========================================
# Arranque (Render usa PORT)
# =========================================
if __name__ == "__main__":
  port = int(os.environ.get("PORT", "10000"))
  app.run(host="0.0.0.0", port=port)
