# app.py — backend-1 (Stripe real): pagos + webhook + CORS + health + VOZ (answer_cr)
# Nora · 2025-10-13
import os, logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# Blueprints
try:
    from routes_payments import bp_pay, create_checkout_session as _ccs  # _ccs para alias directo
except Exception as e:
    bp_pay = None
    _ccs = None
    print("Aviso: routes_payments no disponible:", e)

try:
    from routes_stripe_webhook import bp_webhook  # POST /webhooks/stripe
except Exception as e:
    bp_webhook = None
    print("Aviso: routes_stripe_webhook no disponible:", e)

# === VOZ: responder Twilio con streaming a voice-cr ===
try:
    from routes_voice_answer_cr import bp_voice_answer_cr  # POST /voice/answer_cr
except Exception as e:
    bp_voice_answer_cr = None
    print("Aviso: routes_voice_answer_cr no disponible:", e)

# Lista blanca básica (puedes sobrescribir con FRONTEND_ORIGINS)
ALLOWED_ORIGINS = {
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "https://spainroom.vercel.app",
}
_extra = [o.strip() for o in (os.getenv("FRONTEND_ORIGINS") or "").replace(",", " ").split() if o.strip()]
ALLOWED_ORIGINS.update(_extra)

def create_app():
    app = Flask(__name__)
    # CORS abierto con verificación fina en after_request
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    @app.after_request
    def add_cors_headers(resp: Response):
        origin = request.headers.get("Origin", "")
        # Permite *.vercel.app, localhost y los de la lista
        allow = (
            origin
            and (
                origin in ALLOWED_ORIGINS
                or origin.endswith(".vercel.app")
                or origin.startswith("http://localhost:")
                or origin.startswith("http://127.0.0.1:")
            )
        )
        if allow:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Stripe-Signature"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        return resp

    _init_logging(app)

    # === Pagos (Stripe) ===
    if bp_pay:
        app.register_blueprint(bp_pay, url_prefix="/api/payments")
        if _ccs:
            @app.route("/create-checkout-session", methods=["OPTIONS", "POST", "GET"])
            def create_checkout_session_alias():
                return _ccs()
        app.logger.info("Blueprint pagos registrado.")
    else:
        app.logger.warning("Blueprint pagos NO disponible.")

    # === Webhook Stripe ===
    if bp_webhook:
        app.register_blueprint(bp_webhook)  # POST /webhooks/stripe
        app.logger.info("Webhook de Stripe registrado en /webhooks/stripe.")
    else:
        app.logger.warning("Webhook de Stripe NO disponible.")

    # === VOZ: Twilio answer → voice-cr stream ===
    if bp_voice_answer_cr:
        app.register_blueprint(bp_voice_answer_cr)  # /voice/answer_cr
        app.logger.info("Blueprint voz (answer_cr) registrado.")
    else:
        app.logger.warning("Blueprint voz (answer_cr) NO disponible.")

    # === Health ===
    @app.get("/health")
    @app.get("/healthz")
    def health():
        return jsonify(ok=True, service="spainroom-backend-1")

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
