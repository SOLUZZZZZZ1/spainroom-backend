@echo off
set ROOM_ID=1
set DOC_PATH=C:\spainroom\backend\cedula_prueba.pdf
set OUT=C:\spainroom\backend\resultado_test_cedula.txt

echo ==== SpainRoom - Test Cédula (Room %ROOM_ID%) ==== > "%OUT%"
echo Fecha: %date% %time% >> "%OUT%"

echo 1) Subida de documento >> "%OUT%"
curl -s -X POST "http://127.0.0.1:5000/api/rooms/%ROOM_ID%/cedula/doc" ^
  -F "file=@%DOC_PATH%" ^
  -H "X-Role: franquiciado" >> "%OUT%"
echo. >> "%OUT%"

echo 2) Actualizar estado (admin, VIGENTE) >> "%OUT%"
curl -s -X PATCH "http://127.0.0.1:5000/api/rooms/%ROOM_ID%/cedula" ^
  -H "Content-Type: application/json" ^
  -H "X-Role: admin" ^
  -d "{\"status\":\"VIGENTE\",\"ref\":\"ABC-123\",\"expiry\":\"2026-12-31\",\"lock\":true}" >> "%OUT%"
echo. >> "%OUT%"

echo 3) Verificación automática >> "%OUT%"
curl -s -X POST "http://127.0.0.1:5000/api/rooms/%ROOM_ID%/cedula/verify" >> "%OUT%"
echo. >> "%OUT%"

echo 4) Decisión manual (Admin VERIFIED) >> "%OUT%"
curl -s -X POST "http://127.0.0.1:5000/api/rooms/%ROOM_ID%/cedula/decision" ^
  -H "Content-Type: application/json" ^
  -H "X-Role: admin" ^
  -d "{\"decision\":\"VERIFIED\",\"reason\":\"Comprobada manualmente\"}" >> "%OUT%"
echo. >> "%OUT%"

echo 5) Auditoría (últimos 20 eventos) >> "%OUT%"
curl -s "http://127.0.0.1:5000/api/rooms/%ROOM_ID%/audit?limit=20" >> "%OUT%"
echo. >> "%OUT%"

type "%OUT%"
pause
