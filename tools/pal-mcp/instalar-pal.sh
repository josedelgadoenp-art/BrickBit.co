#!/usr/bin/env bash
# Instala el equipo de tres modelos descrito en GUIA-EQUIPO:
# PAL MCP Server (antes Zen MCP) + Codex CLI + Gemini CLI, y lo registra en Claude Code.
#
#   bash tools/pal-mcp/instalar-pal.sh
#   bash tools/pal-mcp/instalar-pal.sh --git      # servidor desde el repositorio, no desde PyPI
#   bash tools/pal-mcp/instalar-pal.sh --sin-sandbox   # deja el codex.json de PAL tal cual (no recomendado)
#
# Es idempotente: se puede volver a correr para actualizar.
set -euo pipefail

FUENTE="pypi"; ENDURECER=1
for a in "$@"; do
  [ "$a" = "--git" ] && FUENTE="git"
  [ "$a" = "--sin-sandbox" ] && ENDURECER=0
done

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
mal(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
paso(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

paso "1/6 · Requisitos"

command -v node >/dev/null 2>&1 || { mal "Falta Node.js — https://nodejs.org"; exit 1; }
ok "Node.js $(node --version)"
command -v claude >/dev/null 2>&1 || { mal "No encuentro 'claude'. Claude Code lleva la sesión y llama a los demás."; exit 1; }
ok "Claude Code presente"

if ! command -v uv >/dev/null 2>&1; then
  echo "  … instalando uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { mal "uv sigue sin aparecer. Abre una terminal nueva y repite."; exit 1; }
ok "uv en $(command -v uv)"

paso "2/6 · Codex CLI y Gemini CLI"
npm install -g @openai/codex @google/gemini-cli
ok "codex $(codex --version 2>/dev/null | tail -1)"
ok "gemini $(gemini --version 2>/dev/null | tail -1)"

paso "3/6 · PAL MCP Server"
if [ "$FUENTE" = "git" ]; then
  uv tool install --force "git+https://github.com/BeehiveInnovations/pal-mcp-server.git"
else
  uv tool install --force pal-mcp-server
fi
BIN="$(command -v pal-mcp-server || echo "$HOME/.local/bin/pal-mcp-server")"
[ -x "$BIN" ] || { mal "No quedó el ejecutable pal-mcp-server"; exit 1; }
ok "servidor en $BIN"

paso "4/6 · Acotar el sandbox de Codex"
# PAL trae, para clink→codex, --dangerously-bypass-approvals-and-sandbox. El propio Codex
# lo describe como "EXTREMELY DANGEROUS. Intended solely for running in environments that are
# externally sandboxed". Tu portátil no lo está. ~/.pal/cli_clients tiene precedencia.
if [ "$ENDURECER" = "1" ]; then
  mkdir -p "$HOME/.pal/cli_clients"
  if [ -e "$HOME/.pal/cli_clients/codex.json" ]; then
    cp "$HOME/.pal/cli_clients/codex.json" "$HOME/.pal/cli_clients/codex.json.bak.$(date +%s)"
    echo "  … había uno; guardé copia .bak"
  fi
  # sed quita la línea _comment para dejar un JSON limpio.
  sed '/"_comment"/d' "$AQUI/codex-sandbox.json" > "$HOME/.pal/cli_clients/codex.json"
  ok "codereviewer y planner en read-only, default en workspace-write"
else
  mal "sandbox SIN acotar, por --sin-sandbox: Codex correrá sin aprobaciones ni aislamiento"
fi

paso "5/6 · Registrar en Claude Code"
# --scope user: queda en todos los proyectos, no sólo en este repositorio.
claude mcp remove pal --scope user >/dev/null 2>&1 || true
claude mcp add-json pal "{
  \"command\": \"$BIN\",
  \"args\": [],
  \"env\": { \"PATH\": \"$HOME/.local/bin:$PATH\", \"DEFAULT_MODEL\": \"auto\" }
}" --scope user
claude mcp get pal || true

paso "6/6 · Falta que entres con tus cuentas"
cat <<'AYUDA'
  Los dos CLIs entran con cuenta, no con clave de API. Una sola vez, a mano,
  porque abren el navegador:

    codex     → "Sign in with ChatGPT"    (requiere plan de pago)
    gemini    → cuenta de Google          (nivel gratuito)

  Con eso ya funciona clink, que es el 90% de lo que promete la guía.

  Las demás herramientas (chat, consensus, thinkdeep) NO usan los CLIs: hablan
  por API y necesitan una clave. Sin ella el servidor arranca igual y avisa
  "No AI providers are configured". Si quieres consensus:

    claude mcp remove pal -s user
    # y vuelve a añadirlo con  "GEMINI_API_KEY": "..."  dentro de env

  Reinicia Claude Code: los MCP se cargan al arrancar la sesión.
AYUDA
