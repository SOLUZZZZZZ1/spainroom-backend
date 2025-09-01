import os
from flask import Flask, send_from_directory
from flask_cors import CORS

# -------------------------------------------------------------------
# Config básica
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# CORS robusto para desarrollo (React en 127.0.0.1:5177 / localhost:5177)
CORS(
    app,
    resources={r"/api/*": {"origins": [
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:5176", "http://localhost:5176",
        "http://127.0.0.1:5177", "http://localhost:5177",
        "http://127.0.0.1:5199", "http://localhost:5199",
    ]}},
    supports_credentials=False,
    allow_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS"]
)

# -------------------------------------------------------------------
# Rutas API (cédulas)
# -------------------------------------------------------------------
from routes.cedula import cedula_bp, init_db  # noqa: E402

init_db()  # crea data/cedula_checks.db si no existe
app.register_blueprint(cedula_bp, url_prefix="/api/cedula")

# -------------------------------------------------------------------
# Rutas simples
# -------------------------------------------------------------------
@app.route("/")
def index():
    return {
        "service": "SpainRoom Backend — Cédulas",
        "ok": True,
        "owners_check": "/owners-check",
        "api_sample": "/api/cedula/list",
    }

@app.route("/owners-check")
def owners_check():
    filename = "owners-check.html"
    if os.path.exists(os.path.join(STATIC_DIR, filename)):
        return send_from_directory(app.static_folder, filename)
    return {"hint": "Sube static/owners-check.html o usa /api/cedula/*"}, 200

@app.route("/ping")
def ping():
    return {"pong": True}

# -------------------------------------------------------------------
# Arranque
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 SpainRoom Backend listo en http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
