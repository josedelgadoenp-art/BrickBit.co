# Equipo de tres modelos — PAL MCP Server

Montaje de la *Guía práctica: Claude Code, GPT-5.5 y Gemini* (@scorchlayer, 2026), dejado
listo para correr con un solo comando. Conecta **Claude Code**, **Codex CLI** y **Gemini CLI**
a través de [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server) — el antiguo
Zen MCP, Apache 2.0, de BeehiveInnovations. No es un producto de Anthropic, OpenAI ni Google.

No toca nada del sitio. Vive en `tools/`, que `netlify.toml` cierra con un redirect `force` a 404.

## Instalar

Los archivos viven en la rama `claude/wizardly-galileo-ct3dsf`. Si aún no está en `main`,
hay que cambiarse a ella antes: `git fetch origin claude/wizardly-galileo-ct3dsf` y
`git checkout claude/wizardly-galileo-ct3dsf`. Y hay que correrlo **desde la raíz del
repositorio**, no desde `C:\Users\TuUsuario`.

```powershell
# Windows (PowerShell) — ojo: aquí no hay 'bash'
powershell -ExecutionPolicy Bypass -File tools\pal-mcp\instalar-pal.ps1
```

```bash
# macOS / Linux
bash tools/pal-mcp/instalar-pal.sh
```

Si algo falla, esto dice qué falta (PowerShell):

```powershell
foreach ($c in 'git','node','npm','claude','uv') { "{0,-8} {1}" -f $c, $(if (Get-Command $c -EA SilentlyContinue) {(Get-Command $c).Source} else {'--- FALTA ---'}) }
```

Comprueba requisitos, instala lo que falte, acota el sandbox de Codex (ver abajo) y registra
el servidor en Claude Code con `--scope user` — queda en todos tus proyectos, no sólo en este
repositorio. Es idempotente: correrlo otra vez sirve para actualizar.

Por omisión instala el servidor **de PyPI** (`pal-mcp-server` 11.1.0, versión fija). Con `-Git`
lo toma del repositorio, que es lo que dice la guía. Las dos vías son oficiales.

## Antes de confiar en esto: el sandbox de Codex

Es lo más importante de esta página y la guía no lo menciona.

PAL trae, para `clink` → `codex`, este argumento **por defecto**:

```
--dangerously-bypass-approvals-and-sandbox
```

El propio Codex lo documenta así: *"Skip all confirmation prompts and execute commands without
sandboxing. **EXTREMELY DANGEROUS.** Intended solely for running in environments that are
externally sandboxed."* Tu portátil no es un entorno externamente aislado. Tal cual viene, pedir
«que Codex revise esto» le da a Codex una terminal sobre tu repositorio sin aislamiento y sin
pedirte permiso para nada.

Los tres CLIs vienen con criterios muy distintos, lo cual no es obvio:

| CLI | por defecto en PAL | qué puede hacer |
|---|---|---|
| `codex` | `--dangerously-bypass-approvals-and-sandbox` | **todo, sin preguntar** |
| `gemini` | `--approval-mode plan` | sólo planea, no toca nada |
| `claude` | `--permission-mode acceptEdits` | acepta ediciones solo |

`codex-sandbox.json` corrige el de Codex y el instalador lo copia a `~/.pal/cli_clients/codex.json`,
que tiene precedencia sobre el que trae el paquete. Cada rol recibe el mínimo que necesita:

| rol | sandbox | por qué |
|---|---|---|
| `codereviewer` | `read-only` | revisar es leer; no necesita escribir |
| `planner` | `read-only` | planear tampoco |
| `default` | `workspace-write` | escribe, pero acotado al directorio de trabajo |

Si prefieres el comportamiento original: `--sin-sandbox` (`-SinSandbox` en Windows).

## Lo que tienes que hacer tú a mano

Un script no puede entrar por ti: los dos CLIs abren el navegador. Una sola vez:

