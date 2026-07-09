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

    if (url.pathname !== '/api/claude' || request.method !== 'POST') {
      return json({ error: { message: 'No encontrado. Usa POST /api/claude, POST /api/share o GET /api/share/{id}' } }, 404, headers);
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
  if (!data || typeof data !== 'object' || !data.geometry || !data.engineering) {
    return json({ error: { message: 'Proyecto inválido: se esperan geometry y engineering.' } }, 400, headers);
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
