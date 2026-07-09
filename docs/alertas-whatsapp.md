# Alertas de zona por WhatsApp (MVP)

Cuando el pronóstico de una zona que un usuario vigila (panel "Mi BrickBit" →
Alertas) cambia **más que su umbral**, el Worker de Cloudflare te manda **a ti
(José)** un WhatsApp con el resumen. Así detectas movimiento y das seguimiento.

- **Detección:** compara la apreciación proyectada (`data/forecast.json`) de cada
  zona/horizonte contra la línea base guardada en `zone_alerts.ultimo_valor`.
  La primera corrida sólo fija la línea base (no avisa); a partir de ahí, avisa
  cuando el cambio ≥ `umbral_pct`.
- **Frecuencia:** cada lunes 15:00 UTC (cron en `wrangler.toml`). También puedes
  dispararlo a mano (ver "Probar").
- **Código:** `backend/worker.js` → `runZoneAlerts()`. No hace nada si faltan
  secretos, así que es seguro desplegar antes de configurarlos.

## Lo que tú debes hacer

### 1) Twilio (remitente de WhatsApp)
1. Crea cuenta en <https://www.twilio.com>.
2. Para **probar ya**: activa el **WhatsApp Sandbox** (Messaging → Try it out →
   Send a WhatsApp message). Desde tu celular, manda el código `join …` al número
   del sandbox para "unirte". El sandbox permite mensajes de texto libre sin
   plantilla — perfecto para el MVP, que sólo te escribe a ti.
3. Anota: **Account SID**, **Auth Token** y el **From** del sandbox
   (p. ej. `whatsapp:+14155238886`).
4. Para **producción** (opcional, luego): registra tu propio número de WhatsApp
   Business y una plantilla aprobada; cambia sólo `TWILIO_WHATSAPP_FROM`.

### 2) Supabase (leer las alertas)
1. Supabase → Project Settings → **API**.
2. Copia la **Project URL** y la **service_role key** (⚠️ secreta, sólo servidor).

### 3) Guarda los secretos en el Worker
```bash
cd backend
npx wrangler secret put SUPABASE_URL           # https://xxxx.supabase.co
npx wrangler secret put SUPABASE_SERVICE_KEY    # service_role key
npx wrangler secret put TWILIO_ACCOUNT_SID
npx wrangler secret put TWILIO_AUTH_TOKEN
npx wrangler secret put TWILIO_WHATSAPP_FROM    # whatsapp:+14155238886 (sandbox)
npx wrangler secret put ALERT_WHATSAPP_TO       # whatsapp:+5215584681927 (tu número)
npx wrangler secret put ALERT_TEST_KEY          # una clave que inventes, para el disparo manual
npx wrangler deploy
```
`SITE_URL` es opcional (por defecto `https://brickbit.co`).

## Probar (sin esperar al lunes)

La **primera** corrida sólo fija líneas base. Corre el disparo manual dos veces:

```bash
# 1) fija líneas base (no avisa)
curl -X POST "https://brickbit-api.jose-delgado-enp.workers.dev/api/zone-alerts/run?key=TU_ALERT_TEST_KEY"
```
Para forzar un aviso de prueba, en Supabase → Table editor → `zone_alerts`,
cambia el `ultimo_valor` de una fila activa a un número muy distinto (o ponlo en
NULL para re-fijar), y vuelve a llamar:
```bash
curl -X POST "https://brickbit-api.jose-delgado-enp.workers.dev/api/zone-alerts/run?key=TU_ALERT_TEST_KEY"
```
Respuesta esperada: `{"ok":true,"revisadas":N,"cambios":[…]}` y, si hubo cambios,
te llega el WhatsApp.

## Migrar a "avisar a cada usuario" (cuando quieras)
Requiere: (a) capturar el **teléfono** de cada usuario en el panel y guardarlo
(tabla `profiles` con `user_id, telefono, whatsapp_opt_in`), (b) una **plantilla
de WhatsApp aprobada** (los mensajes iniciados por el negocio la exigen fuera de
la ventana de 24 h), (c) en `runZoneAlerts`, en vez de un solo `ALERT_WHATSAPP_TO`,
enviar a `profiles.telefono` de cada `user_id`. El resto del pipeline ya queda listo.
