# routes_twilio_stream.py — Twilio Voice → Media Streams (ConversationRelay WS)
# Conecta llamadas entrantes a tu WS: VOICE_WS_URL (p. ej. wss://voice-cr.onrender.com/cr)
# Nora · 2025-10-13

import os
from urllib.parse import urlencode
from flask import Blueprint, request, make_response, jsonify, current_app

bp_twilio_stream = Blueprint("twilio_stream", __name__)

# Config del servicio de voz
VOICE_WS_URL = (os.getenv("VOICE_WS_URL") or "wss://voice-cr.onrender.com/cr").rstrip("/")
GREETING     = (os.getenv("VOICE_GREETING") or
                "Gracias por llamar a SpainRoom. Conectamos su audio para asistencia.").strip()

def _twiml(xml_body: str):
    resp = make_response(xml_body, 200)
    resp.headers["Content-Type"] = "application/xml"
    return resp

@bp_twilio_stream.route("/twilio/voice/stream/inbound", methods=["POST"])
def voice_stream_inbound():
    """
    Webhook Voice de Twilio (A CALL COMES IN):
    Devuelve TwiML con <Connect><Stream url="wss://..."> para enviar el audio al WS.
    """
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "")
    to_num   = request.form.get("To", "")

    # Parámetros útiles para tu relay (voice-cr) en el querystring
    qs = urlencode({"callSid": call_sid, "from": from_num, "to": to_num})
    ws_url = f"{VOICE_WS_URL}?{qs}"

    # TwiML: saludo + connect stream
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="es-ES">{GREETING}</Say>
  <Connect>
    <Stream url="{ws_url}" />
  </Connect>
</Response>"""

    try:
        current_app.logger.info("[TWILIO STREAM] callSid=%s from=%s to=%s ws=%s",
                                call_sid, from_num, to_num, ws_url)
    except Exception:
        pass
    return _twiml(xml)

@bp_twilio_stream.route("/twilio/voice/stream/status", methods=["POST"])
def voice_stream_status():
    """
    (Opcional) Status Callback para eventos de la llamada (ringing, answered, completed...).
    Configurable en Twilio Console si lo deseas; aquí solo registramos en logs.
    """
    payload = {
        "CallStatus": request.form.get("CallStatus"),
        "CallSid": request.form.get("CallSid"),
        "From": request.form.get("From"),
        "To": request.form.get("To"),
        "Timestamp": request.form.get("Timestamp"),
        "Direction": request.form.get("Direction"),
        "Duration": request.form.get("CallDuration"),
    }
    try:
        current_app.logger.info("[TWILIO STATUS] %s", payload)
    except Exception:
        pass
    return jsonify(ok=True)
