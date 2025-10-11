# routes_stripe_webhook.py — Webhook de Stripe (firma verificada + idempotencia)
# Nora · 2025-10-11
import os
import json
import hashlib
from flask import Blueprint, request, jsonify

try:
    import stripe
except Exception:
    stripe = None

bp_webhook = Blueprint("stripe_webhook", __name__)

# Memoria simple para idempotencia (reinicia al redeploy). Sustituir por BD si quieres persistencia.
_SEEN = set()

def _already_processed(event_id: str) -> bool:
    if not event_id:
        return False
    if event_id in _SEEN:
        return True
    _SEEN.add(event_id)
    return False

@bp_webhook.route("/webhooks/stripe", methods=["POST"])
def stripe_webhooks():
    # Webhooks NO usan CORS ni cookies. Responder rápido (200) salvo errores de firma/payload.
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()

    if not stripe:
        # Si no hay stripe instalado, no bloqueamos el flujo pero registramos:
        return jsonify(ok=True, skipped=True, reason="stripe module not available"), 200

    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=endpoint_secret
            )
        else:
            # Sin secreto -> NO verificado (solo para pruebas locales)
            event = json.loads(payload or "{}")
    except Exception as e:
        # Firma no válida o payload inválido
        return jsonify(ok=False, error="signature verification failed", detail=str(e)), 400

    event_id = event.get("id")
    if _already_processed(event_id):
        # Idempotencia: si ya lo vimos, devolvemos 200 sin reprocesar
        return jsonify(ok=True, idempotent=True), 200

    event_type = event.get("type")

    # === Manejo de eventos clave ===
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        # Ejemplo: marcar reserva pagada (si enviaste reservation_id en metadata)
        reservation_id = (session.get("metadata") or {}).get("reservation_id")
        customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email")
        _mark_reservation_paid(reservation_id, session.get("id"), customer_email)

    # Puedes añadir más eventos: payment_intent.succeeded, charge.refunded, etc.

    return jsonify(ok=True), 200


def _mark_reservation_paid(reservation_id: str, session_id: str, customer_email: str):
    """Placeholder: aquí iría la actualización real en tu BD.
    Sustituye por tu lógica (SQL/ORM/API) para dejar constancia del pago.
    """
    # TODO: Implementar persistencia real (ej. UPDATE reservations SET status='paid', stripe_session_id=...)
    # Por ahora solo imprime en logs del servidor:
    print(f"[Stripe] Reserva pagada: reservation_id={reservation_id} session={session_id} email={customer_email}")
