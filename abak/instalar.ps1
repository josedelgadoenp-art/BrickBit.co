<#
    Abak — instalacion (Windows). Se corre una sola vez.
    El equivalente de `make instalar`, que en Windows no existe.
#>

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot

Write-Host ""
Write-Host "  Instalando Abak. Tarda varios minutos la primera vez." -ForegroundColor Green
Write-Host ""

Push-Location $raiz
try {
    if (-not (Test-Path (Join-Path $raiz ".venv"))) {
        Write-Host "  [1/4] Creando el entorno de Python..."
        python -m venv .venv
    } else {
        Write-Host "  [1/4] El entorno de Python ya existe" -ForegroundColor DarkGray
    }

    $pip = Join-Path $raiz ".venv\Scripts\pip.exe"
    Write-Host "  [2/4] Dependencias del nucleo (pandas, statsmodels, xgboost...)"
    & $pip install -q --upgrade pip
    & $pip install -e "packages/core[todo,dev]"

    Write-Host "  [3/4] API y worker"
    & $pip install -e services/worker -e services/api

    Write-Host "  [4/4] Interfaz (npm install)"
    Push-Location (Join-Path $raiz "apps\web")
    npm install
    Pop-Location

    Write-Host ""
    Write-Host "  Listo. Arranca con:  .\iniciar.ps1" -ForegroundColor Green
    Write-Host "  O crea un acceso directo:  .\crear-acceso-directo.ps1" -ForegroundColor Green
    Write-Host ""
}
finally {
    Pop-Location
}
Read-Host "Enter para cerrar"
