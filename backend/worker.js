/**
 * BrickBit — Backend del Gemelo Digital (Cloudflare Worker)
 *
 * Proxy seguro hacia la API de Anthropic: la llave vive como secreto del
 * Worker (ANTHROPIC_API_KEY) y nunca llega al navegador. El frontend envía
 * únicamente { system, content, schema } y este Worker construye la llamada
 * real, de modo que el endpoint no puede usarse como proxy genérico.
 *
 * Despliegue: ver backend/README.md
 */

const ANTHROPIC_MODEL = 'claude-opus-4-8';
const MAX_TOKENS = 16000;
const MAX_BODY_BYTES = 30 * 1024 * 1024; // margen bajo el límite de 32 MB de Anthropic

// Tipos de bloque que el frontend legítimamente envía (plano + instrucciones)
const ALLOWED_BLOCK_TYPES = new Set(['text', 'image', 'document']);

function corsHeaders(env, origin) {
  const configured = (env.ALLOWED_ORIGINS || '*').split(',').map(s => s.trim()).filter(Boolean);
  let allow = '';
  if (configured.includes('*')) allow = '*';
  else if (configured.includes(origin)) allow = origin;
  return {
    'access-control-allow-origin': allow,
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'access-control-max-age': '86400',
    'vary': 'origin',
  };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...headers, 'content-type': 'application/json' },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('origin') || '';
    const headers = corsHeaders(env, origin);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers });
    }

    const url = new URL(request.url);

    /* ---- Compartir proyectos (requiere KV namespace SHARES) ---- */
    if (url.pathname === '/api/share' && request.method === 'POST') {
      return handleShareCreate(request, env, headers);
    }
    const shareMatch = url.pathname.match(/^\/api\/share\/([a-z0-9]{4,20})$/);
    if (shareMatch && request.method === 'GET') {
      return handleShareGet(shareMatch[1], env, headers);
    }

    /* ---- Alertas Valor Futuro (requiere KV SHARES; email opcional con RESEND_API_KEY) ---- */
    if (url.pathname === '/api/alerts' && request.method === 'POST') {
      return handleAlertSubscribe(request, env, headers);
    }

    /* ---- Iris: asistente virtual de BrickBit (chat + búsqueda web) ---- */
    if (url.pathname === '/api/iris' && request.method === 'POST') {
      if (headers['access-control-allow-origin'] === '') {
        return json({ error: { message: 'Origen no permitido.' } }, 403, headers);
      }
      return handleIris(request, env, headers);
    }

    /* ---- Alertas de zona por WhatsApp: disparo manual protegido con clave.
       Útil para probar sin esperar al cron. POST /api/zone-alerts/run?key=… ---- */
    if (url.pathname === '/api/zone-alerts/run' && request.method === 'POST') {
      if (!env.ALERT_TEST_KEY || url.searchParams.get('key') !== env.ALERT_TEST_KEY) {
        return json({ error: { message: 'no_autorizado' } }, 403, headers);
      }
      try {
        const out = await runZoneAlerts(env);
        return json({ ok: true, ...out }, 200, headers);
      } catch (e) {
        return json({ ok: false, error: String(e && e.message || e) }, 500, headers);
      }
    }

    /* ---- API pública: BrickBit Score y pronóstico por zona (para widgets/partners).
       Lectura pública (CORS *), datos derivados de estados.json + forecast.json. ---- */
    /* ---- Contexto macro (IA): titulares recientes → factores del mercado.
       INFORMATIVO: NO entra al modelo de predicción validado. Caché 20 h. ---- */
    if (url.pathname === '/api/macro' && request.method === 'GET') {
      return handleMacro(env, headers);
    }
    if (url.pathname === '/api/score' && (request.method === 'GET' || request.method === 'OPTIONS')) {
      return handlePublicApi('score', request, url, env);
    }
    if (url.pathname === '/api/forecast' && (request.method === 'GET' || request.method === 'OPTIONS')) {
      return handlePublicApi('forecast', request, url, env);
    }

    /* ---- Radar de gentrificación: registra/consulta el historial de vibrancia
       por zona (requiere KV SHARES; si falta, no rompe). ---- */
    if (url.pathname === '/api/vibra-log' && request.method === 'POST') {
      return handleVibraLog(request, env);
    }
    if (url.pathname === '/api/vibra' && (request.method === 'GET' || request.method === 'OPTIONS')) {
      return handleVibraGet(request, url, env);
    }

    /* ---- Datos de DEMANDA: registra qué buscan los usuarios (zona, presupuesto,
       estilo de vida) para construir mapas de calor de demanda. KV SHARES. ---- */
    if (url.pathname === '/api/demand-log' && request.method === 'POST') {
      return handleDemandLog(request, env);
    }
    if (url.pathname === '/api/demand' && (request.method === 'GET' || request.method === 'OPTIONS')) {
      return handleDemandGet(request, url, env);
    }

    /* ---- Búsqueda con IA e inventario (Century 21 + BrickBit) ---- */
    if (url.pathname === '/api/buscar' && request.method === 'POST') {
      return handleBuscar(request, env);
    }
    /* ---- Diagnóstico de la llave de IA. Protegido con INGEST_SECRET porque
       revela la forma del secreto (nunca el secreto). Un 400 con cuerpo VACÍO
       de la API no se puede diagnosticar a ciegas: esta ruta hace la llamada
       más pequeña posible y devuelve exactamente qué contestó. ---- */
    if (url.pathname === '/api/diag' && request.method === 'GET') {
      if (!env.INGEST_SECRET || url.searchParams.get('key') !== env.INGEST_SECRET) {
        return json({ error: 'no_autorizado' }, 403, headers);
      }
      return handleDiag(env, headers);
    }
    if (url.pathname === '/api/listados-ingest' && request.method === 'POST') {
      return handleListadosIngest(request, env);
    }
    if (url.pathname === '/api/listados' && (request.method === 'GET' || request.method === 'OPTIONS')) {
      return handleListadosGet(request, url, env);
    }

    /* ---- Modelos AR temporales (~1h). Scene Viewer (Android) y Quick Look
       (iPhone) no leen blob: URLs; necesitan una URL https real. El gemelo
       sube aquí su GLB/USDZ y model-viewer usa estas URLs. KV SHARES. ---- */
    if (url.pathname === '/api/ar-model' && request.method === 'POST') {
      return handleArModelCreate(request, env);
    }
    const arMatch = url.pathname.match(/^\/api\/ar-model\/([a-z0-9]{4,20})\.(glb|usdz)$/);
    if (arMatch && request.method === 'GET') {
      return handleArModelGet(arMatch[1], arMatch[2], env);
    }

    /* ---- Textura de fachada por IA (Google AI Studio / Gemini). Bajo
       demanda: una imagen por petición. Requiere el secreto GOOGLE_AI_KEY. ---- */
    if (url.pathname === '/api/texture' && request.method === 'POST') {
      return handleTexture(request, env);
    }

    if (url.pathname !== '/api/claude' || request.method !== 'POST') {
      return json({ error: { message: 'No encontrado. Usa GET /api/score?zona=, GET /api/forecast?zona=, POST /api/claude, POST /api/share o GET /api/share/{id}' } }, 404, headers);
    }

    // Si se configuraron orígenes explícitos, rechaza los demás
    if (headers['access-control-allow-origin'] === '' ) {
      return json({ error: { message: 'Origen no permitido. Ajusta ALLOWED_ORIGINS en el Worker.' } }, 403, headers);
    }

    if (!env.ANTHROPIC_API_KEY) {
      return json({ error: { message: 'Falta configurar el secreto ANTHROPIC_API_KEY en el Worker.' } }, 500, headers);
    }

    const len = Number(request.headers.get('content-length') || 0);
    if (len > MAX_BODY_BYTES) {
      return json({ error: { message: 'El plano es demasiado grande. Exporta a menor resolución.' } }, 413, headers);
    }

    let payload;
    try { payload = await request.json(); }
    catch { return json({ error: { message: 'Cuerpo JSON inválido.' } }, 400, headers); }

    const { system, content, schema, webSearch } = payload || {};
    if (typeof system !== 'string' || !Array.isArray(content) || content.length === 0 ||
        typeof schema !== 'object' || schema === null) {
      return json({ error: { message: 'Cuerpo inválido: se esperan { system, content, schema }.' } }, 400, headers);
    }
    if (!content.every(b => b && ALLOWED_BLOCK_TYPES.has(b.type))) {
      return json({ error: { message: 'Tipo de bloque de contenido no permitido.' } }, 400, headers);
    }

    // Petición base; con webSearch se agrega la herramienta de búsqueda del servidor
    const base = {
      model: ANTHROPIC_MODEL,
      max_tokens: MAX_TOKENS,
      thinking: { type: 'adaptive' },
      system,
      output_config: { format: { type: 'json_schema', schema } },
    };
    if (webSearch === true) base.tools = [{ type: 'web_search_20260209', name: 'web_search', max_uses: 6 }];

    // Con herramientas de servidor la API puede pausar el turno (pause_turn):
    // se reenvía la conversación para que continúe donde se quedó.
    let messages = [{ role: 'user', content }];
    let bodyText = '', status = 500;
    for (let i = 0; i < 4; i++) {
      const upstream = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({ ...base, messages }),
      });
      status = upstream.status;
      bodyText = await upstream.text();
      if (!upstream.ok) break;
      let data;
      try { data = JSON.parse(bodyText); } catch { break; }
      if (data.stop_reason === 'pause_turn') {
        messages = [...messages, { role: 'assistant', content: data.content }];
        continue;
      }
      break;
    }

    return new Response(bodyText, {
      status,
      headers: { ...headers, 'content-type': 'application/json' },
    });
  },

  /* Cron mensual (ver [triggers] en wrangler.toml): envía el informe de zona
     por correo a los suscriptores. Requiere KV SHARES + RESEND_API_KEY. */
  async scheduled(event, env, ctx) {
    // El informe mensual sólo en su horario (día 1); las alertas de zona en cada disparo.
    if (event.cron === '0 14 1 * *') ctx.waitUntil(runMonthlyAlerts(env));
    ctx.waitUntil(runZoneAlerts(env).catch(e => console.error('[zone-alerts]', e && e.message)));
  },
};


