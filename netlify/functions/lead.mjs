/**
 * BrickBit · Función Netlify: /api/lead
 * -------------------------------------
 * Recibe los leads de /financial y los eventos de /destino, los valida
 * (honeypot anti-bots, tamaños, campos permitidos) y los reenvía firmados
 * con tu secreto al Google Apps Script que escribe en tu hoja de cálculo
 * y te avisa por correo.
 *
 * Variables de entorno requeridas (Netlify → Site settings → Environment):
 *   SHEETS_WEBHOOK_URL  → URL del despliegue de tu Apps Script (termina en /exec)
 *   LEAD_SECRET         → el mismo secreto que pusiste en Code.gs
 * Opcional:
 *   ALLOWED_ORIGIN      → ej. "https://brickbit.co" (por defecto acepta cualquiera)
 */

const CAMPOS_LEAD = [
  "fecha", "nombre", "apellido", "edad", "ingreso", "telefono", "correo",
  "producto", "linea", "hueco", "score", "origen", "respuestas", "ref",
  "accion",
];
const CAMPOS_EVENTO = ["evento", "score", "arquetipo", "percentil", "ref", "origen", "extra"];

export default async (req) => {
  const cors = corsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }
  if (req.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405, cors);
  }

  const webhook = process.env.SHEETS_WEBHOOK_URL;
  const secret = process.env.LEAD_SECRET;
  if (!webhook || !secret) {
    return json({ ok: false, error: "endpoint_no_configurado" }, 500, cors);
  }

  let data;
  try {
    data = JSON.parse(await req.text()); // acepta application/json y text/plain
  } catch {
    return json({ ok: false, error: "json_invalido" }, 400, cors);
  }

  // honeypot: los bots rellenan todo; los humanos nunca ven este campo
  if (data.website) {
    return json({ ok: true }, 200, cors); // respuesta feliz, pero no se guarda nada
  }

  const esEvento = data.tipo === "evento";
  const permitidos = esEvento ? CAMPOS_EVENTO : CAMPOS_LEAD;
  const limpio = { tipo: esEvento ? "evento" : "lead", secret };
  for (const k of permitidos) {
    if (data[k] !== undefined && data[k] !== null) {
      limpio[k] = Array.isArray(data[k])
        ? data[k].slice(0, 20).map((x) => String(x).slice(0, 200))
        : String(data[k]).slice(0, 500);
    }
  }

  // un lead sin ningún dato de contacto ni contexto no sirve de nada
  if (!esEvento && !limpio.telefono && !limpio.correo && !limpio.producto) {
    return json({ ok: false, error: "lead_vacio" }, 400, cors);
  }

  try {
    const r = await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" }, // evita redirecciones raras de Apps Script
      body: JSON.stringify(limpio),
      redirect: "follow", // Apps Script responde con un 302 a googleusercontent
    });
    const body = await r.text();
    let ok = false;
    try { ok = JSON.parse(body).ok === true; } catch { ok = r.ok; }
    return json({ ok }, ok ? 200 : 502, cors);
  } catch (e) {
    return json({ ok: false, error: "reenvio_fallido" }, 502, cors);
  }
};

export const config = { path: "/api/lead" };

function corsHeaders(req) {
  const allowed = process.env.ALLOWED_ORIGIN || "*";
  const origin = req.headers.get("origin") || "";
  const value = allowed === "*" ? "*" : (origin === allowed ? allowed : allowed);
  return {
    "Access-Control-Allow-Origin": value,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
  };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}
