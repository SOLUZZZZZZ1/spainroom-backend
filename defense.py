import os, re
from functools import wraps
from flask import request, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

DEFENSE_WHITELIST = os.getenv("DEFENSE_WHITELIST", "/health,/voice").split(",")
R_LIMIT_MINUTE = os.getenv("RATE_LIMIT_PER_MINUTE", "120/minute")
R_LIMIT_HOURLY = os.getenv("RATE_LIMIT_PER_HOUR", "1000/hour")
R_LIMIT_SENSITIVE = os.getenv("RATE_LIMIT_SENSITIVE", "30/minute")

BAD_UA_REGEX = re.compile(r"sqlmap|nikto|dirbuster|crawler|scrapy|acunetix|masscan|nmap", re.I)

def _real_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or get_remote_address()).split(",")[0].strip()

def _is_whitelisted(path: str):
    for base in DEFENSE_WHITELIST:
        if path.startswith(base.strip()):
            return True
    return False

def init_defense(app):
    limiter = Limiter(
        key_func=lambda: _real_ip(),
        app=app,
        default_limits=[R_LIMIT_MINUTE, R_LIMIT_HOURLY],
        storage_uri=os.getenv("LIMITER_STORAGE_URI", "memory://"),
    )

    @app.before_request
    def _shield():
        if _is_whitelisted(request.path):
            return
        if request.method not in ("GET","POST","OPTIONS","HEAD"):
            abort(405)
        ua = request.headers.get("User-Agent","")
        if BAD_UA_REGEX.search(ua):
            abort(403)

    def sensitive_route(*limits):
        def wrap(fn):
            @limiter.limit(limits or (R_LIMIT_SENSITIVE,))
            @wraps(fn)
            def inner(*a, **kw): return fn(*a, **kw)
            return inner
        return wrap

    app.extensions["defense"] = {"limiter": limiter,"sensitive_route": sensitive_route}
    return limiter
