# -*- coding: utf-8 -*-
"""
Voice bot SpainRoom — Bilingüe ES/EN
- Detección de idioma y/o selección por DTMF (1=ES, 2=EN)
- Intenciones: reservas / propietarios / franquiciados / oportunidades / humano
- Desvío a humano y buzón con transcripción + email
- Seguro: si falta SMTP, sigue funcionando (no envía email)
"""
import os
from flask import Blueprint, request, Response
from email.message import EmailMessage
import smtplib

bp_voice = Blueprint("voice", __name__)

# Config
HUMAN_FALLBACK_NUMBER = os.getenv("HUMAN_FALLBACK_NUMBER", "+34616232306")
SUPPORT_EMAIL_TO      = os.getenv("SUPPORT_EMAIL_TO")
SMTP_HOST             = os.getenv("SMTP_HOST")
SMTP_PORT             = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER             = os.getenv("SMTP_USER")
SMTP_PASS             = os.getenv("SMTP_PASS")
SMTP_TLS              = (os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes"))

VOICE_ES = "Polly-Conchita"  # es-ES
VOICE_EN = "Polly-Joanna"    # en-US (puedes cambiar a Polly-Amy en-GB)

def twiml(xml_str: str) -> Response:
    return Response(xml_str, content_type="text/xml; charset=utf-8")

def send_email(subject: str, body: str):
    if not (SUPPORT_EMAIL_TO and SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = SUPPORT_EMAIL_TO
        msg.set_content(body)
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        if SMTP_TLS: s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
        s.quit()
        return True
    except Exception:
        return False

def detect_language(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "es"
    en_keys = ["hello","hi","good morning","reservation","booking","deposit","owner","franchise","opportunity","human","agent","english"]
    if any(k in t for k in en_keys):
        return "en"
    es_keys = ["hola","buenos días","reserva","reservar","señal","paga y señal","propietario","franquicia","franquiciado","oportunidad","persona","agente","español"]
    if any(k in t for k in es_keys):
        return "es"
    return "es"

def detect_intent(text: str, lang: str) -> str:
    t = (text or "").lower()
    if lang == "en":
        if any(k in t for k in ["human","agent","person","operator","talk to","speak to"]): return "human"
        if any(k in t for k in ["reserve","reservation","booking","deposit","signal"]):    return "reservas"
        if any(k in t for k in ["owner","landlord"]):                                      return "propietarios"
        if any(k in t for k in ["franchise","franchisee"]):                                return "franquiciados"
        if any(k in t for k in ["opportunity","opportunities","partner","collaborator"]):  return "oportunidades"
    else:
        if any(k in t for k in ["persona","agente","humano","operador","hablar"]):         return "human"
        if any(k in t for k in ["reserva","reservar","señal","paga y señal"]):             return "reservas"
        if any(k in t for k in ["propietar","dueño","propietario"]):                       return "propietarios"
        if "franquici" in t:                                                                return "franquiciados"
        if any(k in t for k in ["colaborador","oportunidad","oportunidades","inmobiliaria","inversi"]): return "oportunidades"
    return "unknown"

def m(lang: str, key: str) -> str:
    ES = {
        "welcome": ("Bienvenido a SpainRoom. Esta llamada puede ser grabada para mejorar la atención. "
                    "Puedes hablar en español o en inglés. Pulsa 1 para español, 2 para inglés. "
                    "¿En qué puedo ayudarte? Por ejemplo: reservas, propietarios, franquiciados u oportunidades."),
        "listen": "Te escucho.",
        "noinput": "No recibí respuesta.",
        "reservas": ("Puedo ayudarte con la paga y señal y con el estado de tu reserva. "
                     "¿Quieres iniciar o consultar una reserva?"),
        "propietarios": ("Área de propietarios. Puedo orientarte sobre contratos, liquidaciones y documentación. "
                         "¿Qué necesitas?"),
        "franquiciados": ("Área de franquiciados. Puedo informar sobre comisiones, liquidaciones y oportunidades por zona. "
                          "¿Qué deseas consultar?"),
        "oportunidades": ("Oportunidades para inmobiliarias y colaboradores. Puedo tomar tus datos y enviarte la información. "
                          "¿Te parece?"),
        "unclear": ("Perdona, no me ha quedado claro. Puedes decir reservas, propietarios, franquiciados, "
                    "oportunidades, o hablar con una persona."),
        "handoff": "Te paso con un agente en unos segundos.",
        "choice": ("Gracias. He tomado nota. Si quieres que te llame una persona ahora, di 'hablar con persona'. "
                   "Si prefieres dejar un mensaje, di 'dejar mensaje'."),
        "which": "¿Qué prefieres?",
        "voicemail": "Por favor, deja tu mensaje después del tono. Pulsa cualquier tecla para finalizar.",
        "thanks": "Gracias. Hemos recibido tu mensaje.",
        "fallback": "Puedo pasarte con un agente o grabar un mensaje. ¿Qué prefieres?",
    }
    EN = {
        "welcome": ("Welcome to SpainRoom. This call may be recorded to improve customer service. "
                    "You can speak in English or Spanish. Press 1 for Spanish, 2 for English. "
                    "How can I help you today? For example: reservations, landlords, franchisees or opportunities."),
        "listen": "I'm listening.",
        "noinput": "I didn’t receive a response.",
        "reservas": ("I can help you with the deposit and your reservation status. "
                     "Do you want to start or check a reservation?"),
        "propietarios": ("Landlords area. I can help with contracts, settlements and documentation. "
                         "What do you need?"),
        "franquiciados": ("Franchisees area. I can inform you about commissions, settlements and opportunities by area. "
                          "What would you like to check?"),
        "oportunidades": ("Opportunities for real estate partners and collaborators. I can take your details and send info. "
                          "Is that ok?"),
        "unclear": ("Sorry, I didn’t catch that. You can say reservations, landlords, franchisees, "
                    "opportunities, or speak to a person."),
        "handoff": "Connecting you to an agent now.",
        "choice": ("Thanks. Noted. If you want to speak to a person now, say 'talk to a person'. "
                   "If you prefer to leave a message, say 'leave a message'."),
        "which": "What do you prefer?",
        "voicemail": "Please leave your message after the tone. Press any key to finish.",
        "thanks": "Thank you. We’ve received your message.",
        "fallback": "I can connect you to an agent or record a message. What do you prefer?",
    }
    return (EN if lang == "en" else ES)[key]

@bp_voice.route("/voice/answer", methods=["POST"])
def voice_answer():
    welcome_es = m("es", "welcome")
    welcome_en = m("en", "welcome")
    return twiml(f"""
<Response>
  <Gather input="speech dtmf" language="es-ES" numDigits="1" timeout="5"
          hints="reservas, propietarios, franquiciados, oportunidades, hablar con persona, english, reservation"
          action="/voice/lang-or-intent" method="POST">
    <Say language="es-ES" voice="{VOICE_ES}">{welcome_es}</Say>
    <Pause length="1"/>
    <Say language="en-US" voice="{VOICE_EN}">{welcome_en}</Say>
  </Gather>
  <Say language="es-ES" voice="{VOICE_ES}">{m('es','noinput')}</Say>
  <Redirect method="POST">/voice/fallback</Redirect>
</Response>
""".strip())

@bp_voice.route("/voice/lang-or-intent", methods=["POST"])
def voice_lang_or_intent():
    digits = request.values.get("Digits", "")
    speech = request.values.get("SpeechResult", "")
    lang = "es" if digits == "1" else "en" if digits == "2" else detect_language(speech)
    intent = detect_intent(speech, lang)

    if intent == "human":
        return handoff(lang)

    msg = m(lang, intent) if intent in ("reservas","propietarios","franquiciados","oportunidades") else m(lang,"unclear")
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{msg}</Say>
  <Gather input="speech" language="{('en-US' if lang=='en' else 'es-ES')}" speechTimeout="auto"
          action="/voice/handle-intent?i={intent}&lang={lang}" method="POST">
    <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'listen')}</Say>
  </Gather>
  <Redirect method="POST">/voice/fallback?lang={lang}</Redirect>
</Response>
""".strip())

def handoff(lang: str) -> Response:
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'handoff')}</Say>
  <Dial callerId="{HUMAN_FALLBACK_NUMBER}">
    <Number>{HUMAN_FALLBACK_NUMBER}</Number>
  </Dial>
</Response>
""".strip())

