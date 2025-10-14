# routes_voice_answer_cr.py — Twilio Voice → ConversationRelay (voice-cr)
# Nora · 2025-10-14
import os
from flask import Blueprint, request, make_response, jsonify

bp_voice_answer_cr = Blueprint("voice_answer_cr", __name__)

def env(k, default=""):
    return os.getenv(k, default)

def _twiml_cr():
    """Construye TwiML <ConversationRelay> apuntando al WS del servicio VOZ (voice-cr)."""
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

    # TwiML final
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <ConversationRelay {' '.join(attrs)} />
  </Connect>
</Response>'''
    return twiml

@bp_voice_answer_cr.route("/voice/answer_cr", methods=["GET","POST"])
def voice_answer_cr():
    """Webhook Twilio (A CALL COMES IN) → ConversationRelay hacia voice-cr."""
    return make_response(_twiml_cr(), 200, {"Content-Type": "application/xml"})

@bp_voice_answer_cr.route("/voice/fallback", methods=["GET","POST"])
def voice_fallback():
    """Fallback opcional (mismo TwiML)."""
    return make_response(_twiml_cr(), 200, {"Content-Type": "application/xml"})

@bp_voice_answer_cr.route("/diag_runtime", methods=["GET"])
def diag_runtime():
    keys = [
        "VOICE_WS_URL",
        "CR_LANGUAGE",
        "CR_TRANSCRIPTION_LANGUAGE",
        "CR_TTS_PROVIDER",
        "CR_VOICE",
        "CR_WELCOME",
    ]
    return jsonify({k: env(k, "") for k in keys})
