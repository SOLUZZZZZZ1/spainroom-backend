# codigo_flask.py — SpainRoom pagos (Stripe real + demo + CORS) + health
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
    "https://frontend-pagos.vercel.app",  # tu front en Vercel
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
def _abs_url(origin: str, path: str) -> str:
    if not path:
        return origin or ""
    if path.startswith(("http://", "https://")):
        return path
    base = (origin or "").rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))

# ======================
# Health
# ======================
@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

# ======================
# Pagos (Stripe)
#   - Compatibilidad con dos rutas:
#       1) POST /create-checkout-session          (Flask simple)
#       2) POST /api/payments/create-checkout-session (para front antiguo)
#   - GET: mensaje informativo (evita "Method Not Allowed")
# ======================
def _create_checkout_session_impl(data, origin):
    amount_eur   = int(data.get("amount") or data.get("amount_eur") or 150)
    currency     = (data.get("currency") or "eur").lower()
    success_path = data.get("success_path") or "/?reserva=ok"
    cancel_path  = data.get("cancel_path")  or "/?reserva=error"
    success_url  = _abs_url(origin, success_path)
    cancel_url   = _abs_url(origin, cancel_path)
    stripe_key   = (os.getenv("STRIPE_SECRET_KEY") or "").strip()

    if not stripe_key:
        # Modo demo (sin clave Stripe)
        return jsonify(ok=True, demo=True, url=success_url)

    try:
        import stripe
        stripe.api_key = stripe_key
        amount_cents = amount_eur * 100
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
            metadata=data.get("metadata") or {},
        )
        return jsonify(ok=True, url=session.url)
    except Exception as e:
        return jsonify(ok=True, demo=True, url=success_url, error=str(e))


# === Ruta 1: /create-checkout-session ===
@app.route("/create-checkout-session", methods=["POST", "OPTIONS", "GET"])
def create_checkout_session():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return jsonify(ok=True, info="Use POST con JSON: {amount, success_path, cancel_path}"), 200
    data = request.get_json(silent=True) or {}
    origin = request.headers.get("Origin") or os.getenv("FRONTEND_ORIGIN", "http://localhost:5176")
    return _create_checkout_session_impl(data, origin)

# === Ruta 2: /api/payments/create-checkout-session ===
@app.route("/api/payments/create-checkout-session", methods=["POST", "OPTIONS", "GET"])
def create_checkout_session_api():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return jsonify(ok=True, info="Use POST con JSON: {amount, success_path, cancel_path}"), 200
    data = request.get_json(silent=True) or {}
    origin = request.headers.get("Origin") or os.getenv("FRONTEND_ORIGIN", "http://localhost:5176")
    return _create_checkout_session_impl(data, origin)

# ======================
# Run / Factory
# ======================
def create_app():
    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
