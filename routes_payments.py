# routes_payments.py — Stripe real + demo (fallback)
import os
from flask import Blueprint, request, jsonify
import stripe

bp_pay = Blueprint("payments", __name__)

@bp_pay.route("/create-checkout-session", methods=["POST", "OPTIONS"])
def create_checkout_session():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    amount_eur = int(data.get("amount") or 150)
    currency = (data.get("currency") or "eur").lower()
    success_path = data.get("success_path") or "/?reserva=ok"
    cancel_path = data.get("cancel_path") or "/?reserva=error"

    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    base_front = request.headers.get("Origin") or "https://frontend-pagos.vercel.app"

    if not stripe_key:
        demo_url = f"{base_front}{success_path}"
        return jsonify(ok=True, demo=True, url=demo_url)

    try:
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
            success_url=f"{base_front}{success_path}",
            cancel_url=f"{base_front}{cancel_path}",
            customer_email=data.get("customer_email") or None,
            metadata=(data.get("metadata") or {}),
        )
        return jsonify(ok=True, url=session.url)
    except Exception as e:
        return jsonify(ok=True, demo=True, url=f"{base_front}{success_path}", error=str(e))
