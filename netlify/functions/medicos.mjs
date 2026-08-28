/**
 * BrickBit Financial · Función Netlify: /api/medicos
 * --------------------------------------------------
 * Sirve el listado de médicos sin pago directo. Antes el archivo vivía en
 * /data/gnp_medicos_sin_pago_directo.txt y Netlify lo publicaba estático, así
 * que la reja de la página nunca lo protegió: cualquiera con la URL se bajaba
 * los 713 nombres. La ruta estática ahora está bloqueada en netlify.toml y el
 * contenido sólo sale por aquí, contra un pase.
 *
 * EL PASE
 * Lo emite /api/lead cuando registra un prospecto de la red hospitalaria. Es
 * "<vencimiento>.<firma>", con la firma HMAC-SHA256 del vencimiento. No se
 * puede fabricar sin el secreto y caduca solo. Con esto el listado deja de ser
 * descargable con un simple curl: hay que pasar por la puerta.
 *
 * No pretende ser un control de identidad —cualquiera puede llenar la puerta—
 * sino impedir la descarga masiva anónima y dejar rastro de quién entró.
 *
 * Variables de entorno:
 *   MEDICOS_SECRET     secreto de firma. Si falta, usa DIAG_ADMIN_TOKEN.
 *
 * El .txt se empaqueta con la función vía included_files en netlify.toml.
 */
import { createHmac, timingSafeEqual } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const VIGENCIA = 30 * 24 * 60 * 60 * 1000;   // 30 días
const VENTANA = 60_000;
const TOPE = 30;                              // peticiones por IP por minuto

/* El .txt se resuelve desde la raíz del despliegue, que es donde Netlify deja
   lo declarado en included_files. */
const RUTA = new URL('../../data/gnp_medicos_sin_pago_directo.txt', import.meta.url);

const golpes = new Map();
function limitar(ip) {
  const ahora = Date.now();
  const reg = golpes.get(ip);
  if (!reg || ahora > reg.hasta) { golpes.set(ip, { n: 1, hasta: ahora + VENTANA }); return true; }
  reg.n++;
  if (golpes.size > 500) for (const [k, v] of golpes) if (ahora > v.hasta) golpes.delete(k);
  return reg.n <= TOPE;
}

function secreto() {
  return process.env.MEDICOS_SECRET || process.env.DIAG_ADMIN_TOKEN || '';
}

/* Se exporta para que lead.mjs emita el pase con la misma firma. */
export function emitirPase() {
  const s = secreto();
  if (!s) return null;
  const exp = String(Date.now() + VIGENCIA);
  return exp + '.' + createHmac('sha256', s).update(exp).digest('hex');
}

function paseValido(pase) {
  const s = secreto();
  if (!s || !pase) return false;
  const i = String(pase).indexOf('.');
  if (i < 1) return false;
  const exp = pase.slice(0, i), firma = pase.slice(i + 1);
  if (!/^\d{10,16}$/.test(exp) || Number(exp) < Date.now()) return false;
  const esperada = createHmac('sha256', s).update(exp).digest('hex');
  /* timingSafeEqual exige el mismo largo; si difiere, no coincide y punto. */
  if (firma.length !== esperada.length) return false;
  try { return timingSafeEqual(Buffer.from(firma), Buffer.from(esperada)); }
  catch { return false; }
}

const cabeceras = {
  'access-control-allow-origin': process.env.ALLOWED_ORIGIN || '*',
  'access-control-allow-headers': 'content-type, x-pase',
  'access-control-allow-methods': 'GET,OPTIONS',
  'cache-control': 'no-store',
  'x-robots-tag': 'noindex, nofollow',
};

const json = (obj, status) =>
  new Response(JSON.stringify(obj), {
    status, headers: { ...cabeceras, 'content-type': 'application/json; charset=utf-8' },
  });

export default async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cabeceras });
  if (req.method !== 'GET') return json({ ok: false, error: 'metodo_no_permitido' }, 405);

  const ip = req.headers.get('x-nf-client-connection-ip')
    || req.headers.get('x-forwarded-for')?.split(',')[0].trim() || 'anon';
  if (!limitar(ip)) return json({ ok: false, error: 'demasiadas_peticiones' }, 429);

  if (!secreto()) return json({ ok: false, error: 'sin_configurar' }, 503);
  if (!paseValido(req.headers.get('x-pase'))) return json({ ok: false, error: 'sin_pase' }, 401);

  try {
    const txt = await readFile(RUTA, 'utf8');
    return new Response(txt, {
      status: 200,
      headers: { ...cabeceras, 'content-type': 'text/plain; charset=utf-8' },
    });
  } catch {
    return json({ ok: false, error: 'no_disponible' }, 500);
  }
};

export const config = { path: '/api/medicos' };
