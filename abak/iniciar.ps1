<#
    Abak — arranque de un solo clic (Windows).

    Levanta el API y la interfaz y abre el navegador. Existe porque el arranque
    normal son dos comandos en dos terminales, y para una herramienta de uso
    diario esa fricción se paga todos los días.

    Se usa `npm run dev` y no `npm run start` a propósito: `start` sirve una
    compilación ya hecha, y después de un `git pull` estaría enseñando la
    versión vieja sin avisar. `dev` siempre muestra el código que tienes. Como
    la aplicación es una sola ruta, compila una vez y ya.
#>

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot

function Escribir($texto, $color = "Gray") { Write-Host $texto -ForegroundColor $color }

function Falla($texto) {
    Escribir ""
    Escribir "  $texto" "Red"
    Escribir ""
    Read-Host "Enter para cerrar"
    exit 1
}

# ¿Hay algo escuchando en ese puerto? Un TcpClient es la manera rápida;
# Test-NetConnection tarda segundos y aquí se llama en un bucle.
function Responde([int]$puerto) {
    $cliente = New-Object Net.Sockets.TcpClient
    try   { $cliente.Connect("127.0.0.1", $puerto); $cliente.Close(); return $true }
    catch { return $false }
    finally { $cliente.Dispose() }
}

Escribir ""
Escribir "  Abak" "Green"
Escribir "  analisis economico sin codigo"
Escribir ""

$python = Join-Path $raiz ".venv\Scripts\python.exe"
$web    = Join-Path $raiz "apps\web"

if (-not (Test-Path $python)) {
    Falla "Falta el entorno de Python. Corre primero:  .\instalar.ps1"
}
if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Falla "Faltan las dependencias de la interfaz. Corre primero:  .\instalar.ps1"
}

if (Responde 8000) {
    Escribir "  API      ya estaba corriendo" "DarkGray"
} else {
    Escribir "  API      arrancando en :8000"
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "abak_api.main:app", "--port", "8000" `
        -WorkingDirectory $raiz -WindowStyle Minimized
}

if (Responde 3000) {
    Escribir "  Interfaz ya estaba corriendo" "DarkGray"
} else {
    Escribir "  Interfaz arrancando en :3000"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $web -WindowStyle Minimized
}

Escribir ""
Escribir "  Esperando a que la interfaz compile (la primera vez tarda mas)..."

$lista = $false
foreach ($intento in 1..90) {
    Start-Sleep -Seconds 1
    if (-not (Responde 3000)) { continue }
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $lista = $true; break }
    } catch { }
}

if (-not $lista) {
    Falla "La interfaz no respondio en 90 segundos. Mira las dos ventanas minimizadas: ahi esta el error."
}

if (-not (Responde 8000)) {
    Escribir ""
    Escribir "  Aviso: la interfaz abrio pero el API no responde en :8000." "Yellow"
    Escribir "  Vas a ver 'No se pudo cargar el catalogo'. Revisa la ventana del API." "Yellow"
}

Start-Process "http://localhost:3000"

Escribir ""
Escribir "  Listo: http://localhost:3000" "Green"
Escribir ""
Escribir "  Para cerrarlo todo:  .\detener.ps1" "DarkGray"
Escribir "  (o cierra las dos ventanas minimizadas)" "DarkGray"
Escribir ""
Start-Sleep -Seconds 4