/* =====================================================================
   Iris — asistente virtual de BrickBit
   Chat en texto libre con conocimiento del producto + búsqueda web
   acotada (max_uses por consulta = tope de costo). La llave de Anthropic
   vive en el Worker; el navegador solo manda { messages }.
===================================================================== */
const IRIS_SYSTEM =
`Eres **Iris**, la asistente virtual de BrickBit — una proptech mexicana de inteligencia inmobiliaria. Hablas en español de México, con calidez, claridad y brevedad (respuestas para leer o escuchar en voz alta: ve al grano, 2–5 frases salvo que pidan detalle).

QUÉ ES BRICKBIT y sus herramientas (guía al usuario a la correcta):
- Mapa interactivo: precio, plusvalía y ciclo de las 32 zonas.
- Analizador de inversión: pro-forma completa (TIR, ROI, cap rate), escenarios, comparador de zonas y "Economía de la zona" con datos reales del DENUE.
- Simulador 3D de desarrollo (zona3d): dibuja el volumen COS/CUS sobre la ciudad y ve inversión/ventas/utilidad.
- Pulso de México: las 32 ciudades como torres 3D con serie SHF 2005–2026 y proyección.
- Cinema y Versus: recorrido y duelo de ciudades.
- Arquitectos con IA: Creador de Planos (texto→plano), Gemelo Digital 3D (materiales, fallas, simulador 4D, inversión) y Comparador.
- Motor de Morfogénesis Urbana: México como organismo vivo; 6.1M negocios del DENUE/INEGI; contagio de plusvalía a 5 escalas (estados, 2,436 municipios, códigos postales de CDMX, calle/establecimiento en 83 ciudades, y microtejido/ZMVM).
- BrickBit Financial: seguros GNP y asesoría financiera con José Delgado (NO es parte de tu alcance; si preguntan de seguros o finanzas personales, remítelos amablemente al módulo Financial).

PRINCIPIO DE HONESTIDAD DE DATOS: los conteos de negocios, empleo, geometrías y la serie SHF son reales (DENUE/INEGI, SHF, SEPOMEX). Las proyecciones a futuro son SIMULACIONES para visualización, no asesoría de inversión. Dilo cuando aplique. Nunca presentes una estimación como hecho.

REGLAS:
- Si te preguntan datos actuales o externos (noticias, tasas, precios de mercado, un desarrollo específico), USA la búsqueda web y cita brevemente la fuente.
- No des asesoría financiera, legal ni fiscal definitiva; orienta y sugiere confirmar con un profesional o con el equipo de BrickBit.
- Si no sabes algo, dilo con honestidad. No inventes cifras.
- Ayuda a la gente a entender qué está viendo y a llegar a la herramienta correcta.`;

async function handleIris(request, env, headers) {
  if (!env.ANTHROPIC_API_KEY) {
    return json({ error: { message: 'Falta configurar ANTHROPIC_API_KEY en el Worker.' } }, 500, headers);
  }
  let payload;
  try { payload = await request.json(); }
  catch { return json({ error: { message: 'Cuerpo JSON inválido.' } }, 400, headers); }

  const raw = Array.isArray(payload && payload.messages) ? payload.messages : null;
  if (!raw || !raw.length) {
    return json({ error: { message: 'Se esperan { messages: [{role, content}] }.' } }, 400, headers);
  }
  // Sanea: solo texto de user/assistant, últimos 12 turnos, cada uno acotado.
  const messages = raw
    .filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .slice(-12)
    .map(m => ({ role: m.role, content: m.content.slice(0, 4000) }));
  if (!messages.length || messages[messages.length - 1].role !== 'user') {
    return json({ error: { message: 'La última entrada debe ser del usuario.' } }, 400, headers);
  }

  const base = {
    model: ANTHROPIC_MODEL,
    max_tokens: 1200,
    system: IRIS_SYSTEM,
    // Búsqueda web acotada: máx. 3 búsquedas por consulta = tope de costo.
    tools: [{ type: 'web_search_20260209', name: 'web_search', max_uses: 3 }],
  };

  let convo = messages, bodyText = '', status = 500, data = null;
  for (let i = 0; i < 4; i++) {
    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({ ...base, messages: convo }),
    });
    status = upstream.status;
    bodyText = await upstream.text();
    if (!upstream.ok) {
      return json({ error: { message: 'Iris no está disponible en este momento.' } }, status, headers);
    }
    try { data = JSON.parse(bodyText); } catch { break; }
    if (data.stop_reason === 'pause_turn') {
      convo = [...convo, { role: 'assistant', content: data.content }];
      continue;
    }
    break;
  }

  const text = (data && Array.isArray(data.content) ? data.content : [])
    .filter(b => b && b.type === 'text').map(b => b.text).join('').trim();
  return json({ text: text || 'Perdona, no pude generar una respuesta. ¿Puedes reformular tu pregunta?' }, 200, headers);
}


/* =====================================================================
   Compartir proyectos — enlaces cortos con Cloudflare KV
   Configuración: npx wrangler kv namespace create SHARES
   y agrega el binding en wrangler.toml (ver backend/README.md)
===================================================================== */
const SHARE_TTL_SECONDS = 60 * 60 * 24 * 90; // 90 días
const SHARE_MAX_BYTES = 300 * 1024;

async function handleShareCreate(request, env, headers) {
  if (!env.SHARES) {
    return json({ error: { message: 'El backend no tiene configurado el almacén de enlaces (KV namespace SHARES). Ver backend/README.md.' } }, 501, headers);
  }
  const body = await request.text();
  if (body.length > SHARE_MAX_BYTES) {
    return json({ error: { message: 'El proyecto es demasiado grande para compartir.' } }, 413, headers);
  }
  let data;
  try { data = JSON.parse(body); } catch { data = null; }
  // Acepta proyectos del gemelo (geometry+engineering) y páginas de preventa.
  const esGemelo = data && data.geometry && data.engineering;
  const esPreventa = data && data.tipo === 'preventa' && data.proyecto;
  if (!data || typeof data !== 'object' || (!esGemelo && !esPreventa)) {
    return json({ error: { message: 'Proyecto inválido: se esperan geometry y engineering, o un payload de preventa.' } }, 400, headers);
  }
  const alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const id = [...crypto.getRandomValues(new Uint8Array(8))].map(b => alphabet[b % 36]).join('');
  await env.SHARES.put(id, body, { expirationTtl: SHARE_TTL_SECONDS });
  return json({ id, expiresInDays: 90 }, 200, headers);
}

