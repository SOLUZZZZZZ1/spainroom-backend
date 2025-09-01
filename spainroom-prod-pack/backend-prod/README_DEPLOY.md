# SpainRoom Backend — Deploy a Producción (Render/Railway)

1) Sube tu backend (con app.py) + estos archivos a un repo: wsgi.py, Procfile, requirements-prod.txt.
2) Render (Web Service) → Build: `pip install -r requirements.txt` (o requirements-prod.txt) → Start:
   `gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
3) Obtén la URL HTTPS (p.ej. https://spainroom-backend.onrender.com).
