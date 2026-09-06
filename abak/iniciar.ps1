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

param(
    # Con -Red, la interfaz escucha en toda la red local y puedes entrar desde
    # el celular o la laptop. Sin el parametro, solo responde en esta maquina.
    [switch]$Red
)

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

# La IP con la que te ven los demas aparatos de tu casa.
function IPLocal {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Sort-Object -Property SkipAsSource, InterfaceMetric |
        Select-Object -First 1
    if ($ip) { return $ip.IPAddress }
    return $null
}

# Windows sabe si estas en tu casa o en el wifi de un cafe. Es la diferencia
# entre abrirle Abak a tu celular y abrirselo a desconocidos: Abak EJECUTA
# codigo, asi que quien alcance el puerto puede correr lo que quiera en esta
# maquina. En una red publica se pregunta antes; no se asume.
function RedesPublicas {
    $perfiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue |
        Where-Object { $_.NetworkCategory -eq "Public" }
    return @($perfiles)
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

if ($Red) {
    $publicas = RedesPublicas
    if ($publicas.Count -gt 0) {
        $nombres = ($publicas | ForEach-Object { $_.Name }) -join ", "
        Escribir ""
        Escribir "  CUIDADO: Windows tiene esta red marcada como PUBLICA ($nombres)." "Yellow"
        Escribir "  Abak ejecuta codigo Python. Quien alcance el puerto 3000 puede" "Yellow"
        Escribir "  correr lo que quiera en esta computadora. En el wifi de un cafe," "Yellow"
        Escribir "  un hotel o una oficina ajena, eso es cualquiera." "Yellow"
        Escribir ""
        $r = Read-Host "  Escribe SI (mayusculas) si aun asi quieres abrirlo en esta red"
        if ($r -cne "SI") {
            Escribir ""
            Escribir "  Cancelado. Arranca sin -Red para usarlo solo en esta maquina." "Green"
            Escribir ""
            exit 0
        }
    }
}

if (Responde 3000) {
    Escribir "  Interfaz ya estaba corriendo" "DarkGray"
} else {
    if ($Red) {
        Escribir "  Interfaz arrancando en :3000 (abierta a la red local)"
        # -H 0.0.0.0 hace que escuche en todas las interfaces, no solo en
        # localhost. El API se queda en 127.0.0.1 a proposito: el navegador
        # del celular solo habla con el 3000, y Next reenvia al API desde
        # ESTA maquina. Un puerto expuesto en vez de dos.
        $orden = "npm run dev -- -H 0.0.0.0"
    } else {
        Escribir "  Interfaz arrancando en :3000"
        $orden = "npm run dev"
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $orden `
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

if ($Red) {
    $ip = IPLocal
    if ($ip) {
        Escribir "  Desde el celular o la laptop: http://${ip}:3000" "Green"
        Escribir ""
        Escribir "  Si no abre desde el otro aparato, falta el permiso del" "DarkGray"
        Escribir "  Firewall: corre una vez  .\permitir-en-red.ps1  (pide admin)." "DarkGray"
    } else {
        Escribir "  No pude detectar la IP de esta maquina en la red." "Yellow"
    }
}

Escribir ""
Escribir "  Para cerrarlo todo:  .\detener.ps1" "DarkGray"
Escribir "  (o cierra las dos ventanas minimizadas)" "DarkGray"
Escribir ""
Start-Sleep -Seconds 4
