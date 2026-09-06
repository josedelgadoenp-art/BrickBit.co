<# Abak — cierra el API y la interfaz. #>

function Matar([int]$puerto, [string]$que) {
    $conexiones = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue
    if (-not $conexiones) { Write-Host "  $que no estaba corriendo" -ForegroundColor DarkGray; return }
    # Ojo: no usar $pid como variable. En PowerShell es automatica y de solo
    # lectura (es el PID de esta consola); asignarla aqui lanza un error.
    foreach ($proceso in ($conexiones.OwningProcess | Select-Object -Unique)) {
        Stop-Process -Id $proceso -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  $que detenido" -ForegroundColor Green
}

Write-Host ""
Matar 8000 "API     "
Matar 3000 "Interfaz"
Write-Host ""
