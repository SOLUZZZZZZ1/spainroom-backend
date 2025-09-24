# SpainRoom — Flask VOZ + Stripe (TwiML + Webhook firmado)
# Render:
#   Build: pip install -r requirements.txt
#   Start: gunicorn "app:create_app()"
#
# Env requeridas (Render → Environment):
#   VOICE_WS_URL=wss://spainroom-backend-1.onrender.com/cr
#   CR_LANGUAGE=es-ES
#   CR_TRANSCRIPTION_LANGUAGE=es-ES
#   CR_TTS_PROVIDER=Google
#   CR_VOICE=es-ES-Standard-A
#   CR_WELCOME=Bienvenido a SpainRoom
#   STRIPE_WEBHOOK_SECRET=whsec_*******

import os
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

def env(k, default=""):
    return os.getenv(k, default)

def _twiml_cr():
    """Construye TwiML <ConversationRelay> apuntando al WS del servicio VOZ."""
    ws_url     = env("VOICE_WS_URL", "").strip() or "wss://INVALID-WS-URL"
    lang       = env("CR_LANGUAGE", "es-ES").strip()
    trans_lang = env("CR_TRANSCRIPTION_LANGUAGE", lang).strip()
    tts        = env("CR_TTS_PROVIDER", "Google").strip()
    voice      = env("CR_VOICE", "").strip()
    welcome    = env("CR_WELCOME", "").strip()

    attrs = [
        f'url="{ws_url}"',
        f'language="{lang}"',
        f'transcriptionLanguage="{trans_lang}"',
        f'ttsProvider="{tts}"',
        'interruptible="speech"',
        'reportInputDuringAgentSpeech="none"',
    ]
    if welcome:
        attrs.append(f'welcomeGreeting="{welcome}"')
    if voice:
        attrs.append(f'voice="{voice}"')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <ConversationRelay {' '.join(attrs)} />
  </Connect>
</Response>'''

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # -------------------- Health & Diag --------------------
    @app.get("/health")
    def health():
        return jsonify(ok=True, service="flask-voz-stripe")

    @app.get("/diag_runtime")
    def diag_runtime():
        keys = ["VOICE_WS_URL","CR_LANGUAGE","CR_TRANSCRIPTION_LANGUAGE",
                "CR_TTS_PROVIDER","CR_VOICE","CR_WELCOME"]
        return jsonify({k: env(k, "") for k in keys})

    # -------------------- TwiML --------------------
    @app.route("/voice/answer_cr", methods=["GET","POST"])
    def voice_answer():
        return Response(_twiml_cr(), mimetype="application/xml")

    @app.route("/voice/fallback", methods=["GET","POST"])
    def voice_fallback():
        return Response(_twiml_cr(), mimetype="application/xml")

    # -------------------- Stripe Webhook --------------------
    @app.route("/webhooks/stripe", methods=["POST"])
    def stripe_webhook():
        secret = env("STRIPE_WEBHOOK_SECRET", "")
        if not secret:
            return jsonify(ok=False, error="missing_webhook_secret"), 500

        try:
            import stripe
        except Exception:
            return jsonify(ok=False, error="stripe_sdk_not_installed"), 500

        payload = request.get_data(cache=False, as_text=False)
        sig_hdr = request.headers.get("Stripe-Signature", "")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_hdr,
                secret=secret
            )
        except Exception as e:
            return jsonify(ok=False, error="invalid_signature", message=str(e)), 400

        ev_type = event.get("type", "")
        ev_id   = event.get("id", "")
        app.logger.info("Stripe event: %s id=%s", ev_type, ev_id)

        return jsonify(ok=True)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5005")), debug=True)
