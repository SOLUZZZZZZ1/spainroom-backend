# app.py — App unificada: pagos + proxy habitaciones + CORS + healthz
import os
from flask import Flask, jsonify
from flask_cors import CORS

# Blueprints
from payments import bp_pay          # tu blueprint de pagos (/api/payments/...)  (ajustado para no romper sin STRIPE_SECRET_KEY)
from rooms_proxy import bp_rooms     # proxy de /api/rooms/* y /instance/* hacia el upstream

ALLOWED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    # añade aquí tu dominio público del frontend cuando lo tengas
]

def create_app():
    app = Flask(__name__)

    # CORS: autoriza API rooms y pagos; instance solo GET
    CORS(app, resources={
        r"/api/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"],
        },
        r"/instance/*": {
            "origins": "*",
            "methods": ["GET", "OPTIONS"],
        },
    })

    # Health
    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True), 200

    # Blueprints
    app.register_blueprint(bp_pay)    # /api/payments/create-checkout-session (Stripe)
    app.register_blueprint(bp_rooms)  # /api/rooms/* y /instance/* (proxy)

    return app

# Soporte para ejecución local directa (Render usa gunicorn con create_app())
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
