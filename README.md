# SpainRoom Backend (Flask + Pillow)

API de SpainRoom para gestionar **habitaciones** y **fotos** de forma automática:
- Corrige orientación EXIF
- Recorta a **4:3** (uniforme para el Listado)
- Genera variantes **400/800/1200/1600** (WebP + JPG)
- Crea **placeholder LQIP** (blur) para carga elegante
- CRUD de habitaciones en **SQLite**

---

## 🚀 Stack
- Python 3.11+
- Flask 3
- Pillow 10
- SQLite
- gunicorn (producción)
- CORS habilitado para `/api/*`

---

## 📦 Instalación local

```bash
# (Opcional) crear venv
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
# http://localhost:5000
