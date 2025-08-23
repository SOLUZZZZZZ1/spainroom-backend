from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, time
from pathlib import Path

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
RES_FILE = DATA_DIR / "reservas.json"

def read_all():
    if not RES_FILE.exists():
        return []
    try:
        with open(RES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def write_all(items):
    with open(RES_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

@app.get("/api/reservas")
def list_reservas():
    items = read_all()
    # params: limit, offset
    try:
        limit = int(request.args.get("limit", "200"))
        offset = int(request.args.get("offset", "0"))
    except ValueError:
        limit, offset = 200, 0
    return jsonify({
        "items": items[offset:offset+limit],
        "total": len(items),
        "limit": limit,
        "offset": offset
    })

@app.post("/api/reservas")
def create_reserva():
    payload = request.get_json(silent=True) or {}
    required = ["roomId","roomTitle","roomLocation","price","name","email","phone","date"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return jsonify({"ok": False, "error": f"Missing: {', '.join(missing)}"}), 400
    items = read_all()
    item = {
        "id": f"R-{int(time.time()*1000)}",
        "createdAt": __import__("datetime").datetime.utcnow().isoformat()+"Z",
        **payload
    }
    items.insert(0, item)
    write_all(items)
    return jsonify({"ok": True, "item": item}), 201

if __name__ == "__main__":
    # Local dev: python app.py
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