async function handleShareGet(id, env, headers) {
  if (!env.SHARES) {
    return json({ error: { message: 'El backend no tiene configurado el almacén de enlaces (KV namespace SHARES).' } }, 501, headers);
  }
  const value = await env.SHARES.get(id);
  if (!value) {
    return json({ error: { message: 'Enlace no encontrado o expirado (los enlaces duran 90 días).' } }, 404, headers);
  }
  return new Response(value, { status: 200, headers: { ...headers, 'content-type': 'application/json' } });
}


/* =====================================================================
   Alertas Valor Futuro — suscripción + envío mensual por correo
   Requiere: KV SHARES (mismo del share) y, para el envío,
   el secreto RESEND_API_KEY (resend.com) y opcionalmente ALERTS_FROM.
===================================================================== */
async function handleAlertSubscribe(request, env, headers) {
  if (!env.SHARES) {
    return json({ error: { message: 'El backend no tiene KV configurado (namespace SHARES). Ver backend/README.md.' } }, 501, headers);
  }
  let data;
  try { data = await request.json(); } catch { data = null; }
  const email = data && String(data.email || '').trim();
  const zona = data && String(data.zona || '').trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || !zona || zona.length > 60) {
    return json({ error: { message: 'Se esperan { email, zona } válidos.' } }, 400, headers);
  }
  // clave determinista → suscribirse dos veces no duplica
  const keyBase = (zona + '|' + email).toLowerCase();
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(keyBase));
  const id = [...new Uint8Array(digest)].slice(0, 10).map(b => b.toString(16).padStart(2, '0')).join('');
  await env.SHARES.put('alert:' + id, JSON.stringify({ email, zona, creada: new Date().toISOString() }));
  return json({ ok: true, zona }, 200, headers);
}

async function runMonthlyAlerts(env) {
  if (!env.SHARES || !env.ANTHROPIC_API_KEY || !env.RESEND_API_KEY) return;
  // agrupar suscriptores por zona
  const byZone = {};
  let cursor;
  do {
    const page = await env.SHARES.list({ prefix: 'alert:', cursor });
    for (const k of page.keys) {
      const v = await env.SHARES.get(k.name);
      if (!v) continue;
      try {
        const a = JSON.parse(v);
        (byZone[a.zona] = byZone[a.zona] || []).push(a.email);
      } catch {}
    }
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor);

  for (const [zona, emails] of Object.entries(byZone)) {
    try {
      const informe = await zoneReportText(env, zona);
      await sendAlertEmail(env, emails, zona, informe);
    } catch (err) {
      console.error('[alertas]', zona, err && err.message);
    }
  }
}

async function zoneReportText(env, zona) {
  let messages = [{
    role: 'user',
    content: [{ type: 'text', text:
      'Busca noticias recientes relevantes para el valor inmobiliario de ' + zona +
      ', México (obra pública, desarrollos, uso de suelo, economía local) y redacta un informe breve en español, en HTML simple (párrafos y listas <ul>), de máximo 300 palabras, terminando con el efecto esperado en la plusvalía.' }],
  }];
  let data;
  for (let i = 0; i < 4; i++) {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: 4000,
        thinking: { type: 'adaptive' },
        tools: [{ type: 'web_search_20260209', name: 'web_search', max_uses: 5 }],
        messages,
      }),
    });
    if (!res.ok) throw new Error('Anthropic ' + res.status);
    data = await res.json();
    if (data.stop_reason === 'pause_turn') {
      messages = [...messages, { role: 'assistant', content: data.content }];
      continue;
    }
    break;
  }
  const texts = (data.content || []).filter(b => b.type === 'text');
  return texts.length ? texts[texts.length - 1].text : 'Sin novedades relevantes este mes.';
}

async function sendAlertEmail(env, emails, zona, informeHtml) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'authorization': 'Bearer ' + env.RESEND_API_KEY,
    },
    body: JSON.stringify({
      from: env.ALERTS_FROM || 'BrickBit <onboarding@resend.dev>',
      to: [emails[0]],
      bcc: emails.slice(1),
      subject: '🏗️ BrickBit Valor Futuro — informe mensual de ' + zona,
      html: '<div style="font-family:Georgia,serif;max-width:560px;margin:auto;color:#22201d">' +
            '<h2 style="color:#1a7d50">■ BrickBit · Valor Futuro</h2>' +
            '<h3>' + zona + ' — ' + new Date().toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }) + '</h3>' +
            informeHtml +
            '<hr><p style="font-size:12px;color:#888">Informe generado con IA y búsqueda web. No es asesoría de inversión. ' +
            'Para dejar de recibirlo, responde a este correo.</p></div>',
    }),
  });
  if (!res.ok) throw new Error('Resend ' + res.status + ': ' + (await res.text()).slice(0, 200));
}


/* =====================================================================
   Alertas de zona por WhatsApp (MVP: te avisan a TI, José)
   ---------------------------------------------------------------------
   Lee la tabla `zone_alerts` de Supabase (con la service key, saltando RLS),
   compara la apreciación proyectada de cada zona vigilada contra la línea base
   guardada (`ultimo_valor`) y, si el pronóstico se movió más que el umbral del
   usuario, te manda UN WhatsApp (vía Twilio) con el resumen de los cambios.

   Secretos requeridos en el Worker (si falta alguno, la función no hace nada):
     SUPABASE_URL           p.ej. https://xxxx.supabase.co
     SUPABASE_SERVICE_KEY   service_role key (NUNCA en el navegador)
     TWILIO_ACCOUNT_SID
     TWILIO_AUTH_TOKEN
     TWILIO_WHATSAPP_FROM   p.ej. whatsapp:+14155238886 (sandbox) o tu número
     ALERT_WHATSAPP_TO      tu número, p.ej. whatsapp:+5215584681927
   Opcional:
     SITE_URL               de dónde leer forecast.json (def. https://brickbit.co)
     ALERT_TEST_KEY         clave para el disparo manual POST /api/zone-alerts/run
===================================================================== */
async function runZoneAlerts(env) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) return { skipped: 'falta_supabase' };
  if (!env.TWILIO_ACCOUNT_SID || !env.TWILIO_AUTH_TOKEN || !env.TWILIO_WHATSAPP_FROM || !env.ALERT_WHATSAPP_TO) {
    return { skipped: 'falta_twilio' };
  }

  // 1) alertas activas
  const rows = await sbSelect(env,
    'zone_alerts',
    '?activa=eq.true&select=id,user_id,zona,horizonte,umbral_pct,ultimo_valor');
  if (!rows || !rows.length) return { revisadas: 0, cambios: [] };

  // 2) pronóstico actual (multiplicadores por zona/horizonte)
  const site = (env.SITE_URL || 'https://brickbit.co').replace(/\/+$/, '');
  const fRes = await fetch(site + '/data/forecast.json', { cf: { cacheTtl: 0 } });
  if (!fRes.ok) throw new Error('forecast.json ' + fRes.status);
  const forecast = await fRes.json();

  const cambios = [];
  for (const a of rows) {
    const zf = forecast[a.zona];
    const c = zf && zf[String(a.horizonte)];
    if (!c || typeof c.f !== 'number') continue;

    // apreciación proyectada, en %, para comparar contra el umbral (en puntos)
    const apprNueva = Math.round((c.f - 1) * 1000) / 10;
    const prev = a.ultimo_valor;

    // primera vez: sólo fijamos la línea base, sin notificar
    if (prev === null || prev === undefined) {
      await sbUpdate(env, 'zone_alerts', a.id, { ultimo_valor: apprNueva });
      continue;
    }
    const delta = Math.abs(apprNueva - Number(prev));
    if (delta >= Number(a.umbral_pct)) {
      cambios.push({ zona: a.zona, horizonte: a.horizonte, antes: Number(prev), ahora: apprNueva, delta: Math.round(delta * 10) / 10 });
      await sbUpdate(env, 'zone_alerts', a.id, { ultimo_valor: apprNueva, notificado_en: new Date().toISOString() });
    }
  }

  if (cambios.length) {
    // dedup de líneas por zona+horizonte (varios usuarios pueden vigilar lo mismo)
    const vistos = new Set();
    const lineas = [];
    for (const c of cambios) {
      const k = c.zona + '|' + c.horizonte;
      if (vistos.has(k)) continue;
      vistos.add(k);
      const sa = (c.antes >= 0 ? '+' : '') + c.antes, sn = (c.ahora >= 0 ? '+' : '') + c.ahora;
      lineas.push(`• ${c.zona} (${c.horizonte}a): ${sa}% → ${sn}% (Δ ${c.delta} pts)`);
    }
    const cuerpo =
      '🏗️ BrickBit · Alertas de pronóstico\n' +
      lineas.length + ' zona(s) vigilada(s) por tus usuarios cambiaron más que su umbral:\n\n' +
      lineas.join('\n') +
      '\n\nEntra a "Mi BrickBit" para ver el detalle.';
    await sendWhatsAppTwilio(env, env.ALERT_WHATSAPP_TO, cuerpo);
  }

  return { revisadas: rows.length, cambios };
}