@bp_voice.route("/voice/handle-intent", methods=["POST"])
def voice_handle_intent():
    lang = request.args.get("lang", "es")
    speech = request.values.get("SpeechResult", "")
    if detect_intent(speech, lang) == "human":
        return handoff(lang)
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'choice')}</Say>
  <Gather input="speech" language="{('en-US' if lang=='en' else 'es-ES')}" speechTimeout="auto"
          action="/voice/second-step?lang={lang}" method="POST">
    <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'which')}</Say>
  </Gather>
  <Redirect method="POST">/voice/fallback?lang={lang}</Redirect>
</Response>
""".strip())

@bp_voice.route("/voice/second-step", methods=["POST"])
def voice_second_step():
    lang = request.args.get("lang", "es")
    speech = (request.values.get("SpeechResult") or "").lower()
    if (lang == "en" and any(k in speech for k in ["human","agent","person","operator","talk","speak"])) or \
       (lang == "es" and any(k in speech for k in ["persona","agente","humano","operador","hablar"])):
        return handoff(lang)
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'voicemail')}</Say>
  <Record transcribe="true" playBeep="true" maxLength="120" finishOnKey="1234567890*#"
          transcribeCallback="/voice/transcribed?lang={lang}" recordingStatusCallback="/voice/recording-done" />
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'thanks')}</Say>
  <Hangup/>
</Response>
""".strip())

@bp_voice.route("/voice/fallback", methods=["POST"])
def voice_fallback():
    lang = request.args.get("lang", detect_language(request.values.get("SpeechResult","")))
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'fallback')}</Say>
  <Gather input="speech" language="{('en-US' if lang=='en' else 'es-ES')}" speechTimeout="auto"
          action="/voice/second-step?lang={lang}" method="POST">
    <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'listen')}</Say>
  </Gather>
  <Hangup/>
</Response>
""".strip())

@bp_voice.route("/voice/transcribed", methods=["POST"])
def voice_transcribed():
    lang = request.args.get("lang", "es")
    transcription = request.values.get("TranscriptionText", "")
    recording_url = request.values.get("RecordingUrl", "")
    subject = "[SpainRoom] New voicemail (EN transcription)" if lang == "en" else "[SpainRoom] Nuevo mensaje de voz (transcripción)"
    body = f"Transcription ({'EN' if lang=='en' else 'ES'}):\n{transcription}\n\nAudio: {recording_url}.mp3"
    send_email(subject, body)
    return ("", 204)

@bp_voice.route("/voice/recording-done", methods=["POST"])
def voice_recording_done():
    return ("", 204)
