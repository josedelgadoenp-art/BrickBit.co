# Instala el equipo de tres modelos descrito en GUIA-EQUIPO:
# PAL MCP Server (antes Zen MCP) + Codex CLI + Gemini CLI, y lo registra en Claude Code.
#
#   powershell -ExecutionPolicy Bypass -File tools\pal-mcp\instalar-pal.ps1
#   ... -Git          # servidor desde el repositorio, no desde PyPI
#   ... -SinSandbox   # deja el codex.json de PAL tal cual (no recomendado)
#
# Es idempotente: se puede volver a correr para actualizar.
param([switch]$Git, [switch]$SinSandbox)
$ErrorActionPreference = "Stop"

$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
function Ok  ($m){ Write-Host "  [ok] $m" -ForegroundColor Green }
function Mal ($m){ Write-Host "  [!!] $m" -ForegroundColor Red }
function Paso($m){ Write-Host "`n$m" -ForegroundColor White }

Paso "1/6 - Requisitos"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Mal "Falta Node.js. Bajalo de https://nodejs.org (version LTS), reinicia PowerShell y repite."
  exit 1
}
Ok "Node.js $(node --version)"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Mal "No encuentro 'claude' en esta maquina."
  Write-Host "     Todo esto se registra CONTRA el Claude Code local. Si solo lo usas"
  Write-Host "     desde la web, primero instalalo aqui:  npm install -g @anthropic-ai/claude-code"
  exit 1
}
Ok "Claude Code presente"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "  ... instalando uv"
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Mal "uv sigue sin aparecer. Abre una terminal nueva."; exit 1 }
Ok "uv en $((Get-Command uv).Source)"

Paso "2/6 - Codex CLI y Gemini CLI"
npm install -g '@openai/codex' '@google/gemini-cli'
Ok "codex y gemini instalados"

Paso "3/6 - PAL MCP Server"
if ($Git) { uv tool install --force "git+https://github.com/BeehiveInnovations/pal-mcp-server.git" }
else      { uv tool install --force pal-mcp-server }
$bin = (Get-Command pal-mcp-server -ErrorAction SilentlyContinue).Source
if (-not $bin) { $bin = "$env:USERPROFILE\.local\bin\pal-mcp-server.exe" }
if (-not (Test-Path $bin)) { Mal "No quedo el ejecutable pal-mcp-server"; exit 1 }
Ok "servidor en $bin"

Paso "4/6 - Acotar el sandbox de Codex"
# PAL trae, para clink->codex, --dangerously-bypass-approvals-and-sandbox. El propio Codex lo
# describe como "EXTREMELY DANGEROUS. Intended solely for running in environments that are
# externally sandboxed". Tu portatil no lo esta. ~/.pal/cli_clients tiene precedencia.
if (-not $SinSandbox) {
  $dir = "$env:USERPROFILE\.pal\cli_clients"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $dest = "$dir\codex.json"
  if (Test-Path $dest) {
    Copy-Item $dest "$dest.bak.$([int](Get-Date -UFormat %s))"
    Write-Host "  ... habia uno; guarde copia .bak"
  }
  # Quita la linea _comment para dejar un JSON limpio.
  Get-Content "$Aqui\codex-sandbox.json" | Where-Object { $_ -notmatch '"_comment"' } | Set-Content $dest -Encoding UTF8
  Ok "codereviewer y planner en read-only, default en workspace-write"
} else {
  Mal "sandbox SIN acotar, por -SinSandbox: Codex correra sin aprobaciones ni aislamiento"
}

Paso "5/6 - Registrar en Claude Code"
$cfg = @{
  command = $bin
  args    = @()
  env     = @{ PATH = "$env:USERPROFILE\.local\bin;$env:Path"; DEFAULT_MODEL = "auto" }
} | ConvertTo-Json -Compress -Depth 5

# --scope user: queda en todos los proyectos, no solo en este repositorio.
try { claude mcp remove pal --scope user 2>$null | Out-Null } catch {}
claude mcp add-json pal $cfg --scope user
claude mcp get pal

Paso "6/6 - Falta que entres con tus cuentas"
Write-Host @"
  Los dos CLIs entran con cuenta, no con clave de API. Una sola vez, a mano,
  porque abren el navegador:

    codex     -> "Sign in with ChatGPT"    (requiere plan de pago)
    gemini    -> cuenta de Google          (nivel gratuito)

  Con eso ya funciona clink, que es el 90% de lo que promete la guia.

  Las demas herramientas (chat, consensus, thinkdeep) NO usan los CLIs: hablan
  por API y necesitan una clave. Sin ella el servidor arranca igual y avisa
  "No AI providers are configured". Si quieres consensus, vuelve a anadirlo
  con GEMINI_API_KEY dentro de env.

  Reinicia Claude Code: los MCP se cargan al arrancar la sesion.
"@
