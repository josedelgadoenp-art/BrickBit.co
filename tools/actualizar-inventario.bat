@echo off
setlocal
REM ============================================================================
REM  BrickBit — Actualizar el inventario de Century 21 (Windows, doble clic)
REM
REM  Corre los tres pasos del refresco mensual, en orden:
REM    1) scraper 'todo'      -> baja/actualiza el inventario base
REM    2) scraper 'profundo'  -> exprime los estados grandes por municipio
REM    3) subir               -> limpia PII y lo sube al Worker de BrickBit
REM
REM  Uso: doble clic (te pide la clave de ingesta), o desde la terminal:
REM       tools\actualizar-inventario.bat TU_INGEST_SECRET
REM
REM  Debe ejecutarse desde la carpeta del proyecto (donde esta la carpeta tools).
REM ============================================================================

cd /d "%~dp0.."

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No encuentro Node.js. Instalalo desde https://nodejs.org y vuelve a intentar.
  pause & exit /b 1
)

set "KEY=%~1"
if "%KEY%"=="" set /p "KEY=Pega tu clave de ingesta (INGEST_SECRET) y presiona Enter: "
if "%KEY%"=="" (
  echo [ERROR] Sin clave no se puede subir. Vuelve a correrlo con la clave.
  pause & exit /b 1
)

echo.
echo === 1/3  Inventario base (scraper 'todo') ==========================
call node tools\c21-scraper.mjs todo
if errorlevel 1 ( echo [ERROR] Fallo el scraper base. Puedes reanudar corriendo esto de nuevo. & pause & exit /b 1 )

echo.
echo === 2/3  Profundizando estados grandes (scraper 'profundo') ========
call node tools\c21-scraper.mjs profundo

echo.
echo === 3/3  Subiendo al Worker (sin datos personales) =================
call node tools\c21-subir.mjs --key "%KEY%"
if errorlevel 1 ( echo [ERROR] Fallo la subida. Revisa la clave y tu conexion. & pause & exit /b 1 )

echo.
echo === LISTO ==========================================================
echo El inventario quedo actualizado en el Worker. El sitio lo refleja al instante
echo (Mapa, Analizador, Buscador con IA, Simulador 3D). No hace falta redeploy.
echo.
pause
endlocal
