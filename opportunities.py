# opportunities.py
import os
import re
import smtplib
from email.message import EmailMessage
from flask import Blueprint, request, jsonify

bp_opp = Blueprint("opportunities", __name__, url_prefix="/api/oportunidades")

EMAIL_TO = os.getenv("CONTACT_EMAIL_TO")  # destinatario (ej. soporte@spainroom.es)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_TLS  = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

def _is_email(v: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v or ""))

def _normalize_bool(v):
    if isinstance(v, bool): 
        return v
    if v is None: 
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "on")

@bp_opp.post("/contacto")
def contacto():
    """
    Espera JSON:
    {
      empresa: str, nombre: str, email: str, telefono: str, provincia: str,
      interes: {captar: bool, portfolio: bool, inversion: bool, colaboraciones: bool},
      mensaje: str, consentimiento: bool
    }
    """
    data = request.get_json(silent=True) or {}

    empresa  = (data.get("empresa") or "").strip()
    nombre   = (data.get("nombre") or "").strip()
    email    = (data.get("email") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    provincia = (data.get("provincia") or "").strip()
    interes  = data.get("interes") or {}
    captar   = _normalize_bool(interes.get("captar"))
    portfolio = _normalize_bool(interes.get("portfolio"))
    inversion = _normalize_bool(interes.get("inversion"))
    colaboraciones = _normalize_bool(interes.get("colaboraciones"))
    mensaje  = (data.get("mensaje") or "").strip()
    consentimiento = _normalize_bool(data.get("consentimiento"))

    # Validación básica
    if not empresa:
        return jsonify(error="empresa requerida"), 400
    if not nombre:
        return jsonify(error="nombre requerido"), 400
    if not _is_email(email):
        return jsonify(error="email inválido"), 400
    if not telefono:
        return jsonify(error="teléfono requerido"), 400
    if not consentimiento:
        return jsonify(error="debes aceptar el tratamiento de datos"), 400

    # Payload para email o almacenamiento futuro
    payload = {
        "empresa": empresa,
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "provincia": provincia,
        "interes": {
            "captar": captar,
            "portfolio": portfolio,
            "inversion": inversion,
            "colaboraciones": colaboraciones,
        },
        "mensaje": mensaje,
        "origen": "oportunidades-web",
    }

    # Enviar correo si SMTP configurado
    sent = False
    smtp_error = None
    if EMAIL_TO and SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[SpainRoom] Oportunidades — {empresa} / {nombre}"
            msg["From"] = SMTP_USER
            msg["To"] = EMAIL_TO
            body = (
                "Nueva solicitud de Oportunidades (web)\n\n"
                f"Empresa: {empresa}\n"
                f"Nombre: {nombre}\n"
                f"Email: {email}\n"
                f"Teléfono: {telefono}\n"
                f"Provincia: {provincia}\n"
                f"Interés:\n"
                f"  - Captar habitaciones: {captar}\n"
                f"  - Compartir portfolio: {portfolio}\n"
                f"  - Inversión: {inversion}\n"
                f"  - Colaboraciones: {colaboraciones}\n"
                f"\nMensaje:\n{mensaje}\n"
            )
            msg.set_content(body)

            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            sent = True
        except Exception as e:
            smtp_error = str(e)

    result = {"ok": True, "notified": sent, "data": payload}
    if smtp_error:
        result["warning"] = f"email_not_sent: {smtp_error}"

    return jsonify(result), 200
