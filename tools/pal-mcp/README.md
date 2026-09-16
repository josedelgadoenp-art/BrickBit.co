# Equipo de tres modelos — PAL MCP Server

Montaje de la *Guía práctica: Claude Code, GPT-5.5 y Gemini* (@scorchlayer, 2026), dejado
listo para correr con un solo comando. Conecta **Claude Code**, **Codex CLI** y **Gemini CLI**
a través de [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server) — el antiguo
Zen MCP, Apache 2.0, de BeehiveInnovations. No es un producto de Anthropic, OpenAI ni Google.

No toca nada del sitio. Vive en `tools/`, que `netlify.toml` cierra con un redirect `force` a 404.

## Instalar

```bash
# macOS / Linux
bash tools/pal-mcp/instalar-pal.sh

# Windows
powershell -ExecutionPolicy Bypass -File tools\pal-mcp\instalar-pal.ps1
```

El script comprueba requisitos, instala lo que falte y registra el servidor en Claude Code
con `--scope user` (queda en todos tus proyectos, no sólo en este repositorio). Es idempotente:
correrlo otra vez sirve para actualizar.

Por omisión baja el servidor **de PyPI** (`pal-mcp-server`, versión fija, arranca en segundos).
Con `--git` / `-Git` lo baja del repositorio, que es lo que dice la guía original. Las dos vías
son oficiales; PyPI es más rápida, git te da siempre lo último.

## Lo que tienes que hacer tú a mano

Un script no puede entrar por ti: los dos CLIs abren el navegador y piden tu cuenta.
**No hacen falta claves de API.** Una sola vez:

```bash
codex      # elige "Sign in with ChatGPT"  — requiere plan de pago
gemini     # entra con tu cuenta de Google — nivel gratuito
```

Después **reinicia Claude Code**: los servidores MCP se cargan al arrancar la sesión, así que
uno registrado a media sesión no aparece hasta la siguiente.

Comprueba que quedó con `claude mcp get pal`.

## Cómo se pide

No hay comandos raros: se le pide a Claude Code en español y él llama a quien toque.

| Herramienta | Para qué | Ejemplo |
|---|---|---|
| `clink` | pasarle el trabajo a otro CLI | «arregla el buscador de CP de gmm.html y que Codex lo revise» |
| `clink` + rol `codereviewer` | que otro modelo mire el código con ojos nuevos | «clink with codex codereviewer: audita `lead.mjs`» |
| `clink` + rol `planner` | planear antes de escribir | «clink with gemini planner: cómo migrar `mapa.html` a Leaflet local» |
| `consensus` | que varios opinen y ver dónde no coinciden | «usa consensus: ¿el analizador a Supabase o se queda en JSON?» |

Los roles que documenta el proyecto son `default`, `planner` y `codereviewer`.

**El reparto que recomienda la guía:** Claude construye y lleva la sesión · Codex revisa lo
escrito · Gemini se traga lo que no le cabe a los otros (leer el repositorio entero, archivos
largos), que es donde su contexto de 1M marca la diferencia.

Para este repositorio en concreto, Gemini es el bueno para cosas como leer las 33 páginas de
`zona/` de una sentada, o revisar `cp_centroides.txt` (31,778 registros) completo.

## Qué está verificado y qué no

Siguiendo el principio de honestidad de datos del proyecto, separo lo comprobado de lo citado:

**Comprobado** (2026-09-16, contra las fuentes):
- El repositorio existe, es Apache 2.0 y efectivamente se llamaba Zen MCP.
- `pal-mcp-server` está publicado en PyPI, versión **11.1.0**.
- `@openai/codex` está en npm, versión **0.154.0**. Instalado y respondiendo.
- `@google/gemini-cli` está en npm, versión **0.60.0**. Instalado y respondiendo.
- Las herramientas `clink` y `consensus` existen, con los roles de arriba.

**Citado de la guía, sin verificar aquí** (confírmalo antes de contar con ello):
- Que GPT-5.5 salió el 23 de abril de 2026 y entra en los planes Plus, Pro, Business y
  Enterprise. Si tu plan no lo incluye, Codex funciona igual con el modelo que te toque.
- Los límites del nivel gratuito de Gemini (1M de contexto, 60 peticiones/minuto,
  1.000/día). Son los que publica su repositorio y pueden cambiar.

**Errata de la guía**: el PDF imprime la URL como `https:-/github.com/...`. Es `https://`.

## Coste

El servidor no cobra y corre en tu máquina. Lo que cuesta es lo de siempre: tu plan de
ChatGPT para Codex y, si te pasas del nivel gratuito, lo de Gemini.