/* --- Supabase REST con service key (salta RLS: úsala SOLO en el servidor) --- */
async function sbSelect(env, table, query) {
  const r = await fetch(env.SUPABASE_URL.replace(/\/+$/, '') + '/rest/v1/' + table + query, {
    headers: { apikey: env.SUPABASE_SERVICE_KEY, authorization: 'Bearer ' + env.SUPABASE_SERVICE_KEY },
  });
  if (!r.ok) throw new Error('Supabase select ' + r.status + ': ' + (await r.text()).slice(0, 200));
  return r.json();
}
async function sbUpdate(env, table, id, patch) {
  const r = await fetch(env.SUPABASE_URL.replace(/\/+$/, '') + '/rest/v1/' + table + '?id=eq.' + encodeURIComponent(id), {
    method: 'PATCH',
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY, authorization: 'Bearer ' + env.SUPABASE_SERVICE_KEY,
      'content-type': 'application/json', prefer: 'return=minimal',
    },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error('Supabase update ' + r.status + ': ' + (await r.text()).slice(0, 200));
}

/* =====================================================================
   API pública: BrickBit Score y pronóstico por zona
   ---------------------------------------------------------------------
   Datos derivados de estados.json + forecast.json del sitio. Pensado para
   incrustar en fichas de propiedad de terceros (widgets) o consumir como API.
   El Score replica el índice del mapa (Valor Futuro, rendimiento, riesgo,
   liquidez, oportunidad) normalizado entre las 32 zonas.
===================================================================== */
let _bbData = null; // caché best-effort dentro del isolate
async function loadBBData(env) {
  if (_bbData) return _bbData;
  const site = (env.SITE_URL || 'https://brickbit.co').replace(/\/+$/, '');
  const [er, fr] = await Promise.all([
    fetch(site + '/data/estados.json', { cf: { cacheTtl: 3600 } }),
    fetch(site + '/data/forecast.json', { cf: { cacheTtl: 3600 } }),
  ]);
  if (!er.ok || !fr.ok) throw new Error('No se pudieron leer los datos del sitio.');
  const ej = await er.json(), fj = await fr.json();
  _bbData = { estados: (ej.estados || ej), forecast: fj };
  return _bbData;
}
function _pubInputs(e, forecast) {
  const fc = forecast[e.nombre] && forecast[e.nombre]['3'];
  const appr = fc ? (fc.f - 1) * 100 : (Math.pow(1 + (e.plusvalia || 0) / 100, 3) - 1) * 100;
  return { appr, yld: (+e['yield'] || 0), vol: (e.volatilidad_anual != null ? e.volatilidad_anual : 4.0),
           dom: (+e.dom || 60), opp: (e.oportunidad === 'Alta' ? 3 : e.oportunidad === 'Media' ? 2 : 1) };
}
function _pubScore(inputs) {
  const rng = k => { const v = inputs.map(o => o.x[k]); return [Math.min(...v), Math.max(...v)]; };
  const R = { appr: rng('appr'), yld: rng('yld'), vol: rng('vol'), dom: rng('dom'), opp: rng('opp') };
  const nrm = (v, r, inv) => { const mn = r[0], mx = r[1]; if (mx === mn) return 50; let t = (v - mn) / (mx - mn); if (inv) t = 1 - t; return Math.max(0, Math.min(1, t)) * 100; };
  return x => {
    const parts = [
      ['Valor Futuro', nrm(x.appr, R.appr, false), .35],
      ['Rendimiento', nrm(x.yld, R.yld, false), .20],
      ['Riesgo bajo', nrm(x.vol, R.vol, true), .20],
      ['Liquidez', nrm(x.dom, R.dom, true), .10],
      ['Oportunidad', nrm(x.opp, R.opp, false), .15],
    ];
    const total = Math.round(parts.reduce((a, p) => a + p[1] * p[2], 0));
    const grade = total >= 80 ? 'A' : total >= 65 ? 'B' : total >= 50 ? 'C' : 'D';
    return { total, grade, parts: parts.map(p => ({ k: p[0], s: Math.round(p[1]) })) };
  };
}
async function handlePublicApi(kind, request, url, env) {
  const headers = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, OPTIONS',
                    'access-control-allow-headers': 'content-type', 'cache-control': 'public, max-age=600',
                    'content-type': 'application/json' };
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
  try {
    const zona = (url.searchParams.get('zona') || '').trim();
    const { estados, forecast } = await loadBBData(env);
    if (kind === 'forecast') {
      if (!zona) return new Response(JSON.stringify({ zonas: Object.keys(forecast) }), { headers });
      const f = forecast[zona] || forecast[Object.keys(forecast).find(k => k.toLowerCase() === zona.toLowerCase())];
      if (!f) return new Response(JSON.stringify({ error: 'zona_no_encontrada' }), { status: 404, headers });
      return new Response(JSON.stringify({ zona, forecast: f }), { headers });
    }
    const inputs = estados.map(e => ({ e, x: _pubInputs(e, forecast) }));
    const calc = _pubScore(inputs);
    if (!zona) {
      const all = inputs.map(o => ({ zona: o.e.nombre, ...calc(o.x) })).sort((a, b) => b.total - a.total);
      return new Response(JSON.stringify({ zonas: all }), { headers });
    }
    const o = inputs.find(o => o.e.nombre === zona || o.e.nombre.toLowerCase() === zona.toLowerCase());
    if (!o) return new Response(JSON.stringify({ error: 'zona_no_encontrada' }), { status: 404, headers });
    const sc = calc(o.x);
    return new Response(JSON.stringify({
      zona: o.e.nombre, score: sc.total, grade: sc.grade, parts: sc.parts,
      precio_m2: o.e.precio_m2, plusvalia: o.e.plusvalia, yield: o.e['yield'], valorFuturo3a: Math.round(o.x.appr),
    }), { headers });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err && err.message || err) }), { status: 500, headers });
  }
}

/* =====================================================================
   Radar de gentrificación en el tiempo
   Guarda una lectura de vibrancia por zona y día en KV (SHARES) y devuelve el
   historial, para graficar la tendencia. Empieza a acumular en cuanto la gente
   usa el escaneo de vibrancia; la curva aparece cuando hay ≥2 lecturas.
===================================================================== */
async function handleVibraLog(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  if (!env.SHARES) return new Response(JSON.stringify({ ok: false, error: 'sin_kv' }), { status: 200, headers });
  let d; try { d = await request.json(); } catch { return new Response(JSON.stringify({ ok: false }), { status: 400, headers }); }
  const zona = String(d && d.zona || '').slice(0, 80);
  const score = Math.round(Number(d && d.score));
  if (!zona || !isFinite(score)) return new Response(JSON.stringify({ ok: false }), { status: 400, headers });
  const key = 'vibra:' + zona.toLowerCase();
  let arr = [];
  try { const v = await env.SHARES.get(key); if (v) arr = JSON.parse(v); } catch {}
  const today = new Date().toISOString().slice(0, 10);
  const last = arr[arr.length - 1];
  if (last && last.d === today) last.s = score;      // una lectura por día por zona
  else arr.push({ d: today, s: score });
  arr = arr.slice(-60);
  await env.SHARES.put(key, JSON.stringify(arr));
  return new Response(JSON.stringify({ ok: true, n: arr.length }), { headers });
}
async function handleVibraGet(request, url, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json', 'cache-control': 'public, max-age=300' };
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
  const zona = (url.searchParams.get('zona') || '').trim();
  if (!env.SHARES || !zona) return new Response(JSON.stringify({ historial: [] }), { headers });
  let arr = [];
  try { const v = await env.SHARES.get('vibra:' + zona.toLowerCase()); if (v) arr = JSON.parse(v); } catch {}
  return new Response(JSON.stringify({ zona, historial: arr }), { headers });
}