```bash
codex      # "Sign in with ChatGPT"  — requiere plan de pago
gemini     # cuenta de Google        — nivel gratuito
```

Después **reinicia Claude Code**: los servidores MCP se cargan al arrancar la sesión, así que
uno registrado a media sesión no aparece hasta la siguiente. Comprueba con `claude mcp get pal`.

### Las claves de API: la guía se queda corta

«No hacen falta claves de API» es verdad **sólo para `clink`**, que es el que lanza los binarios
`codex` y `gemini` ya autenticados con tu cuenta. Las otras herramientas del servidor —`chat`,
`consensus`, `thinkdeep`, `codereview`— no usan los CLIs: hablan por API y necesitan una clave.
Sin ella el servidor arranca igual y avisa:

```
No AI providers are configured. The server will start and stay discoverable,
but any tool needing a model will return an error result until a key is set.
```

O sea: `clink` gratis con tus cuentas; `consensus` quiere `GEMINI_API_KEY` u `OPENAI_API_KEY`
en el `env` del servidor.

## Cómo se pide

No hay comandos raros: se le pide a Claude Code en español y él llama a quien toque.

| Herramienta | Para qué | Ejemplo |
|---|---|---|
| `clink` | pasarle el trabajo a otro CLI | «arregla el buscador de CP de gmm.html y que Codex lo revise» |
| `clink` + `codereviewer` | otro modelo mira el código con ojos nuevos | «clink with codex codereviewer: audita `lead.mjs`» |
| `clink` + `planner` | planear antes de escribir | «clink with gemini planner: cómo migrar `mapa.html` a Leaflet local» |
| `consensus` | que varios opinen y ver dónde no coinciden | «usa consensus: ¿el analizador a Supabase o se queda en JSON?» |

Roles disponibles: `default`, `planner`, `codereviewer`.

**El reparto que recomienda la guía:** Claude construye y lleva la sesión · Codex revisa lo
escrito · Gemini se traga lo que no le cabe a los otros (leer el repositorio entero, archivos
largos), que es donde su contexto de 1M marca la diferencia.

Para este repositorio, Gemini es el bueno para leer las 33 páginas de `zona/` de una sentada,
o `cp_centroides.txt` (31,778 registros) completo.

## Qué está verificado y qué no

Siguiendo el principio de honestidad de datos del proyecto, separo lo comprobado de lo citado.

**Comprobado** (2026-09-16, ejecutado de verdad):
- El repositorio existe, es Apache 2.0 y efectivamente se llamaba Zen MCP.
- `pal-mcp-server` **11.1.0** instalado desde PyPI; el ejecutable arranca y registra 19
  herramientas: `chat, clink, jules, thinkdeep, planner, consensus, codereview, precommit,
  debug, secaudit, docgen, analyze, refactor, tracer, testgen, challenge, apilookup,
  listmodels, version`.
- Registrado en Claude Code y el cliente reporta **Status: Connected**.
- `@openai/codex` **0.154.0** y `@google/gemini-cli` **0.60.0** instalados y respondiendo.
- Los flags por defecto de cada CLI y la precedencia de `~/.pal/cli_clients`, leídos del
  paquete instalado.

**Citado de la guía, sin verificar** (confírmalo antes de contar con ello):
- Que GPT-5.5 salió el 23 de abril de 2026 y entra en los planes Plus, Pro, Business y
  Enterprise. Si tu plan no lo incluye, Codex funciona con el modelo que te toque.
- Los límites gratuitos de Gemini (1M de contexto, 60 peticiones/minuto, 1.000/día).

**Errata de la guía**: el PDF imprime la URL como `https:-/github.com/...`. Es `https://`.

## Coste

El servidor no cobra y corre en tu máquina. Lo que cuesta es tu plan de ChatGPT para Codex y,
si te pasas del nivel gratuito, lo de Gemini. Las herramientas por API (`consensus`) se cobran
aparte, por token, contra la clave que pongas.
