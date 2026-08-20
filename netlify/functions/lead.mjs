/**
 * BrickBit · Función Netlify: /api/lead
 * -------------------------------------
 * Recibe los prospectos de /financial, los valida (honeypot anti-bots,
 * tamaños, campos permitidos), los GUARDA en Upstash Redis y además los
 * reenvía firmados al Google Apps Script que escribe en la hoja de cálculo
 * y avisa por correo.
 *
 * El orden importa: primero se guarda en Upstash y después se manda a la
 * hoja. Antes, la hoja era el único registro que existía; si el Apps Script
 * se caía o alguien revocaba su despliegue, el prospecto se quedaba encolado
 * en el navegador del visitante y no había forma de verlo. Ahora la hoja es
 * una comodidad, no el sistema de registro.
 *
 * Variables de entorno (Netlify → Site settings → Environment):
 *   UPSTASH_REDIS_REST_URL     ya configuradas (mismo almacén que /api/diagnostico)
 *   UPSTASH_REDIS_REST_TOKEN   ya configuradas
 *   DIAG_ADMIN_TOKEN           la llave del panel; sirve para los dos formularios
 * Opcionales — si están, cada prospecto se copia a la hoja de cálculo:
 *   SHEETS_WEBHOOK_URL
 *   LEAD_SECRET
 *   ALLOWED_ORIGIN             ej. "https://brickbit.co"
 *
 * Rutas:
 *   POST   /api/lead                 -> guarda un prospecto (y lo copia a la hoja)
 *   GET    /api/lead                 -> devuelve los prospectos (privado)
 *   DELETE /api/lead?telefono=NNN    -> borra los prospectos de esa persona
 *
 * LA LLAVE VA EN EL HEADER, NUNCA EN LA URL:
 *   x-admin-token: LLAVE      (o  Authorization: Bearer LLAVE)
 * Un ?token= acabaría en los logs de Netlify y en el historial del navegador.
 *
 * Los ayudantes de Redis y de autorización están duplicados a propósito con
 * diagnostico.mjs en lugar de vivir en un módulo común: son cuarenta líneas,
 * el sitio no tiene paso de compilación, y así cada función se despliega sola
 * sin depender de que el empaquetador resuelva un import compartido.
 */

const LISTA = 'lead:leads';
const TOPE_LISTA = 5000;        // prospectos que se conservan
const MAX_BYTES = 8 * 1024;     // tope por registro
const VENTANA = 60_000;         // ventana del limitador por IP
const TOPE_POST = 20;           // envíos por IP por minuto (una persona manda hasta 3)

const CAMPOS_LEAD = [
  'fecha', 'nombre', 'apellido', 'edad', 'ingreso', 'telefono', 'correo',
  'producto', 'linea', 'hueco', 'score', 'origen', 'respuestas', 'ref',
  'accion',
];
const CAMPOS_EVENTO = ['evento', 'score', 'arquetipo', 'percentil', 'ref', 'origen', 'extra'];

const soloDigitos = (v) => String(v || '').replace(/\D/g, '');

const golpes = new Map();
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
  return reg.n <= TOPE_POST;
}

/* Comparación de la llave sin fugar por dónde dejó de coincidir. */
function mismaLlave(a, b) {
  const x = String(a || ''), y = String(b || '');
  if (!y || x.length !== y.length) return false;
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return d === 0;
}

/* La llave del panel, tomada SOLO de headers. Devuelve 'ok' | 'sin-config' | 'no'. */
function autorizado(req) {
  const esperada = process.env.DIAG_ADMIN_TOKEN;
  if (!esperada) return 'sin-config';
  const dada = req.headers.get('x-admin-token')
    || (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
  return mismaLlave(dada, esperada) ? 'ok' : 'no';
}

function cabeceras(req) {
  const permitido = process.env.ALLOWED_ORIGIN || '*';
  return {
    'access-control-allow-origin': permitido,
    'access-control-allow-methods': 'GET,POST,DELETE,OPTIONS',
    'access-control-allow-headers': 'content-type, x-admin-token, authorization',
    'cache-control': 'no-store',
    'x-robots-tag': 'noindex, nofollow',
  };
}

const json = (obj, status, req) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { ...cabeceras(req), 'content-type': 'application/json; charset=utf-8' },
  });

function hayRedis() {
  return Boolean(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);
}

async function redis(comandos) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error('Faltan las variables de Upstash');
  const r = await fetch(url.replace(/\/$/, '') + '/pipeline', {
    method: 'POST',
    headers: { authorization: 'Bearer ' + token, 'content-type': 'application/json' },
    body: JSON.stringify(comandos),
  });
  if (!r.ok) throw new Error('Upstash respondió ' + r.status);
  return r.json();
}

/* Copia a la hoja de cálculo. Devuelve true si la hoja la aceptó. */
async function aLaHoja(limpio) {
  const webhook = process.env.SHEETS_WEBHOOK_URL;
  const secret = process.env.LEAD_SECRET;
  if (!webhook || !secret) return false;
  const r = await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' }, // evita redirecciones raras de Apps Script
    body: JSON.stringify({ ...limpio, secret }),
    redirect: 'follow',                                       // Apps Script responde 302 a googleusercontent
  });
  const cuerpo = await r.text();
  try { return JSON.parse(cuerpo).ok === true; } catch { return r.ok; }
}