/* =====================================================================
   Datos de DEMANDA — el moat que un bróker con inventario no tiene
   Agrega, de forma anónima, qué zonas/presupuestos/estilos de vida buscan los
   usuarios en las herramientas. Con esto se arman "mapas de calor de demanda"
   para desarrolladores. KV SHARES; si falta, no rompe.
===================================================================== */
const DEMAND_KEY = 'demand:agg';
async function handleDemandLog(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  if (!env.SHARES) return new Response(JSON.stringify({ ok: false, error: 'sin_kv' }), { status: 200, headers });
  let d; try { d = await request.json(); } catch { return new Response(JSON.stringify({ ok: false }), { status: 400, headers }); }
  const evento = String(d && d.evento || '').slice(0, 24);
  const zona = String(d && d.zona || '').slice(0, 80);
  if (!evento) return new Response(JSON.stringify({ ok: false }), { status: 400, headers });
  let agg = {};
  try { const v = await env.SHARES.get(DEMAND_KEY); if (v) agg = JSON.parse(v); } catch {}
  agg.zonas = agg.zonas || {}; agg.presupuestos = agg.presupuestos || {}; agg.estilos = agg.estilos || {}; agg.tipos = agg.tipos || {};
  agg.total = (agg.total || 0) + 1;
  if (zona) { const z = agg.zonas[zona] = agg.zonas[zona] || { n: 0, ev: {} }; z.n++; z.ev[evento] = (z.ev[evento] || 0) + 1; }
  const meta = (d && d.meta) || {};
  if (meta.presupuesto) { const k = String(meta.presupuesto).slice(0, 40); agg.presupuestos[k] = (agg.presupuestos[k] || 0) + 1; }
  if (meta.tipo) { const k = String(meta.tipo).slice(0, 24); agg.tipos[k] = (agg.tipos[k] || 0) + 1; }
  if (Array.isArray(meta.estilos)) meta.estilos.slice(0, 10).forEach(c => { const k = String(c).slice(0, 24); agg.estilos[k] = (agg.estilos[k] || 0) + 1; });
  agg.actualizado = new Date().toISOString();
  await env.SHARES.put(DEMAND_KEY, JSON.stringify(agg));
  return new Response(JSON.stringify({ ok: true }), { headers });
}
async function handleDemandGet(request, url, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json', 'cache-control': 'public, max-age=300' };
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
  if (!env.SHARES) return new Response(JSON.stringify({ zonas: {}, total: 0 }), { headers });
  let agg = {};
  try { const v = await env.SHARES.get(DEMAND_KEY); if (v) agg = JSON.parse(v); } catch {}
  // ranking de zonas por demanda
  const ranking = Object.entries(agg.zonas || {}).map(([z, o]) => ({ zona: z, n: o.n, eventos: o.ev }))
    .sort((a, b) => b.n - a.n).slice(0, 100);
  return new Response(JSON.stringify({ total: agg.total || 0, actualizado: agg.actualizado || null, ranking,
    presupuestos: agg.presupuestos || {}, estilos: agg.estilos || {}, tipos: agg.tipos || {} }), { headers });
}

/* --- Modelos AR temporales (GLB/USDZ) --- */
const AR_TTL_SECONDS = 3600;      // 1 hora: suficiente para la sesión de AR
const AR_MAX_B64 = 15_000_000;    // ~11 MB binarios por archivo

async function handleArModelCreate(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  if (!env.SHARES) {
    return new Response(JSON.stringify({ error: 'El backend no tiene el KV SHARES configurado.' }), { status: 501, headers });
  }
  let data;
  try { data = await request.json(); } catch { data = null; }
  if (!data || typeof data.glb !== 'string' || !data.glb) {
    return new Response(JSON.stringify({ error: 'Falta el modelo glb (base64).' }), { status: 400, headers });
  }
  if (data.glb.length > AR_MAX_B64 || (typeof data.usdz === 'string' && data.usdz.length > AR_MAX_B64)) {
    return new Response(JSON.stringify({ error: 'Modelo demasiado grande.' }), { status: 413, headers });
  }
  const alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const id = [...crypto.getRandomValues(new Uint8Array(8))].map(b => alphabet[b % 36]).join('');
  await env.SHARES.put('ar:' + id + ':glb', data.glb, { expirationTtl: AR_TTL_SECONDS });
  const hayUsdz = typeof data.usdz === 'string' && data.usdz.length > 0;
  if (hayUsdz) await env.SHARES.put('ar:' + id + ':usdz', data.usdz, { expirationTtl: AR_TTL_SECONDS });
  const base = new URL(request.url).origin;
  return new Response(JSON.stringify({
    id,
    glb: base + '/api/ar-model/' + id + '.glb',
    usdz: hayUsdz ? base + '/api/ar-model/' + id + '.usdz' : null,
    expiraEnMin: Math.round(AR_TTL_SECONDS / 60),
  }), { status: 200, headers });
}

async function handleArModelGet(id, fmt, env) {
  const cors = { 'access-control-allow-origin': '*' };
  if (!env.SHARES) return new Response('sin KV', { status: 501, headers: cors });
  const b64 = await env.SHARES.get('ar:' + id + ':' + fmt);
  if (!b64) return new Response('Modelo no encontrado o expirado (duran 1 hora).', { status: 404, headers: cors });
  const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Response(bin, {
    status: 200,
    headers: {
      ...cors,
      'content-type': fmt === 'glb' ? 'model/gltf-binary' : 'model/vnd.usdz+zip',
      'cache-control': 'public, max-age=3600',
    },
  });
}

/* --- Textura de fachada por IA (Gemini de Google AI Studio) --- */
const TEX_ESTILOS = {
  contemporaneo: 'fachada residencial contemporánea de concreto aparente y grandes paños de vidrio',
  ladrillo: 'muro de ladrillo rojo aparente estilo industrial, con juntas de mortero',
  colonial: 'fachada colonial mexicana con aplanado texturizado, molduras y cantera',
  minimalista: 'fachada minimalista blanca, superficie lisa y limpia, mínimas juntas',
  madera: 'revestimiento de listones de madera natural en tono cálido',
};
async function handleTexture(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  if (!env.GOOGLE_AI_KEY) {
    return new Response(JSON.stringify({ error: 'El backend no tiene GOOGLE_AI_KEY configurada. Ver backend/README.md.' }), { status: 501, headers });
  }
  let body; try { body = await request.json(); } catch { body = {}; }
  const estilo = String(body.estilo || 'contemporaneo').toLowerCase();
  const desc = TEX_ESTILOS[estilo] || TEX_ESTILOS.contemporaneo;
  const prompt = `Textura de material arquitectónico SIN COSTURAS (seamless, tileable) para mapear sobre una pared 3D: ${desc}. Vista frontal completamente plana (elevación ortográfica), sin perspectiva, sin cielo ni suelo ni entorno, sin sombras marcadas, iluminación uniforme y difusa, patrón que se repite en mosaico sin bordes visibles, alta resolución, cuadrada.`;
  // gemini-2.5-flash-image exige declarar responseModalities (sin eso: 400).
  // Si el modelo estable no está disponible para la llave, se reintenta el -preview.
  const payload = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ['TEXT', 'IMAGE'] },
  });
  const MODELOS = ['gemini-2.5-flash-image', 'gemini-2.5-flash-image-preview'];
  let r = null, lastErr = '';
  for (const modelo of MODELOS) {
    try {
      r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-goog-api-key': env.GOOGLE_AI_KEY },
        body: payload,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: 'No se pudo contactar a Google: ' + e.message }), { status: 502, headers });
    }
    if (r.ok) break;
    lastErr = await r.text().catch(() => '');
    if (r.status !== 400 && r.status !== 404) break; // otros errores: no reintentar
  }
  if (!r || !r.ok) {
    let msg = '';
    try { msg = (JSON.parse(lastErr).error || {}).message || ''; } catch { msg = lastErr.slice(0, 200); }
    return new Response(JSON.stringify({ error: 'Google respondió ' + (r ? r.status : '?') + (msg ? ': ' + msg : '') + '. Revisa que la llave tenga habilitada la Generative Language API y facturación activa.', detalle: lastErr.slice(0, 300) }), { status: 502, headers });
  }
  let data; try { data = await r.json(); } catch { data = null; }
  const parts = (((data || {}).candidates || [])[0] || {}).content?.parts || [];
  const img = parts.find((p) => p.inlineData || p.inline_data);
  const inline = img && (img.inlineData || img.inline_data);
  if (!inline || !inline.data) {
    return new Response(JSON.stringify({ error: 'La respuesta de Google no incluyó una imagen.' }), { status: 502, headers });
  }
  const mime = inline.mimeType || inline.mime_type || 'image/png';
  return new Response(JSON.stringify({ image: `data:${mime};base64,${inline.data}`, estilo }), { status: 200, headers });
}

