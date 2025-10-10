# app.py — backend-1 (Stripe real): pagos + CORS + health (+ proxy rooms opcional)
import os, logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from flask_cors import CORS

# === Blueprints obligatorios/opcionales ===
# Pagos (tu fichero es routes_payments.py y el blueprint se llama bp_pay)
from routes_payments import bp_pay  # expone /api/payments/create-checkout-session

# Proxy de rooms opcional (solo si lo usas en este backend)
try:
    from rooms_proxy import bp_rooms  # expone /api/rooms/* (proxy) y/o /instance/*
except Exception:
    bp_rooms = None

ALLOWED_ORIGINS = {
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    # añade aquí tu dominio de producción del front si aplica:
    # "https://tu-frontend.vercel.app",
}

def create_app():
    app = Flask(__name__)

    # ---------- CORS ----------
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    @app.after_request
    def add_cors_headers(resp):
        origin = request.headers.get("Origin", "")
        # Permite localhost y *.vercel.app automáticamente
        if origin and (origin in ALLOWED_ORIGINS or origin.endswith(".vercel.app")):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Stripe-Signature"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        return resp

    # ---------- Logging ----------
    _init_logging(app)

    # ---------- Blueprints ----------
    # Pagos (Stripe). IMPORTANTE: este backend debe tener STRIPE_SECRET_KEY en Environment.
    app.register_blueprint(bp_pay, url_prefix="/api/payments")

    # Rooms proxy (opcional): solo si quieres servir también /api/rooms/* desde este backend
    if bp_rooms:
        app.register_blueprint(bp_rooms)  # si tu bp ya define /api/rooms/* en los decoradores
        app.logger.info("rooms_proxy registrado")

    # ---------- Health ----------
    @app.get("/health")
    def health(): return jsonify(ok=True, service="spainroom-backend-1")

    @app.get("/healthz")
    def healthz(): return jsonify(ok=True)

    return app


def _init_logging(app: Flask):
    app.logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    app.logger.addHandler(sh)

    try:
        fh = RotatingFileHandler("backend.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(formatter)
        app.logger.addHandler(fh)
    except Exception:
        pass

    app.logger.info("Logging listo (backend-1).")


# Soporte local; en Render usarás gunicorn "app:create_app()"
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "10000"))
    # No usar debug en producción
    app.run(host="0.0.0.0", port=port)
