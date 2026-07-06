// netlify/functions/denue.js
// Proxy server-side hacia la API del DENUE (evita CORS).
// Usa el cliente clásico de Node (https) en vez de fetch(undici), porque INEGI
// devuelve respuestas HTTP poco estándar que rompen a undici con ERR_ASSERTION.
const https = require('https');

function getText(url, headers, depth) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers, timeout: 22000, family: 4 }, (res) => {
      // seguir un redirect simple si lo hubiera
      if ([301, 302, 307, 308].includes(res.statusCode) && res.headers.location && (depth || 0) < 2) {
        res.resume();
        return resolve(getText(res.headers.location, headers, (depth || 0) + 1));
      }
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { data += c; });
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('timeout', () => { req.destroy(new Error('timeout')); });
    req.on('error', reject);
  });
}

exports.handler = async (event) => {
  const token = process.env.DENUE_TOKEN;
  const cors = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*'
  };
  if (!token) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: 'Falta DENUE_TOKEN en las variables de entorno de Netlify.' }) };
  }
  const q = event.queryStringParameters || {};
  const lat = q.lat, lng = q.lng, radio = q.radio || '2000';
  if (!lat || !lng) {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Faltan parámetros lat y lng.' }) };
  }
  const url = 'https://www.inegi.org.mx/app/api/denue/v1/consulta/Buscar/todos/' +
              encodeURIComponent(lat) + ',' + encodeURIComponent(lng) + '/' +
              encodeURIComponent(radio) + '/' + encodeURIComponent(token);
  try {
    const { status, body } = await getText(url, {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'es-MX,es;q=0.9',
      'Referer': 'https://www.inegi.org.mx/'
    });
    return { statusCode: status || 200, headers: cors, body: body || '[]' };
  } catch (e) {
    const cause = e && e.cause ? (e.cause.code || e.cause.message || String(e.cause)) : '';
    return { statusCode: 502, headers: cors, body: JSON.stringify({ error: String((e && e.message) || e), cause }) };
  }
};
