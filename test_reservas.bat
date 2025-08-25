@echo off
REM ===========================================
REM SpainRoom - Test automático de Reservas
REM ===========================================
setlocal

REM === Config editable ===
set BASE=http://127.0.0.1:5000/api
set ROOM_ID=1
set START_DATE=2025-09-10
set END_DATE=2025-09-20
set GUEST_NAME=Prueba Auto
set GUEST_EMAIL=prueba.auto@spainroom.local
set OUT=C:\spainroom\backend\resultado_test_reservas.txt

echo =============================== > "%OUT%"
echo SpainRoom - Test Reservas (Room %ROOM_ID%) >> "%OUT%"
echo Fecha: %date% %time% >> "%OUT%"
echo =============================== >> "%OUT%"

echo 0) Health >> "%OUT%"
curl -s "%BASE:/api=/api%/health" >> "%OUT%"
echo.>> "%OUT%"

echo 1) Disponibilidad (%START_DATE% a %END_DATE%) >> "%OUT%"
curl -s "%BASE%/rooms/%ROOM_ID%/availability?from=%START_DATE%&to=%END_DATE%" >> "%OUT%"
echo.>> "%OUT%"

echo 2) Crear reserva (pending) >> "%OUT%"
curl -s -X POST "%BASE%/reservations" ^
  -H "Content-Type: application/json" ^
  -d "{\"room_id\":%ROOM_ID%,\"guest_name\":\"%GUEST_NAME%\",\"guest_email\":\"%GUEST_EMAIL%\",\"start_date\":\"%START_DATE%\",\"end_date\":\"%END_DATE%\"}" > "%TEMP%\res_create.json"

type "%TEMP%\res_create.json" >> "%OUT%"
echo.>> "%OUT%"

REM === Extraer ID de la reserva con PowerShell ===
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\res_create.json' | ConvertFrom-Json).id"`) do set RES_ID=%%I

echo ID de la reserva creada: %RES_ID% >> "%OUT%"
echo.>> "%OUT%"

echo 3) Listar reservas pending (TOP 200) >> "%OUT%"
curl -s "%BASE%/reservations?status=pending" >> "%OUT%"
echo.>> "%OUT%"

echo 4) Aprobar reserva (PATCH -> approved) >> "%OUT%"
curl -s -X PATCH "%BASE%/reservations/%RES_ID%" ^
  -H "Content-Type: application/json" ^
  -d "{\"status\":\"approved\"}" >> "%OUT%"
echo.>> "%OUT%"

echo 5) Cancelar reserva (PATCH -> cancelled) >> "%OUT%"
curl -s -X PATCH "%BASE%/reservations/%RES_ID%" ^
  -H "Content-Type: application/json" ^
  -d "{\"status\":\"cancelled\"}" >> "%OUT%"
echo.>> "%OUT%"

echo 6) Estado final de reservas (últimas) >> "%OUT%"
curl -s "%BASE%/reservations" >> "%OUT%"
echo.>> "%OUT%"

echo =============================== >> "%OUT%"
echo PRUEBA FINALIZADA. Resultados en: %OUT%
echo ===============================

type "%OUT%"
pause
endlocal
