# app.py — backend-1 (Stripe real): pagos + CORS + health
import os, logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from flask_cors import CORS
from routes_payments import bp_pay

ALLOWED_ORIGINS = {
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "https://frontend-pagos.vercel.app",
}

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    @app.after_request
    def add_cors_headers(resp):
        origin = request.headers.get("Origin", "")
        if origin and (origin in ALLOWED_ORIGINS or origin.endswith(".vercel.app")):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Stripe-Signature"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        return resp

    _init_logging(app)
    app.register_blueprint(bp_pay, url_prefix="/api/payments")

    @app.get("/health")
    def health(): return jsonify(ok=True, service="spainroom-backend-1")

    return app

def _init_logging(app: Flask):
    app.logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh = logging.StreamHandler(); sh.setFormatter(fmt)
    app.logger.addHandler(sh)
    try:
        fh = RotatingFileHandler("backend.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        app.logger.addHandler(fh)
    except Exception:
        pass

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
