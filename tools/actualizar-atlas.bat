@echo off
setlocal
chcp 65001 >nul
REM ============================================================================
REM  BrickBit Atlas — Refresco mensual completo (Windows, doble clic)
REM
REM  Corre TODO en orden, del scraper al informe final:
REM    1) scraper 'todo'      inventario nacional de Century 21
REM    2) scraper 'profundo'  exprime la CDMX municipio por municipio
REM    3) Fase 0              ingesta al lago (listados + DENUE + CP + calles)
REM    4) Fase 1              malla H3 + variables geoespaciales
REM    5) Fase 2              AVM + intervalos calibrados
REM    6) Fase 3              índice temporal + campo espacial
REM
REM  Uso: doble clic. No pide claves ni sube nada a ningún lado.
REM
REM  Para subir el inventario al Worker de BrickBit, eso es aparte:
REM    tools\actualizar-inventario.bat TU_INGEST_SECRET
REM
REM  Tarda entre 30 y 60 minutos, casi todo en el scraper. Se puede cortar con
REM  Ctrl+C y volver a correr: el scraper reanuda donde iba.
REM ============================================================================

cd /d "%~dp0.."
set "RAIZ=%CD%"

echo.
echo ================================================================
echo   BrickBit Atlas - refresco mensual
echo   Carpeta: %RAIZ%
echo ================================================================

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No encuentro Node.js. Instalalo desde https://nodejs.org
  pause & exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No encuentro Python. Instalalo desde https://python.org
  pause & exit /b 1
)

echo.
echo === 1/6  Inventario nacional (10-25 min) ========================
call node tools\c21-scraper.mjs todo
if errorlevel 1 (
  echo [ERROR] Fallo el scraper base. Vuelve a correr esto: reanuda donde iba.
  pause & exit /b 1
)

echo.
echo === 2/6  Profundizando la CDMX por alcaldia (2-5 min) ===========
call node tools\c21-scraper.mjs profundo --estado ciudad-de-mexico
if errorlevel 1 (
  echo [AVISO] El barrido profundo fallo. Se sigue con lo que trajo el paso 1.
)

cd /d "%RAIZ%\atlas"

echo.
echo === 3/6  Fase 0: ingesta al lago ================================
call python -m pipelines.fase0
if errorlevel 1 ( echo [ERROR] Fallo la Fase 0. & pause & exit /b 1 )

echo.
echo === 4/6  Fase 1: malla y variables geoespaciales (~1 min) =======
call python -m pipelines.fase1
if errorlevel 1 ( echo [ERROR] Fallo la Fase 1. & pause & exit /b 1 )

echo.
echo === 5/6  Fase 2: AVM e intervalos (~3 min) ======================
call python -m pipelines.fase2
if errorlevel 1 ( echo [ERROR] Fallo la Fase 2. & pause & exit /b 1 )

echo.
echo === 6/6  Fase 3: tiempo y campo espacial (~5 min) ===============
call python -m pipelines.fase3
if errorlevel 1 ( echo [ERROR] Fallo la Fase 3. & pause & exit /b 1 )

echo.
echo ================================================================
echo   LISTO. El lago quedo en atlas\data\
echo.
echo   Para ver todo esto en un mapa:
echo       cd atlas
echo       streamlit run app.py
echo.
echo   Cada corrida mensual suma inventario nuevo. Cuando haya dos
echo   capturas separadas en el tiempo se podra estimar el crecimiento
echo   POR CELDA, que es lo unico que hoy la Fase 3 no puede hacer.
echo ================================================================
echo.
pause
