# -*- coding: utf-8 -*-
# voice_bot.py — SpainRoom Voice Bot ES/EN (Twilio)
import os
from flask import Blueprint, request, Response
from email.message import EmailMessage
import smtplib

bp_voice = Blueprint("voice", __name__)

HUMAN_FALLBACK_NUMBER = os.getenv("HUMAN_FALLBACK_NUMBER", "+34616232306")

VOICE_ES = "Polly-Conchita"
VOICE_EN = "Polly-Joanna"


def twiml(xml: str) -> Response:
    return Response(xml, content_type="text/xml; charset=utf-8")


def detect_language(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["hello", "reservation", "booking", "deposit", "owner", "franchise", "opportunity"]):
        return "en"
    if any(k in t for k in ["hola", "reserva", "reservar", "señal", "propietario", "franquicia", "oportunidad"]):
        return "es"
    return "es"


def detect_intent(text: str, lang: str) -> str:
    t = (text or "").lower()
    if lang == "en":
        if "reservation" in t or "booking" in t: return "reservas"
        if "landlord" in t or "owner" in t: return "propietarios"
        if "franchise" in t: return "franquiciados"
        if "opportunit" in t or "partner" in t: return "oportunidades"
        if "person" in t or "agent" in t: return "human"
    else:
        if "reserva" in t or "señal" in t: return "reservas"
        if "propietario" in t or "dueño" in t: return "propietarios"
        if "franquici" in t: return "franquiciados"
        if "oportunidad" in t or "colaborador" in t: return "oportunidades"
        if "persona" in t or "agente" in t: return "human"
    return "unknown"


def m(lang: str, key: str) -> str:
    ES = {
        "welcome": "Bienvenido a SpainRoom. Puedes hablar en español o en inglés. ¿En qué puedo ayudarte?",
        "noinput": "No recibí respuesta.",
        "reservas": "Puedo ayudarte con la paga y señal o consultar tu reserva.",
        "propietarios": "Área de propietarios. Contratos, liquidaciones y documentación.",
        "franquiciados": "Área de franquiciados. Comisiones, liquidaciones y oportunidades.",
        "oportunidades": "Oportunidades para inmobiliarias y colaboradores. ¿Quieres que te tomemos los datos?",
        "unclear": "Perdona, no me ha quedado claro. Puedes decir reservas, propietarios, franquiciados u oportunidades.",
        "handoff": "Te paso con un agente ahora.",
        "listen": "Te escucho.",
    }
    EN = {
        "welcome": "Welcome to SpainRoom. You can speak in English or Spanish. How can I help you?",
        "noinput": "I didn’t receive a response.",
        "reservas": "I can help you with the deposit or your reservation status.",
        "propietarios": "Landlords area. Contracts, settlements and documentation.",
        "franquiciados": "Franchisees area. Commissions, settlements and opportunities.",
        "oportunidades": "Opportunities for agencies and collaborators. Shall I take your details?",
        "unclear": "Sorry, I didn’t catch that. You can say reservations, landlords, franchisees or opportunities.",
        "handoff": "Connecting you to an agent now.",
        "listen": "I'm listening.",
    }
    return (EN if lang == "en" else ES)[key]


@bp_voice.route("/voice/answer", methods=["POST"])
def voice_answer():
    # Primer mensaje, sin opción 1/2
    return twiml(f"""
<Response>
  <Gather input="speech" language="es-ES" speechTimeout="auto"
          hints="reservas, propietarios, franquiciados, oportunidades, reservation, landlord, franchisee, opportunity, person, agent"
          action="/voice/lang-or-intent" method="POST">
    <Say language="es-ES" voice="{VOICE_ES}">{m('es','welcome')}</Say>
    <Pause length="1"/>
    <Say language="en-US" voice="{VOICE_EN}">{m('en','welcome')}</Say>
  </Gather>
  <Say language="es-ES" voice="{VOICE_ES}">{m('es','noinput')}</Say>
  <Redirect method="POST">/voice/fallback</Redirect>
</Response>
""".strip())


@bp_voice.route("/voice/lang-or-intent", methods=["POST"])
def voice_lang_or_intent():
    speech = request.values.get("SpeechResult", "")
    lang = detect_language(speech)
    intent = detect_intent(speech, lang)

    if intent == "human":
        return handoff(lang)

    msg = m(lang, intent) if intent in ("reservas", "propietarios", "franquiciados", "oportunidades") else m(lang, "unclear")

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
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'unclear')}</Say>
  <Redirect method="POST">/voice/fallback?lang={lang}</Redirect>
</Response>
""".strip())


@bp_voice.route("/voice/fallback", methods=["POST"])
def voice_fallback():
    lang = detect_language(request.values.get("SpeechResult", ""))
    return twiml(f"""
<Response>
  <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'unclear')}</Say>
  <Gather input="speech" language="{('en-US' if lang=='en' else 'es-ES')}" speechTimeout="auto"
          action="/voice/handle-intent?lang={lang}" method="POST">
    <Say language="{('en-US' if lang=='en' else 'es-ES')}" voice="{(VOICE_EN if lang=='en' else VOICE_ES)}">{m(lang,'listen')}</Say>
  </Gather>
</Response>
""".strip())
