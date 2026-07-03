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
    'access-control-allow-methods': 'POST, OPTIONS',
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
    if (url.pathname !== '/api/claude' || request.method !== 'POST') {
      return json({ error: { message: 'No encontrado. Usa POST /api/claude' } }, 404, headers);
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

    const { system, content, schema } = payload || {};
    if (typeof system !== 'string' || !Array.isArray(content) || content.length === 0 ||
        typeof schema !== 'object' || schema === null) {
      return json({ error: { message: 'Cuerpo inválido: se esperan { system, content, schema }.' } }, 400, headers);
    }
    if (!content.every(b => b && ALLOWED_BLOCK_TYPES.has(b.type))) {
      return json({ error: { message: 'Tipo de bloque de contenido no permitido.' } }, 400, headers);
    }

    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: ANTHROPIC_MODEL,
        max_tokens: MAX_TOKENS,
        thinking: { type: 'adaptive' },
        system,
        output_config: { format: { type: 'json_schema', schema } },
        messages: [{ role: 'user', content }],
      }),
    });

    // Devuelve la respuesta de Anthropic tal cual (mismo formato que espera el frontend)
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { ...headers, 'content-type': 'application/json' },
    });
  },
};
