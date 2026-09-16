# Instala el equipo de tres modelos descrito en GUIA-EQUIPO:
# PAL MCP Server (antes Zen MCP) + Codex CLI + Gemini CLI, y lo registra en Claude Code.
#
#   powershell -ExecutionPolicy Bypass -File tools\pal-mcp\instalar-pal.ps1
#   powershell -ExecutionPolicy Bypass -File tools\pal-mcp\instalar-pal.ps1 -Git
#
# Es idempotente: se puede volver a correr para actualizar.
param([switch]$Git)
$ErrorActionPreference = "Stop"

function Ok  ($m){ Write-Host "  [ok] $m"  -ForegroundColor Green }
function Mal ($m){ Write-Host "  [!!] $m"  -ForegroundColor Red }
function Paso($m){ Write-Host "`n$m" -ForegroundColor White }

Paso "1/5 - Requisitos"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Mal "Falta Node.js. Instalalo desde https://nodejs.org y vuelve a correr esto."
  exit 1
}
Ok "Node.js $(node --version)"

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Mal "No encuentro el comando 'claude'. Claude Code es quien lleva la sesion y llama a los demas."
  exit 1
}
Ok "Claude Code presente"

# uv trae uvx, que es con lo que arranca el servidor sin tener que clonar nada.
if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
  Write-Host "  ... instalando uv (trae uvx)"
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
  Mal "uvx sigue sin aparecer. Abre una terminal nueva y repite."
  exit 1
}
Ok "uvx en $((Get-Command uvx).Source)"

Paso "2/5 - Codex CLI y Gemini CLI"
npm install -g '@openai/codex' '@google/gemini-cli'
Ok "codex y gemini instalados"

Paso "3/5 - Registrar PAL MCP Server en Claude Code"

if ($Git) {
  $palArgs = @("--from","git+https://github.com/BeehiveInnovations/pal-mcp-server.git","pal-mcp-server")
  $fuente  = "git"
} else {
  $palArgs = @("pal-mcp-server")
  $fuente  = "pypi"
}

# ConvertTo-Json escapa solo las barras invertidas de las rutas de Windows.
$cfg = @{
  command = "uvx"
  args    = $palArgs
  env     = @{
    PATH         = "$env:USERPROFILE\.local\bin;$env:Path"
    DEFAULT_MODEL = "auto"
  }
} | ConvertTo-Json -Compress -Depth 5

# --scope user: queda disponible en todos los proyectos, no solo en este repositorio.
try { claude mcp remove pal --scope user 2>$null | Out-Null } catch {}
claude mcp add-json pal $cfg --scope user
Ok "servidor 'pal' registrado (fuente: $fuente)"

Paso "4/5 - Comprobacion"
claude mcp get pal

Paso "5/5 - Falta que entres con tus cuentas"
Write-Host @"
  Los dos CLIs entran con cuenta, no con clave de API. Hay que hacerlo UNA vez,
  a mano, porque abren el navegador:

    codex     -> elige "Sign in with ChatGPT"   (requiere plan de pago)
    gemini    -> entra con tu cuenta de Google  (nivel gratuito: 60 pet./min, 1.000/dia)

  Despues reinicia Claude Code para que cargue el servidor, y pruebalo con algo real:

    <<arregla el login y que Codex lo revise>>
    <<clink with gemini to leer el repositorio entero y decirme que esta duplicado>>
    <<usa consensus: conviene mover el analizador a Supabase o dejarlo en JSON?>>
"@