/* --- Búsqueda con IA sobre el inventario (Century 21 + inteligencia BrickBit) --- */
function slugZona(nombre) {
  return String(nombre || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
// Pide JSON directo (sin gramática/output_config, que puede tardar en compilar).
// Opus devuelve JSON limpio con la instrucción; se limpian fences por si acaso.
/* Contexto macro: lee titulares (Google News RSS, consultas fijas de economía e
   inmobiliario MX) y Claude los sintetiza en factores. Se cachea 20 h en KV.
   Es CONTEXTO CUALITATIVO — el modelo de precios validado no lo consume. */
async function handleMacro(env, headers) {
  const h = { ...headers, 'content-type': 'application/json' };
  try {
    if (env.SHARES) {
      const c = await env.SHARES.get('macro:brief');
      if (c) { const j = JSON.parse(c); if (Date.now() - (j._ts || 0) < 20 * 3600e3) return new Response(c, { headers: h }); }
    }
    const feeds = [
      'https://news.google.com/rss/search?q=Banxico+OR+%22tasa+de+inter%C3%A9s%22+OR+inflaci%C3%B3n+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
      'https://news.google.com/rss/search?q=%22sector+inmobiliario%22+OR+vivienda+OR+hipotecario+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    ];
    const titulares = [];
    for (const f of feeds) {
      try {
        const xml = await (await fetch(f, { headers: { 'user-agent': 'BrickBit/1.0' } })).text();
        const m = [...xml.matchAll(/<title>(?:<!\[CDATA\[)?([^<\]]{15,160})/g)].map((x) => x[1]);
        titulares.push(...m.slice(1, 11)); // el primer <title> es el del feed
      } catch (e) {}
    }
    if (titulares.length < 4) return json({ error: 'sin titulares' }, 502, h);
    const out = await askClaudeJSON(env,
      'Eres un analista macro del mercado inmobiliario mexicano. Con base SOLO en los titulares dados, responde JSON: {"resumen": "2 frases", "factores": [{"factor": "...", "efecto": "favorable|neutral|riesgo", "explicacion": "1 frase sobre su efecto en vivienda/tasas"}]} con 3 a 5 factores. Sé sobrio: son titulares, no datos verificados.',
      'Titulares recientes:\n- ' + titulares.join('\n- '));
    const brief = { ...out, fecha: new Date().toISOString().slice(0, 10), n: titulares.length, _ts: Date.now() };
    if (env.SHARES) await env.SHARES.put('macro:brief', JSON.stringify(brief));
    return json(brief, 200, h);
  } catch (e) {
    return json({ error: 'macro no disponible: ' + e.message }, 500, h);
  }
}

async function askClaudeJSON(env, system, userText) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model: ANTHROPIC_MODEL, max_tokens: 800, system, messages: [{ role: 'user', content: userText }] }),
  });
  // Leer el cuerpo como TEXTO primero: si la respuesta no es el JSON que
  // esperamos (un error de la pasarela, un cuerpo vacío, HTML), r.json()
  // reventaba y el mensaje quedaba en "IA 400:" — un error mudo, imposible de
  // diagnosticar. Con el texto crudo siempre se ve QUÉ contestó la API.
  const crudo = await r.text();
  let data = {};
  try { data = JSON.parse(crudo); } catch { /* no era JSON: queda el crudo */ }
  if (!r.ok) {
    const detalle = (data.error && data.error.message)
      || (crudo || '').trim().slice(0, 300)
      || 'sin cuerpo en la respuesta';
    throw new Error('IA ' + r.status + ': ' + detalle);
  }
  let txt = (data.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('').trim();
  txt = txt.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
  const a = txt.indexOf('{'), b = txt.lastIndexOf('}');
  if (a >= 0 && b > a) txt = txt.slice(a, b + 1);
  return JSON.parse(txt);
}
/* --- Diagnóstico: aísla si el problema es la llave, el modelo o el payload --- */
async function handleDiag(env, headers) {
  const k = env.ANTHROPIC_API_KEY || '';
  // Forma del secreto, NUNCA el secreto. Espacios o saltos de línea pegados por
  // accidente son una causa clásica de peticiones malformadas.
  const llave = {
    presente: !!k,
    longitud: k.length,
    empieza_con: k.slice(0, 7),
    termina_con: k.slice(-4),
    tiene_espacios_alrededor: k !== k.trim(),
    tiene_salto_de_linea: /[\r\n]/.test(k),
    tiene_no_ascii: /[^\x20-\x7E]/.test(k),
  };

  const probar = async (etiqueta, cuerpo) => {
    try {
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': k.trim(),
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(cuerpo),
      });
      const texto = await r.text();
      return {
        prueba: etiqueta, status: r.status,
        request_id: r.headers.get('request-id') || null,
        cuerpo: texto ? texto.slice(0, 400) : '(vacío)',
      };
    } catch (e) {
      return { prueba: etiqueta, error: String(e && e.message || e) };
    }
  };

  const minima = { model: ANTHROPIC_MODEL, max_tokens: 16,
                   messages: [{ role: 'user', content: 'ping' }] };
  return json({
    modelo_configurado: ANTHROPIC_MODEL,
    llave,
    kv_shares: !!env.SHARES,
    pruebas: [
      await probar('mínima', minima),
      // Mismo cuerpo con un modelo distinto: si esta pasa y la de arriba no,
      // el problema es el acceso a ese modelo, no la llave.
      await probar('modelo alterno', { ...minima, model: 'claude-sonnet-4-5' }),
    ],
  }, 200, headers);
}

