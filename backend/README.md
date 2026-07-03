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

# 3. Despliega
npx wrangler deploy
```

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
