# routes_twilio_stream.py — Twilio Voice -> WebSocket (ConversationRelay)
# Nora · 2025-10-12
import os
from flask import Blueprint, request, make_response, jsonify, current_app

bp_twilio_stream = Blueprint("twilio_stream", __name__)

# URL del WebSocket de tu servicio voice-cr
VOICE_CR_WS_URL = (os.getenv("VOICE_CR_WS_URL") or "wss://voice-cr.onrender.com/cr").strip()

# (Opcional) callback de estado de llamada
@bp_twilio_stream.route("/twilio/voice/status", methods=["POST"])
def twilio_status():
    try:
        current_app.logger.info("[TWILIO STATUS] %s", dict(request.form))
    except Exception:
        pass
    return ("", 204)

@bp_twilio_stream.route("/twilio/voice/stream", methods=["POST"])
def voice_stream():
    """
    Webhook de Twilio Voice (A CALL COMES IN).
    Devuelve TwiML que conecta la llamada a tu WebSocket (voice-cr).
    """
    from_num = request.form.get("From", "")
    to_num   = request.form.get("To", "")
    # Puedes inyectar metadatos en <Parameter> si quieres identificador
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="es-ES">Conectando. Un momento, por favor.</Say>
  <Connect>
    <Stream url="{VOICE_CR_WS_URL}">
      <Parameter name="from" value="{from_num}"/>
      <Parameter name="to" value="{to_num}"/>
    </Stream>
  </Connect>
</Response>'''
    resp = make_response(xml, 200)
    resp.headers["Content-Type"] = "application/xml"
    return resp

# (Opcional) test rápido sin Twilio (dev)
@bp_twilio_stream.route("/twilio/voice/stream/test", methods=["GET"])
def voice_stream_test():
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="es-ES">Prueba de conexión</Say>
  <Connect>
    <Stream url="{VOICE_CR_WS_URL}">
      <Parameter name="from" value="+34999999999"/>
      <Parameter name="to" value="+34999999999"/>
    </Stream>
  </Connect>
</Response>'''
    resp = make_response(xml, 200)
    resp.headers["Content-Type"] = "application/xml"
    return resp