async function handleBuscar(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  let body; try { body = await request.json(); } catch { body = {}; }
  const q = String(body.q || '').trim().slice(0, 300);
  if (!q) return json({ error: 'Escribe qué buscas.' }, 400, headers);
  if (!env.SHARES) return json({ error: 'El backend no tiene el KV SHARES (donde vive el inventario).' }, 501, headers);
  if (!env.ANTHROPIC_API_KEY) return json({ error: 'Falta ANTHROPIC_API_KEY.' }, 501, headers);

  const { estados } = await loadBBData(env);
  const zonas = estados.map((e) => ({ nombre: e.nombre, slug: slugZona(e.nombre), yield: e['yield'], plusvalia: e.plusvalia }));
  // Zonas por municipio (inventario fuera de las 32 ciudades ancla). Se publican
  // desde c21-subir.mjs en listados:_zonas; se fusionan sin duplicar por slug.
  let muniZonas = [];
  try {
    const reg = await env.SHARES.get('listados:_zonas');
    if (reg) { const rz = JSON.parse(reg); muniZonas = Array.isArray(rz) ? rz : (rz.zonas || []); }
  } catch { /* sin registro: solo las 32 ancla */ }
  const yaSlug = new Set(zonas.map((z) => z.slug));
  for (const z of muniZonas) {
    const s = slugZona(z.slug || z.nombre);
    if (!s || yaSlug.has(s)) continue;
    yaSlug.add(s);
    zonas.push({ nombre: z.nombre, slug: s, yield: (typeof z.yield === 'number' ? z.yield : null), plusvalia: z.plusvalia ?? null, municipio: true });
  }
  const cities = zonas.filter((z) => !z.municipio).map((z) => `${z.slug} (${z.nombre}, yield ${z.yield}%)`).join('; ');
  const munis = zonas.filter((z) => z.municipio).map((z) => `${z.slug} (${z.nombre}${z.yield != null ? ', yield ' + z.yield + '%' : ''})`).join('; ');
  const lista = cities + (munis ? '. Municipios adicionales: ' + munis : '');
  const system = `Eres el buscador inteligente de BrickBit, proptech de bienes raíces en México. Conviertes una búsqueda en lenguaje natural en filtros.
Ciudades principales (usa el slug exacto): ${lista}.
Reglas: "para N personas" ⇒ recamaras_min ≈ redondeo(N/2) (mínimo 1). Si piden rendimiento/plusvalía/"que me dé X% anual" ⇒ yield_min y, si no nombran ciudad, deja zonas vacío. Si nombran colonia/ciudad, mapea a la zona BrickBit más cercana. Presupuestos en pesos MXN ("2 millones" = 2000000).
Responde SOLO con un objeto JSON válido (sin texto extra, sin markdown) con esta forma, omitiendo o poniendo null lo que no aplique:
{"operacion": "venta"|"renta"|null, "tipo": "casa"|"departamento"|"terreno"|"local"|"oficina"|"bodega"|null, "zonas": ["slug", ...] (0 a 3), "recamaras_min": número|null, "banos_min": número|null, "presupuesto_min": número|null, "presupuesto_max": número|null, "m2_min": número|null, "yield_min": número|null, "orden": "precio_justo"|"yield"|"precio_asc"|"precio_desc"|null, "intencion": "buscar"|"invertir", "objetivo": "plusvalia"|"renta"|"mixto"|null, "interpretacion": "frase breve y cálida de cómo entendiste la búsqueda"}
"intencion" es "invertir" SOLO cuando la persona expresa que quiere INVERTIR una cantidad o armar un portafolio ("quiero invertir 2 millones", "en qué pongo 5 mdp", "arma un portafolio"), no cuando busca un inmueble para vivir. Con "invertir", el presupuesto va en presupuesto_max y zonas queda vacío salvo que nombren ciudad. "objetivo" distingue si busca plusvalía (revalorización), renta (flujo mensual) o mixto.`;

  let f;
  try { f = await askClaudeJSON(env, system, q); }
  catch (e) { return json({ error: 'No se pudo interpretar la búsqueda: ' + e.message }, 502, headers); }

  let slugs = (f.zonas || []).map(slugZona).filter((s) => zonas.some((z) => z.slug === s));
  if (!slugs.length) {
    const orden = [...zonas].sort((a, b) => (b.yield || 0) - (a.yield || 0));
    slugs = orden.slice(0, 3).map((z) => z.slug);
  }
  slugs = slugs.slice(0, 4);

  const shards = await Promise.all(slugs.map((s) => env.SHARES.get('listados:' + s).then((v) => (v ? JSON.parse(v) : []))));
  const pool = shards.flat();
  const yieldByZona = Object.fromEntries(zonas.map((z) => [z.slug, z.yield]));

  // mediana de precio/m² de venta por zona (para el veredicto de precio justo)
  const medZ = {};
  for (const s of slugs) {
    const ps = pool.filter((x) => slugZona(x.zona || '') === s && x.operacion === 'venta' && x.pm2 > 5000 && x.pm2 < 150000).map((x) => x.pm2).sort((a, b) => a - b);
    if (ps.length) medZ[s] = ps[Math.floor(ps.length / 2)];
  }

  let res = pool.filter((x) => {
    if (f.operacion && x.operacion !== f.operacion) return false;
    if (f.tipo && !String(x.tipo || '').includes(String(f.tipo).toLowerCase())) return false;
    if (f.recamaras_min && !(x.recamaras >= f.recamaras_min)) return false;
    if (f.banos_min && !(x.banos >= f.banos_min)) return false;
    if (f.presupuesto_max && !(x.precio <= f.presupuesto_max)) return false;
    if (f.presupuesto_min && !(x.precio >= f.presupuesto_min)) return false;
    if (f.m2_min && !(x.m2_construccion >= f.m2_min)) return false;
    return true;
  }).map((x) => {
    const s = slugZona(x.zona || ''); const med = medZ[s];
    const vs = (med && x.pm2) ? Math.round((x.pm2 / med - 1) * 100) : null;
    return { ...x, vs, veredicto: vs == null ? null : vs <= -12 ? 'oportunidad' : vs >= 12 ? 'sobreprecio' : 'justo', zona_yield: yieldByZona[s] ?? null };
  });

  if (f.yield_min) res = res.filter((x) => (x.zona_yield || 0) >= f.yield_min);
  const orden = f.orden || (f.yield_min ? 'yield' : 'precio_justo');
  res.sort((a, b) => {
    if (orden === 'yield') return (b.zona_yield || 0) - (a.zona_yield || 0);
    if (orden === 'precio_asc') return a.precio - b.precio;
    if (orden === 'precio_desc') return b.precio - a.precio;
    return (a.vs ?? 999) - (b.vs ?? 999); // precio_justo: oportunidades primero
  });

  // ── Asesor de portafolio ────────────────────────────────────────────────
  // Cuando la intención es INVERTIR y hay presupuesto, no basta una lista: se
  // arma un portafolio real. La SELECCIÓN es determinista y sale de los datos
  // (veredicto de precio vs mediana de su zona, yield de la zona, recortes de
  // precio y días publicada del seguimiento). Claude solo REDACTA la tesis con
  // esos números; no elige ni inventa cifras.
  let portafolio = null;
  if (f.intencion === 'invertir' && f.presupuesto_max > 0) {
    try {
      portafolio = await armarPortafolio(env, res, slugs, f, zonas);
    } catch (e) {
      portafolio = { error: 'No se pudo armar el portafolio: ' + e.message };
    }
  }

  return json({ interpretacion: f.interpretacion || '', filtros: f, zonas: slugs, total: res.length, portafolio, resultados: res.slice(0, 24) }, 200, headers);
}

