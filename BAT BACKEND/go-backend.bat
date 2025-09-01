@echo off
cd /d C:\spainroom\backend
if exist venv call venv\Scripts\activate
pip install -r requirements.txt || echo [AVISO] pip falló; arranco igual...
python app.py
pause
