# routes_voice_answer_cr.py — SpainRoom Voice (Twilio → voice-cr)
import os
from urllib.parse import urlencode
from flask import Blueprint, request, make_response, current_app

bp_voice_answer_cr = Blueprint("voice_answer_cr", __name__)

VOICE_WS_URL = (os.getenv("VOICE_WS_URL") or "wss://voice-cr.onrender.com/cr").rstrip("/")
GREETING = (
    os.getenv("VOICE_GREETING")
    or "Gracias por llamar a SpainRoom. Conectamos su audio para asistencia."
).strip()

def _twiml(xml):
    r = make_response(xml, 200)
    r.headers["Content-Type"] = "application/xml"
    return r

@bp_voice_answer_cr.route("/voice/answer_cr", methods=["POST"])
def answer_cr():
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "")
    to_num = request.form.get("To", "")

    qs = urlencode({"callSid": call_sid, "from": from_num, "to": to_num})
    ws_url = f"{VOICE_WS_URL}?{qs}"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="es-ES">{GREETING}</Say>
  <Connect>
    <Stream url="{ws_url}" />
  </Connect>
</Response>"""

    try:
        current_app.logger.info("[VOICE-CR] callSid=%s from=%s to=%s ws=%s",
                                call_sid, from_num, to_num, ws_url)
    except Exception:
        pass
    return _twiml(xml)