/* --- Asesor de portafolio: selección con datos, redacción con IA --- */
async function armarPortafolio(env, res, slugs, f, zonas) {
  const presupuesto = f.presupuesto_max;
  // Seguimiento del mercado por zona: recortes de precio y días publicada.
  const segs = {};
  await Promise.all(slugs.map(async (s) => {
    try {
      const v = await env.SHARES.get('listados:_seg-' + s);
      const j = v ? JSON.parse(v) : null;
      segs[s] = (Array.isArray(j) && j[0] && j[0].items) ? j[0] : null;
    } catch { segs[s] = null; }
  }));
  const segDe = (x) => {
    const s = segs[slugZona(x.zona || '')];
    const it = s && s.items && s.items[String(x.id)];
    if (!it) return {};
    const dias = Math.max(0, Math.round((new Date(s.act) - new Date(it.alta)) / 864e5));
    const o = { dias, diasCens: it.alta === s.base };
    if (it.cambios && it.cambios.length && it.cambios[0].de > 0) {
      o.rec = Math.round((it.p / it.cambios[0].de - 1) * 100);
    }
    return o;
  };

  // Puntuación con señales REALES; el peso cambia según el objetivo declarado.
  const pesoRenta = f.objetivo === 'renta' ? 1.6 : f.objetivo === 'plusvalia' ? 0.6 : 1.0;
  const cand = res
    .filter((x) => x.operacion === 'venta' && x.precio > 0 && x.precio <= presupuesto)
    .map((x) => {
      const sg = segDe(x);
      // descuento vs la mediana de SU zona (vs<0 = bajo la mediana)
      const dsc = x.vs == null ? 0 : Math.max(-40, Math.min(40, -x.vs)) / 40;
      const rnd = (x.zona_yield || 0) / 12;                  // yield de zona
      const rec = sg.rec != null && sg.rec < 0 ? Math.min(1, Math.abs(sg.rec) / 15) : 0;
      const neg = sg.dias != null ? Math.min(1, sg.dias / 180) : 0;  // margen de negociación
      return { ...x, ...sg, _score: 1.0 * dsc + pesoRenta * rnd + 0.5 * rec + 0.35 * neg };
    })
    .sort((a, b) => b._score - a._score);

  // Selección voraz con diversificación: máximo una propiedad por zona, para
  // que el portafolio no quede concentrado en un solo mercado.
  const piezas = [];
  const usadas = new Set();
  let gastado = 0;
  for (const c of cand) {
    if (piezas.length >= 3) break;
    const z = slugZona(c.zona || '');
    if (usadas.has(z)) continue;
    if (gastado + c.precio > presupuesto) continue;
    piezas.push(c); usadas.add(z); gastado += c.precio;
  }
  // Si la diversificación dejó dinero sin usar, se completa sin esa restricción.
  if (piezas.length < 3) {
    for (const c of cand) {
      if (piezas.length >= 3) break;
      if (piezas.some((p) => p.id === c.id)) continue;
      if (gastado + c.precio > presupuesto) continue;
      piezas.push(c); gastado += c.precio;
    }
  }
  if (!piezas.length) return { vacio: true, presupuesto };

  const ficha = (p, i) => {
    const partes = [
      `#${i + 1} ${p.tipo || 'inmueble'} en ${p.municipio || ''}${p.zona ? ', ' + p.zona : ''}`,
      `precio ${Math.round(p.precio).toLocaleString('es-MX')} MXN`,
      p.m2_construccion ? `${p.m2_construccion} m² construidos` : null,
      p.pm2 ? `${Math.round(p.pm2).toLocaleString('es-MX')} $/m²` : null,
      p.vs != null ? `${p.vs > 0 ? '+' : ''}${p.vs}% vs la mediana de su zona` : null,
      p.zona_yield != null ? `rendimiento observado de la zona ${p.zona_yield}%` : null,
      p.rec != null && p.rec < 0 ? `ya bajó ${Math.abs(p.rec)}% desde su publicación` : null,
      p.dias != null && p.dias >= 1 ? `${p.diasCens ? 'al menos ' : ''}${p.dias} días publicada` : null,
      p.recamaras ? `${p.recamaras} recámaras` : null,
    ].filter(Boolean);
    return partes.join(' · ');
  };

  const system = `Eres el asesor de inversión inmobiliaria de BrickBit. Te doy un portafolio YA SELECCIONADO con datos reales del inventario de Century 21 y del seguimiento de mercado de BrickBit. Tu trabajo es EXPLICAR por qué cada pieza tiene sentido, usando ÚNICAMENTE los números que te doy.
REGLAS INQUEBRANTABLES:
- No inventes cifras. Si un dato no está en la ficha, no lo menciones.
- No proyectes rendimientos futuros ni porcentajes de plusvalía a X años: no te los estoy dando y no se pueden verificar.
- El rendimiento que te doy es OBSERVADO de la zona, no una promesa.
- Menciona el riesgo real de cada pieza (concentración, liquidez, que el dato es de zona y no del inmueble exacto).
- Español de México, tono de asesor serio, sin euforia ni emojis.
Responde SOLO con JSON válido:
{"resumen": "2 a 3 frases sobre la lógica del portafolio en conjunto", "piezas": [{"tesis": "2 frases de por qué esta propiedad", "riesgo": "1 frase del principal riesgo"}], "siguiente_paso": "1 frase con la acción concreta a seguir"}
El arreglo "piezas" debe tener exactamente ${piezas.length} elementos, en el mismo orden.`;

  const usuario = `Presupuesto: ${Math.round(presupuesto).toLocaleString('es-MX')} MXN. Objetivo declarado: ${f.objetivo || 'no especificado'}.
Portafolio seleccionado (invierte ${Math.round(gastado).toLocaleString('es-MX')} MXN, quedan ${Math.round(presupuesto - gastado).toLocaleString('es-MX')} MXN sin asignar):
${piezas.map(ficha).join('\n')}`;

  let redaccion = {};
  try { redaccion = await askClaudeJSON(env, system, usuario); } catch { redaccion = {}; }
  const textos = Array.isArray(redaccion.piezas) ? redaccion.piezas : [];

  return {
    presupuesto,
    invertido: Math.round(gastado),
    sin_asignar: Math.round(presupuesto - gastado),
    objetivo: f.objetivo || null,
    resumen: redaccion.resumen || '',
    siguiente_paso: redaccion.siguiente_paso || '',
    piezas: piezas.map((p, i) => ({
      id: p.id, titulo: p.titulo, tipo: p.tipo, url: p.url, imagen: p.imagen,
      precio: p.precio, moneda: p.moneda || 'MXN', municipio: p.municipio, zona: p.zona,
      pm2: p.pm2, m2_construccion: p.m2_construccion, recamaras: p.recamaras,
      vs: p.vs, veredicto: p.veredicto, zona_yield: p.zona_yield,
      rec: p.rec ?? null, dias: p.dias ?? null, diasCens: !!p.diasCens,
      tesis: (textos[i] && textos[i].tesis) || '',
      riesgo: (textos[i] && textos[i].riesgo) || '',
    })),
  };
}

/* --- Ingesta y consulta del inventario en KV --- */
async function handleListadosIngest(request, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json' };
  if (!env.SHARES) return json({ error: 'sin KV SHARES' }, 501, headers);
  if (!env.INGEST_SECRET) return json({ error: 'Configura el secreto INGEST_SECRET en el Worker.' }, 501, headers);
  if (request.headers.get('x-ingest-key') !== env.INGEST_SECRET) return json({ error: 'clave inválida' }, 403, headers);
  let body; try { body = await request.json(); } catch { body = null; }
  if (!body || !body.slug || !Array.isArray(body.items)) return json({ error: 'Se espera { slug, items[] }' }, 400, headers);
  // Los slugs que empiezan con "_" son reservados (p. ej. _zonas, el registro de
  // municipios) y se guardan literales: slugZona() les quitaría el guion bajo.
  const key = String(body.slug).startsWith('_') ? String(body.slug) : slugZona(body.slug);
  await env.SHARES.put('listados:' + key, JSON.stringify(body.items));
  // índice
  let idx = {}; try { idx = JSON.parse(await env.SHARES.get('listados:_index') || '{}'); } catch {}
  idx[key] = body.items.length; idx._actualizado = new Date().toISOString();
  await env.SHARES.put('listados:_index', JSON.stringify(idx));
  return json({ ok: true, slug: key, n: body.items.length }, 200, headers);
}
async function handleListadosGet(request, url, env) {
  const headers = { 'access-control-allow-origin': '*', 'content-type': 'application/json', 'cache-control': 'public, max-age=300' };
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
  if (!env.SHARES) return json({ error: 'sin KV' }, 501, headers);
  const zona = url.searchParams.get('zona');
  if (!zona) { const idx = await env.SHARES.get('listados:_index'); return new Response(idx || '{}', { headers }); }
  const key = zona.startsWith('_') ? zona : slugZona(zona);
  const v = await env.SHARES.get('listados:' + key);
  return new Response(v || '[]', { headers });
}

/* --- WhatsApp vía Twilio --- */
async function sendWhatsAppTwilio(env, to, body) {
  const sid = env.TWILIO_ACCOUNT_SID, tok = env.TWILIO_AUTH_TOKEN;
  const wa = s => (String(s).startsWith('whatsapp:') ? String(s) : 'whatsapp:' + s);
  const form = new URLSearchParams();
  form.set('From', wa(env.TWILIO_WHATSAPP_FROM));
  form.set('To', wa(to));
  form.set('Body', body);
  const r = await fetch('https://api.twilio.com/2010-04-01/Accounts/' + sid + '/Messages.json', {
    method: 'POST',
    headers: { authorization: 'Basic ' + btoa(sid + ':' + tok), 'content-type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!r.ok) throw new Error('Twilio ' + r.status + ': ' + (await r.text()).slice(0, 200));
}