export default async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cabeceras(req) });

  const ip =
    req.headers.get('x-nf-client-connection-ip') ||
    req.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
    'anon';

  try {
    /* ---------- lectura privada ---------- */
    if (req.method === 'GET') {
      const permiso = autorizado(req);
      if (permiso === 'sin-config') return json({ ok: false, error: 'panel_sin_configurar' }, 503, req);
      if (permiso !== 'ok') return json({ ok: false, error: 'no_autorizado' }, 401, req);
      if (!hayRedis()) return json({ ok: false, error: 'sin_almacen' }, 503, req);

      const url = new URL(req.url);
      const limite = Math.min(1000, Math.max(1, +url.searchParams.get('limite') || 500));
      const out = await redis([
        ['LRANGE', LISTA, '0', String(limite - 1)],
        ['LLEN', LISTA],
      ]);
      const crudos = out[0]?.result || [];
      const leads = crudos.map((v) => {
        try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; }
      }).filter(Boolean);
      return json({ ok: true, total: out[1]?.result || leads.length, leads }, 200, req);
    }

    /* ---------- derecho de cancelación (LFPDPPP) ---------- */
    if (req.method === 'DELETE') {
      const permiso = autorizado(req);
      if (permiso === 'sin-config') return json({ ok: false, error: 'panel_sin_configurar' }, 503, req);
      if (permiso !== 'ok') return json({ ok: false, error: 'no_autorizado' }, 401, req);
      if (!hayRedis()) return json({ ok: false, error: 'sin_almacen' }, 503, req);

      const pedido = soloDigitos(new URL(req.url).searchParams.get('telefono'));
      if (pedido.length !== 10) return json({ ok: false, error: 'telefono_invalido' }, 400, req);

      /* Redis no borra "por campo": hay que leer la lista, quitar los registros
         de esa persona y reescribirla. Va en un solo pipeline (DEL + RPUSH)
         para que no pueda quedar a medias entre un comando y otro. */
      const actual = await redis([['LRANGE', LISTA, '0', '-1']]);
      const crudos = actual[0]?.result || [];
      const conservados = crudos.filter((v) => {
        try {
          const r = typeof v === 'string' ? JSON.parse(v) : v;
          return soloDigitos(r?.telefono) !== pedido;
        } catch {
          return true;   // lo ilegible se conserva: borrar de más es peor
        }
      });
      const borrados = crudos.length - conservados.length;
      if (!borrados) return json({ ok: true, borrados: 0 }, 200, req);

      const comandos = [['DEL', LISTA]];
      /* RPUSH respeta el orden de los valores que recibe, así que reescribir la
         lista conservada mantiene el original (más reciente primero, como LPUSH). */
      for (let i = 0; i < conservados.length; i += 500) {
        const lote = conservados.slice(i, i + 500)
          .map((v) => (typeof v === 'string' ? v : JSON.stringify(v)));
        comandos.push(['RPUSH', LISTA, ...lote]);
      }
      await redis(comandos);
      return json({ ok: true, borrados }, 200, req);
    }

    /* ---------- alta de un prospecto ---------- */
    if (req.method !== 'POST') return json({ ok: false, error: 'method_not_allowed' }, 405, req);
    if (!limitar(ip)) return json({ ok: false, error: 'demasiadas_peticiones' }, 429, req);

    let data;
    try { data = JSON.parse(await req.text()); }   // acepta application/json y text/plain
    catch { return json({ ok: false, error: 'json_invalido' }, 400, req); }

    // honeypot: los bots rellenan todo; los humanos nunca ven este campo
    if (data.website) return json({ ok: true }, 200, req);   // respuesta feliz, no se guarda nada

    const esEvento = data.tipo === 'evento';
    const permitidos = esEvento ? CAMPOS_EVENTO : CAMPOS_LEAD;
    const limpio = { tipo: esEvento ? 'evento' : 'lead' };
    for (const k of permitidos) {
      if (data[k] !== undefined && data[k] !== null) {
        limpio[k] = Array.isArray(data[k])
          ? data[k].slice(0, 20).map((x) => String(x).slice(0, 200))
          : String(data[k]).slice(0, 500);
      }
    }

    // un prospecto sin ningún dato de contacto ni contexto no le sirve a nadie
    if (!esEvento && !limpio.telefono && !limpio.correo && !limpio.producto) {
      return json({ ok: false, error: 'lead_vacio' }, 400, req);
    }
    limpio.fecha = limpio.fecha || new Date().toISOString();

    /* Los eventos son analítica, no prospectos: se mandan a la hoja pero no
       entran a la lista, para no ensuciar el panel. */
    let guardado = false;
    if (!esEvento && hayRedis()) {
      const payload = JSON.stringify(limpio);
      if (payload.length > MAX_BYTES) return json({ ok: false, error: 'registro_muy_grande' }, 413, req);
      await redis([
        ['LPUSH', LISTA, payload],
        ['LTRIM', LISTA, '0', String(TOPE_LISTA - 1)],
      ]);
      guardado = true;
    }

    /* La hoja ya no puede tumbar el registro: si falla, el prospecto ya está
       guardado y el visitante recibe ok, así que no lo reintenta de más. */
    let enHoja = false;
    try { enHoja = await aLaHoja(limpio); } catch { /* la hoja puede esperar */ }

    if (!guardado && !enHoja) {
      // ningún destino disponible: que el cliente lo encole y reintente
      return json({ ok: false, error: 'endpoint_no_configurado' }, 500, req);
    }
    return json({ ok: true, guardado, enHoja }, 200, req);
  } catch (e) {
    return json({ ok: false, error: e.message || 'error_interno' }, 500, req);
  }
};

export const config = { path: '/api/lead' };
