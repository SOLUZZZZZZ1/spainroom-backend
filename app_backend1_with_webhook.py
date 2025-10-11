# app_backend1_with_webhook.py — Backend-1 con Stripe + Webhook + Health + CORS
# Nora · 2025-10-11
import os
import logging
from urllib.parse import urljoin
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# === Blueprints locales ===
try:
    from routes_payments import bp_pay
except Exception as e:
    bp_pay = None
    print("Aviso: no se pudo importar bp_pay desde routes_payments:", e)

try:
    from routes_stripe_webhook import bp_webhook
except Exception as e:
    bp_webhook = None
    print("Aviso: no se pudo importar bp_webhook:", e)

app = Flask(__name__)

# ====== CORS ======
DEFAULT_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "https://spainroom.vercel.app",
]
ENV_ORIGINS = [o.strip() for o in (os.getenv("FRONTEND_ORIGINS") or "").replace(",", " ").split() if o.strip()]
ALLOWED_ORIGINS = ENV_ORIGINS if ENV_ORIGINS else DEFAULT_ORIGINS
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=False)

# ====== Health ======
@app.get("/health")
@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

# ====== Registro de blueprints ======
if bp_pay:
    # Exponemos ambas rutas: /create-checkout-session y /api/payments/create-checkout-session
    app.register_blueprint(bp_pay)
else:
    print("routes_payments no disponible.")

if bp_webhook:
    app.register_blueprint(bp_webhook)  # expone POST /webhooks/stripe
else:
    print("routes_stripe_webhook no disponible.")

# ====== Factory para Gunicorn ======
def create_app():
    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
