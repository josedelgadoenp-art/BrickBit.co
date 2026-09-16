#!/usr/bin/env bash
# Instala el equipo de tres modelos descrito en GUIA-EQUIPO:
# PAL MCP Server (antes Zen MCP) + Codex CLI + Gemini CLI, y lo registra en Claude Code.
#
#   bash tools/pal-mcp/instalar-pal.sh          # servidor desde PyPI (rápido, versión fija)
#   bash tools/pal-mcp/instalar-pal.sh --git    # servidor desde el repositorio (lo que dice la guía)
#
# Es idempotente: se puede volver a correr para actualizar.
set -euo pipefail

FUENTE="pypi"
[ "${1:-}" = "--git" ] && FUENTE="git"

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
mal(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
paso(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

paso "1/5 · Requisitos"

if ! command -v node >/dev/null 2>&1; then
  mal "Falta Node.js. Instálalo desde https://nodejs.org y vuelve a correr esto."
  exit 1
fi
ok "Node.js $(node --version)"

if ! command -v claude >/dev/null 2>&1; then
  mal "No encuentro el comando 'claude'. Claude Code es quien lleva la sesión y llama a los demás."
  exit 1
fi
ok "Claude Code presente"

# uv trae uvx, que es con lo que arranca el servidor sin tener que clonar nada.
if ! command -v uvx >/dev/null 2>&1; then
  echo "  … instalando uv (trae uvx)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uvx >/dev/null 2>&1 || { mal "uvx sigue sin aparecer. Abre una terminal nueva y repite."; exit 1; }
ok "uvx en $(command -v uvx)"

paso "2/5 · Codex CLI y Gemini CLI"
npm install -g @openai/codex @google/gemini-cli
ok "codex $(codex --version 2>/dev/null | tail -1)"
ok "gemini $(gemini --version 2>/dev/null | tail -1)"

paso "3/5 · Registrar PAL MCP Server en Claude Code"

if [ "$FUENTE" = "git" ]; then
  ARGS='["--from","git+https://github.com/BeehiveInnovations/pal-mcp-server.git","pal-mcp-server"]'
else
  ARGS='["pal-mcp-server"]'
fi

# --scope user: queda disponible en todos los proyectos, no sólo en este repositorio.
claude mcp remove pal --scope user >/dev/null 2>&1 || true
claude mcp add-json pal "{
  \"command\": \"uvx\",
  \"args\": $ARGS,
  \"env\": {
    \"PATH\": \"$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin\",
    \"DEFAULT_MODEL\": \"auto\"
  }
}" --scope user
ok "servidor 'pal' registrado (fuente: $FUENTE)"

paso "4/5 · Comprobación"
claude mcp get pal || true

paso "5/5 · Falta que entres con tus cuentas"
cat <<'AYUDA'
  Los dos CLIs entran con cuenta, no con clave de API. Hay que hacerlo UNA vez,
  a mano, porque abren el navegador:

    codex     → elige "Sign in with ChatGPT"   (requiere plan de pago)
    gemini    → entra con tu cuenta de Google  (nivel gratuito: 60 pet./min, 1.000/día)

  Después reinicia Claude Code para que cargue el servidor, y pruébalo con algo real:

    «arregla el login y que Codex lo revise»
    «clink with gemini to leer el repositorio entero y decirme qué está duplicado»
    «usa consensus: ¿conviene mover el analizador a Supabase o dejarlo en JSON?»
AYUDA
