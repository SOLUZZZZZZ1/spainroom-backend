# codigo_flask.py — Backend-1 (Stripe + Health + CORS + rutas dobles)
# Nora · 2025-10-11
import os
from urllib.parse import urljoin
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# ====== CORS ======
# Permite lista desde env FRONTEND_ORIGINS o usa defaults seguros (localhost + Vercel)
DEFAULT_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "https://spainroom.vercel.app",
]
ENV_ORIGINS = [o.strip() for o in (os.getenv("FRONTEND_ORIGINS") or "").replace(",", " ").split() if o.strip()]
ALLOWED_ORIGINS = ENV_ORIGINS if ENV_ORIGINS else DEFAULT_ORIGINS

CORS(
    app,
    resources={r"/*": {"origins": ALLOWED_ORIGINS}},
    supports_credentials=False,
)

def abs_url(origin: str, path_or_url: str) -> str:
    """Si nos pasan un path relativo, fabrico URL absoluta con el Origin."""
    if not path_or_url:
        return origin or ""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    base = (origin or "").rstrip("/") + "/"
    return urljoin(base, path_or_url.lstrip("/"))

# ====== Health ======
@app.get("/health")
@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

# ====== Pagos (Stripe) — alias dobles ======
@app.route("/create-checkout-session", methods=["OPTIONS", "POST", "GET"])
@app.route("/api/payments/create-checkout-session", methods=["OPTIONS", "POST", "GET"])
def create_checkout_session():
    # Preflight CORS
    if request.method == "OPTIONS":
        return ("", 204)

    # GET informativo (evita 405 si se visita en navegador)
    if request.method == "GET":
        return jsonify(ok=True, info="Use POST con JSON: {amount(EUR), success_path|success_url, cancel_path|cancel_url}"), 200

    data = request.get_json(silent=True) or {}

    # Origen del front (para construir URLs absolutas si mandan paths)
    origin = request.headers.get("Origin") or os.getenv("FRONTEND_ORIGIN", ALLOWED_ORIGINS[0])

    # Cantidad en EUR (acepta amount o amount_eur)
    amount_eur = data.get("amount", data.get("amount_eur"))
    try:
        amount_eur = int(amount_eur or 0)
    except Exception:
        amount_eur = 0

    currency    = (data.get("currency") or "eur").lower()
    success_url = data.get("success_url") or abs_url(origin, data.get("success_path") or "/?reserva=ok")
    cancel_url  = data.get("cancel_url")  or abs_url(origin, data.get("cancel_path")  or "/?reserva=error")

    stripe_key  = (os.getenv("STRIPE_SECRET_KEY") or "").strip()

    # Sin clave → modo demo (redirige al success)
    if not stripe_key:
        return jsonify(ok=True, demo=True, url=success_url)

    # Stripe real
    try:
        import stripe
        stripe.api_key = stripe_key
        amount_cents = amount_eur * 100
        if amount_cents <= 0:
            return jsonify(ok=False, error="amount inválido (EUR entero > 0)"), 400

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": data.get("concept") or "Depósito SpainRoom"},
                    "unit_amount": amount_cents
                },
                "quantity": int(data.get("quantity") or 1)
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=data.get("customer_email") or None,
            metadata=data.get("metadata") or {},
        )
        return jsonify(ok=True, url=session.url)
    except Exception as e:
        # Fallback demo para no bloquear reservas si Stripe falla
        return jsonify(ok=True, demo=True, url=success_url, error=str(e))

# ====== Factory para Gunicorn ======
def create_app():
    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
