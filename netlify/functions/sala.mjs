/**
 * Carrera de Amor — sincronización de sala
 * Netlify Function v2 + Upstash Redis (REST)
 *
 * Variables de entorno requeridas en Netlify:
 *   UPSTASH_REDIS_REST_URL
 *   UPSTASH_REDIS_REST_TOKEN
 *
 * Rutas:
 *   GET  /api/sala?code=AB12          -> { J: {...}|null, F: {...}|null }
 *   POST /api/sala  { code, who, data } -> escribe mi ranura y devuelve las dos
 */

const TTL = 60 * 60 * 6;          // la sala vive 6 horas
const MAX_BYTES = 24 * 1024;      // tope por ranura, para no abusar
const VENTANA = 60_000;           // ventana del limitador por IP
const TOPE = 260;                 // peticiones por IP por minuto

const golpes = new Map();         // limitador en memoria (por instancia)

function limitar(ip) {
  const ahora = Date.now();
  const reg = golpes.get(ip);
  if (!reg || ahora > reg.hasta) {
    golpes.set(ip, { n: 1, hasta: ahora + VENTANA });
    return true;
  }
  reg.n++;
  if (golpes.size > 500) {
    for (const [k, v] of golpes) if (ahora > v.hasta) golpes.delete(k);
  }
  return reg.n <= TOPE;
}

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': '*',
      'access-control-allow-headers': 'content-type',
      'access-control-allow-methods': 'GET,POST,OPTIONS',
    },
  });

async function redis(comandos) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error('Faltan las variables de Upstash');
  const r = await fetch(url.replace(/\/$/, '') + '/pipeline', {
    method: 'POST',
    headers: {
      authorization: 'Bearer ' + token,
      'content-type': 'application/json',
    },
    body: JSON.stringify(comandos),
  });
  if (!r.ok) throw new Error('Upstash respondió ' + r.status);
  return r.json();
}

const limpiaCodigo = (c) =>
  String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6);

const parsea = (v) => {
  if (!v) return null;
  try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; }
};

export default async (req) => {
  if (req.method === 'OPTIONS') return json({ ok: true });

  const ip =
    req.headers.get('x-nf-client-connection-ip') ||
    req.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
    'anon';
  if (!limitar(ip)) return json({ error: 'Demasiadas peticiones, respira tantito' }, 429);

  try {
    const url = new URL(req.url);

    if (req.method === 'GET') {
      const code = limpiaCodigo(url.searchParams.get('code'));
      if (code.length < 4) return json({ error: 'Código inválido' }, 400);
      const out = await redis([['MGET', `sala:${code}:J`, `sala:${code}:F`]]);
      const [vJ, vF] = out[0]?.result || [null, null];
      return json({ code, J: parsea(vJ), F: parsea(vF) });
    }

    if (req.method === 'POST') {
      const body = await req.json().catch(() => ({}));
      const code = limpiaCodigo(body.code);
      const who = body.who === 'F' ? 'F' : body.who === 'J' ? 'J' : null;
      if (code.length < 4 || !who) return json({ error: 'Faltan code o who' }, 400);

      const payload = JSON.stringify(body.data ?? {});
      if (payload.length > MAX_BYTES) return json({ error: 'Payload muy grande' }, 413);

      const out = await redis([
        ['SET', `sala:${code}:${who}`, payload, 'EX', String(TTL)],
        ['MGET', `sala:${code}:J`, `sala:${code}:F`],
      ]);
      const [vJ, vF] = out[1]?.result || [null, null];
      return json({ code, J: parsea(vJ), F: parsea(vF) });
    }

    return json({ error: 'Método no permitido' }, 405);
  } catch (e) {
    return json({ error: e.message || 'Error interno' }, 500);
  }
};

export const config = { path: '/api/sala' };
