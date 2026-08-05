/**
 * BrickBit Financial · Función Netlify: /api/diagnostico
 * ------------------------------------------------------
 * Guarda los diagnósticos de retiro que la gente completa en
 * /financial/analisisfinanciero. Antes vivían solo en el localStorage
 * del visitante — es decir, no llegaban a nadie. Ahora van a Upstash
 * Redis, que es el mismo almacén que ya usa la sala del juego, así que
 * no hay que dar de alta ningún servicio nuevo.
 *
 * Variables de entorno (Netlify → Site settings → Environment):
 *   UPSTASH_REDIS_REST_URL     ya configuradas
 *   UPSTASH_REDIS_REST_TOKEN   ya configuradas
 *   DIAG_ADMIN_TOKEN           la llave para leer los registros (la eliges tú)
 * Opcionales — si están, cada registro se reenvía también a la hoja de cálculo:
 *   SHEETS_WEBHOOK_URL
 *   LEAD_SECRET
 *
 * Rutas:
 *   POST /api/diagnostico                  -> guarda un registro
 *   GET  /api/diagnostico?token=LLAVE      -> devuelve los registros (privado)
 */

const LISTA = 'diag:leads';
const TOPE_LISTA = 5000;        // registros que se conservan
const MAX_BYTES = 8 * 1024;     // tope por registro
const VENTANA = 60_000;         // ventana del limitador por IP
const TOPE_POST = 12;           // envíos por IP por minuto

/* Los únicos campos que se guardan. Cualquier otra cosa que llegue se tira. */
const CAMPOS = [
  'fecha', 'nombre', 'telefono', 'edad', 'edadRetiro', 'ingresoMensual',
  'ahorroAcumulado', 'ahorroMensual', 'cotizaImss', 'aniosCotizados',
  'tasaReemplazo', 'edadFin', 'pensionEstimada', 'brechaMensual',
  'capitalObjetivo', 'proyeccionActual', 'coberturaMeta', 'aportacionPlan',
  'aportacionManual', 'cargaIngreso', 'ahorroFiscal', 'origen', 'ref',
];

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

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': process.env.ALLOWED_ORIGIN || '*',
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
    headers: { authorization: 'Bearer ' + token, 'content-type': 'application/json' },
    body: JSON.stringify(comandos),
  });
  if (!r.ok) throw new Error('Upstash respondió ' + r.status);
  return r.json();
}

/* Copia opcional a la hoja de cálculo, para no perder el CRM cuando exista. */
async function aLaHoja(reg) {
  const webhook = process.env.SHEETS_WEBHOOK_URL;
  const secret = process.env.LEAD_SECRET;
  if (!webhook || !secret) return;
  const cuerpo = {
    tipo: 'lead', secret,
    fecha: reg.fecha, nombre: reg.nombre, telefono: reg.telefono,
    edad: reg.edad, ingreso: reg.ingresoMensual,
    producto: 'Análisis financiero de retiro',
    linea: 'Retiro',
    origen: reg.origen || 'analisisfinanciero',
    accion: 'Completó el análisis de retiro',
    respuestas: [
      'Retiro a los ' + reg.edadRetiro,
      'Ahorra al mes: ' + reg.ahorroMensual,
      'Acumulado: ' + reg.ahorroAcumulado,
      'IMSS: ' + reg.cotizaImss,
      'Capital objetivo: ' + reg.capitalObjetivo,
      'Aportación requerida: ' + reg.aportacionPlan,
      'Cobertura de la meta: ' + reg.coberturaMeta,
    ],
  };
  await fetch(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify(cuerpo),
    redirect: 'follow',
  });
}

export default async (req) => {
  if (req.method === 'OPTIONS') return json({ ok: true });

  const ip =
    req.headers.get('x-nf-client-connection-ip') ||
    req.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
    'anon';

  try {
    /* ---------- lectura privada ---------- */
    if (req.method === 'GET') {
      const llave = process.env.DIAG_ADMIN_TOKEN;
      if (!llave) return json({ ok: false, error: 'panel_sin_configurar' }, 503);
      const url = new URL(req.url);
      if (!mismaLlave(url.searchParams.get('token'), llave)) {
        return json({ ok: false, error: 'no_autorizado' }, 401);
      }
      const limite = Math.min(1000, Math.max(1, +url.searchParams.get('limite') || 500));
      const out = await redis([
        ['LRANGE', LISTA, '0', String(limite - 1)],
        ['LLEN', LISTA],
      ]);
      const crudos = out[0]?.result || [];
      const leads = crudos.map((v) => {
        try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; }
      }).filter(Boolean);
      return json({ ok: true, total: out[1]?.result || leads.length, leads });
    }

    /* ---------- alta de un diagnóstico ---------- */
    if (req.method === 'POST') {
      if (!limitar(ip)) return json({ ok: false, error: 'demasiadas_peticiones' }, 429);

      let data;
      try { data = JSON.parse(await req.text()); }
      catch { return json({ ok: false, error: 'json_invalido' }, 400); }

      // honeypot: los bots llenan todo; una persona nunca ve este campo
      if (data.website) return json({ ok: true });

      const reg = {};
      for (const k of CAMPOS) {
        if (data[k] !== undefined && data[k] !== null) reg[k] = String(data[k]).slice(0, 200);
      }
      // sin teléfono el registro no le sirve a nadie
      if (!/^\d{10}$/.test(String(reg.telefono || '').replace(/\D/g, ''))) {
        return json({ ok: false, error: 'telefono_invalido' }, 400);
      }
      if (!reg.nombre || reg.nombre.trim().length < 3) {
        return json({ ok: false, error: 'nombre_invalido' }, 400);
      }
      reg.fecha = reg.fecha || new Date().toISOString();

      const payload = JSON.stringify(reg);
      if (payload.length > MAX_BYTES) return json({ ok: false, error: 'registro_muy_grande' }, 413);

      await redis([
        ['LPUSH', LISTA, payload],
        ['LTRIM', LISTA, '0', String(TOPE_LISTA - 1)],
      ]);

      // la copia a la hoja nunca debe tumbar el guardado principal
      try { await aLaHoja(reg); } catch { /* la hoja puede esperar */ }

      return json({ ok: true });
    }

    return json({ ok: false, error: 'metodo_no_permitido' }, 405);
  } catch (e) {
    return json({ ok: false, error: e.message || 'error_interno' }, 500);
  }
};

export const config = { path: '/api/diagnostico' };
