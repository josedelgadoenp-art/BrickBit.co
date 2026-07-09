# API pública de BrickBit — Score y pronóstico por zona

Expone la inteligencia de BrickBit (BrickBit Score + pronóstico) para **socios**
(portales, inmobiliarias, medios, fintech de crédito) vía API o widget embebible.
Corre en el Worker de Cloudflare; los datos se derivan de `estados.json` +
`forecast.json` del sitio.

Base: `https://brickbit-api.jose-delgado-enp.workers.dev`

## Endpoints

### `GET /api/score?zona={nombre}`
Devuelve el BrickBit Score (0–100, A–D) de una zona.
```json
{
  "zona": "Querétaro",
  "score": 78,
  "grade": "B",
  "parts": [
    {"k":"Valor Futuro","s":72},
    {"k":"Rendimiento","s":80},
    {"k":"Riesgo bajo","s":66},
    {"k":"Liquidez","s":60},
    {"k":"Oportunidad","s":100}
  ],
  "precio_m2": 20000,
  "plusvalia": 6.6,
  "yield": 6.5,
  "valorFuturo3a": 19
}
```
Sin `zona`: devuelve `{ "zonas": [ …ranking completo… ] }`.

### `GET /api/forecast?zona={nombre}`
Devuelve el pronóstico (multiplicadores con IC 90%) de la zona.
```json
{ "zona":"Querétaro", "forecast": { "1":{"f":1.06,"lo":1.02,"hi":1.10}, "3":{...}, "5":{...}, "10":{...} } }
```
Sin `zona`: `{ "zonas": ["Ciudad de México", "Guadalajara", …] }`.

CORS abierto (`*`) y `cache-control: 600s`. Pensado para lectura pública.

## Widget embebible (sin código)
El socio pega una línea donde quiera el badge:
```html
<script src="https://brickbit.co/assets/bb-widget.js" data-zona="Querétaro"></script>
```
Renderiza un badge con marca ("BrickBit Score B · +19% a 3 años") que enlaza a brickbit.co.

## Modelo de negocio sugerido
- **Score público** (widget) gratis → distribución de marca.
- **Forecast detallado / API por volumen** → de pago (tu forecast es tu IP).
- Control de acceso por **API key + rate limit** (misma mecánica del tope de Places) cuando se monetice.

## Para activarlo
1. Redesplegar el Worker: `cd backend && npx wrangler deploy` (el código ya está).
2. (Opcional) definir `SITE_URL` si el sitio no es `https://brickbit.co`.
3. Probar: `curl "https://brickbit-api.jose-delgado-enp.workers.dev/api/score?zona=Querétaro"`.
