# Backend del Gemelo Digital — BrickBit

Proxy seguro para las llamadas a la IA de Anthropic (Claude). Con este backend,
la llave `sk-ant-...` vive como **secreto del servidor** y nunca se expone en el
navegador de tus usuarios.

Está implementado como **Cloudflare Worker** (gratis hasta 100,000 peticiones/día,
sin servidores que mantener), pero la lógica de `worker.js` es portable a
Vercel/Netlify Functions o a un Express propio si lo prefieres.

## Qué hace

- Expone `POST /api/claude`, que recibe `{ system, content, schema }` — exactamente
  lo que envían `gemelo-digital.html` y `comparar.html`.
- Construye la llamada real a `https://api.anthropic.com/v1/messages` en el
  servidor (modelo, `max_tokens`, salida estructurada), de modo que el endpoint
  **no** puede usarse como proxy genérico hacia Anthropic.
- Solo acepta bloques de contenido `text`, `image` y `document` (el plano + las
  instrucciones), valida el tamaño del cuerpo y aplica CORS configurable.

## Despliegue (5 minutos)

Requisitos: una cuenta gratuita de [Cloudflare](https://dash.cloudflare.com/sign-up)
y Node.js instalado.

```bash
cd backend

# 1. Autentícate en Cloudflare (abre el navegador)
npx wrangler login

# 2. Guarda tu llave de Anthropic como secreto (te la pedirá por consola)
npx wrangler secret put ANTHROPIC_API_KEY

# 2b. (Opcional) Textura de fachada con IA en el Gemelo Digital.
#     Crea una llave gratis en https://aistudio.google.com/apikey y guárdala:
npx wrangler secret put GOOGLE_AI_KEY

# 3. Despliega
npx wrangler deploy
```

> **`GOOGLE_AI_KEY`** habilita `POST /api/texture`, que usa **Gemini (Google AI
> Studio)** para generar una textura de fachada bajo demanda. Sin esta llave, el
> botón "🎨 Texturizar" del Gemelo avisa que falta configurarla; el resto del
> backend funciona igual. La generación de imágenes se factura por imagen en el
> plan de pago de Google (hay capa gratuita para pruebas).

Al terminar, wrangler imprime la URL del Worker, por ejemplo:

```
https://brickbit-api.tu-cuenta.workers.dev
```

## Conectar el frontend

1. Abre `gemelo-digital.html` → sección **00 / Configuración de APIs**.
2. Pega la URL del Worker en el campo **"URL del backend BrickBit"** y guarda.
3. Deja vacío el campo de la llave de Anthropic: ya no hace falta en el navegador.

El comparador (`comparar.html`) usa la misma configuración automáticamente.

## Endurecer para producción

- **CORS**: en `wrangler.toml`, cambia `ALLOWED_ORIGINS = "*"` por tu dominio:
  `ALLOWED_ORIGINS = "https://brickbit.co,https://www.brickbit.co"` y vuelve a
  desplegar. Peticiones desde otros orígenes recibirán 403.
- **Llave de Google Maps**: esa llave está diseñada para ser pública, pero
  restríngela en Google Cloud Console → Credenciales → *Application restrictions*
  → **HTTP referrers**, limitándola a `brickbit.co/*`. Así nadie puede usarla
  desde otro sitio.
- **Límites de uso**: si esperas tráfico, agrega
  [Cloudflare Rate Limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/)
  sobre la ruta `/api/claude`, o un chequeo de token de sesión propio en
  `worker.js`.

## Habilitar "Compartir proyecto" (enlaces cortos)

El botón **🔗 Compartir proyecto** funciona de dos formas:

- **Sin backend**: el enlace lleva el proyecto completo comprimido dentro de la
  propia URL. Funciona siempre, pero el enlace es largo.
- **Con backend + KV**: se genera un enlace corto (`?share=abc123`) que dura
  90 días. Para habilitarlo:

```bash
cd backend

# 1. Crea el almacén de enlaces (imprime un id)
npx wrangler kv namespace create SHARES

# 2. Descomenta el bloque [[kv_namespaces]] en wrangler.toml
#    y pega el id que imprimió el paso anterior

# 3. Vuelve a desplegar
npx wrangler deploy
```

Endpoints que agrega:

- `POST /api/share` — guarda el proyecto (máx. 300 KB) y devuelve `{ id }`
- `GET /api/share/{id}` — devuelve el proyecto guardado

## Informe de zona con búsqueda web

`POST /api/claude` acepta ahora `"webSearch": true`: el Worker agrega la
herramienta de búsqueda web de Anthropic y maneja las pausas de turno
(`pause_turn`). Lo usa el botón **🗞️ Informe IA en vivo** de `zona3d.html`.
No requiere configuración extra (la búsqueda web se cobra por uso en tu
cuenta de Anthropic).

## Alertas Valor Futuro (correo mensual)

El botón **🔔 Suscribirme** de `zona3d.html` guarda `{email, zona}` en el KV
(`POST /api/alerts`, requiere el namespace SHARES). Un **cron mensual**
(`[triggers]` en `wrangler.toml`, día 1 a las 14:00 UTC) genera el informe de
cada zona con Claude + búsqueda web y lo envía por correo con
[Resend](https://resend.com) (gratis hasta 3,000 correos/mes):

```bash
# 1. Crea una cuenta en resend.com y una API key
# 2. Guárdala como secreto
npx wrangler secret put RESEND_API_KEY

# 3. (Opcional) remitente propio con dominio verificado en Resend
#    npx wrangler secret put ALERTS_FROM   # ej. "BrickBit <alertas@brickbit.co>"

# 4. Redespliega
npx wrangler deploy
```

Sin `RESEND_API_KEY`, el cron simplemente no hace nada (no falla).

## Probar el backend

```bash
curl -X POST https://brickbit-api.tu-cuenta.workers.dev/api/claude \
  -H "content-type: application/json" \
  -d '{
    "system": "Responde en JSON.",
    "content": [{"type": "text", "text": "Di hola"}],
    "schema": {"type":"object","additionalProperties":false,"required":["saludo"],"properties":{"saludo":{"type":"string"}}}
  }'
```

Debe responder el JSON de la API de Anthropic con un bloque de texto que
contiene `{"saludo": "..."}`.
