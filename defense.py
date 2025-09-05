# defense.py
# Capa defensiva ligera para SpainRoom (cabeceras, rate limit y WAF simple).

from __future__ import annotations
import os
import re
from typing import Optional, Set, Dict

from flask import Flask, request, abort, g
from flask.typing import ResponseReturnValue

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:  # pragma: no cover
    Limiter = None
    get_remote_address = lambda: request.remote_addr or "0.0.0.0"  # type: ignore


SQLI_PATTERNS: Set[re.Pattern] = {
    re.compile(r"(?i)\bunion\b.*\bselect\b"),
    re.compile(r"(?i)\bdrop\s+table\b"),
    re.compile(r"(?i)\binsert\s+into\b"),
    re.compile(r"(?i)\bor\s+1\s*=\s*1\b"),
    re.compile(r"(?i)\bupdate\s+.*\bset\b"),
    re.compile(r"(?i)\bdelete\s+from\b"),
}

PATH_PATTERNS: Set[re.Pattern] = {
    re.compile(r"\.\./"),  # directory traversal
    re.compile(r"%2e%2e/"),  # encoded traversal
}

UA_BLOCKLIST: Set[str] = {
    "sqlmap", "nikto", "wpscan", "acunetix", "nessus", "owasp", "curl/7."  # típico pulso
}

def _looks_malicious() -> Optional[str]:
    """Inspección muy simple del request para señales maliciosas."""
    # Tamaño excesivo de body (protección básica)
    cl = request.content_length or 0
    if cl > 2_000_000:  # ~2MB
        return "req_too_large"

    # User-Agent sospechoso
    ua = (request.headers.get("User-Agent") or "").lower()
    for bad in UA_BLOCKLIST:
        if bad in ua:
            return "ua_blocked"

    # Query strings
    qs = request.query_string.decode("utf-8", "ignore")
    path = request.path or ""

    for p in SQLI_PATTERNS:
        if p.search(qs):
            return "sqli_qs"

    for p in PATH_PATTERNS:
        if p.search(path) or p.search(qs):
            return "path_traversal"

    # Cuerpos JSON / formulario
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            if request.is_json:
                payload = request.get_json(silent=True) or {}
                # Búsqueda sencilla
                blob = str(payload)
            else:
                blob = request.get_data(as_text=True) or ""
        except Exception:
            blob = ""

        for p in SQLI_PATTERNS:
            if p.search(blob):
                return "sqli_body"

    return None


def _apply_security_headers(resp) -> ResponseReturnValue:
    # Cabeceras de seguridad (básico, compatibles)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # CSP muy conservadora (ajusta si embebes iframes)
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' data: blob:; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https:;"
    )
    return resp


def init_defense(app: Flask) -> Dict[str, object]:
    """
    Activa:
      - Rate limiting (si flask-limiter está instalado)
      - WAF muy simple por patrón
      - Cabeceras de seguridad
      - Deny/Allow por IP vía variables de entorno (opcional)
    Env:
      DEFENSE_DENYLIST="1.2.3.4, 5.6.7.8"
      DEFENSE_ALLOWLIST="127.0.0.1"
      RATE_LIMIT_DEFAULT="200 per hour"  (formato flask-limiter)
      RATE_LIMIT_BURST="30 per minute"
    """
    # Listas de control IP
    deny: Set[str] = {ip.strip() for ip in (os.getenv("DEFENSE_DENYLIST") or "").split(",") if ip.strip()}
    allow: Set[str] = {ip.strip() for ip in (os.getenv("DEFENSE_ALLOWLIST") or "").split(",") if ip.strip()}

    # Rate limit (si está instalado)
    limiter = None
    if Limiter is not None:
        default = os.getenv("RATE_LIMIT_DEFAULT", "200 per hour")
        burst = os.getenv("RATE_LIMIT_BURST", "30 per minute")

        # Almacenamiento: si hay REDIS_URL lo usa, si no, memoria local
        storage_uri = os.getenv("REDIS_URL")
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[default, burst],
            storage_uri=storage_uri if storage_uri else None,
        )

    @app.before_request
    def _pre_defense():
        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "0.0.0.0"
        g.client_ip = ip

        if allow and ip not in allow:
            # Si usas allowlist, solo esas IP pasan
            abort(403, description="Forbidden")

        if ip in deny:
            abort(403, description="Forbidden")

        reason = _looks_malicious()
        if reason:
            abort(403, description=f"Blocked: {reason}")

    @app.after_request
    def _post_defense(resp):
        return _apply_security_headers(resp)

    return {
        "rate_limiter": bool(limiter),
        "denylist": deny,
        "allowlist": allow,
    }
