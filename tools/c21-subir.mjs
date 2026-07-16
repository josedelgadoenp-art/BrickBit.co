#!/usr/bin/env node
/* =============================================================================
   c21-subir.mjs — Sube el inventario de Century 21 al Worker de BrickBit.
   Corre en TU máquina; lee c21_out/listados.json, lo LIMPIA (quita teléfono,
   email y nombre del asesor), lo cruza a la zona BrickBit por coordenadas, y
   lo sube al KV del Worker para que la búsqueda con IA tenga inventario.

   Uso (dentro de la carpeta del proyecto):
     node tools/c21-subir.mjs --key TU_INGEST_SECRET
     node tools/c21-subir.mjs --key TU_INGEST_SECRET --url https://tu-worker.workers.dev

   El INGEST_SECRET es el que configuraste en el Worker con:
     npx wrangler secret put INGEST_SECRET
============================================================================= */
import fs from 'node:fs';

const args = process.argv.slice(2);
const val = (n) => { const i = args.indexOf('--' + n); return i >= 0 ? args[i + 1] : null; };
const KEY = val('key') || process.env.INGEST_SECRET;
const BACKEND = (val('url') || 'https://brickbit-api.jose-delgado-enp.workers.dev').replace(/\/+$/, '');
if (!KEY) { console.error('Falta la clave. Uso: node tools/c21-subir.mjs --key TU_INGEST_SECRET'); process.exit(1); }

const inv = 'c21_out/listados.json';
if (!fs.existsSync(inv)) { console.error('No encuentro ' + inv + '. Corre primero: node tools/c21-scraper.mjs todo'); process.exit(1); }
const D = JSON.parse(fs.readFileSync(inv, 'utf8'));
const est = JSON.parse(fs.readFileSync('data/estados.json', 'utf8'));
const zonas = est.estados || est;

const zc = zonas.map((e) => [e.nombre, e.lat, e.lng]);
const hav = (a, b, c, d) => { const R = 6371, p = Math.PI / 180; const x = (c - a) * p, y = (d - b) * p; const h = Math.sin(x / 2) ** 2 + Math.cos(a * p) * Math.cos(c * p) * Math.sin(y / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
const slug = (n) => String(n).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, '-');
function zonaDe(lat, lng) { if (lat == null || lng == null) return null; let best = null, bd = 1e9; for (const [n, la, lo] of zc) { const dd = hav(lat, lng, la, lo); if (dd < bd) { bd = dd; best = n; } } return bd <= 40 ? best : null; }

// SOLO campos públicos — se descartan teléfono, whatsapp, email y nombre del asesor
const KEEP = ['id', 'url', 'titulo', 'precio', 'moneda', 'operacion', 'tipo', 'colonia', 'municipio', 'estado', 'm2_construccion', 'm2_terreno', 'recamaras', 'banos', 'estacionamientos', 'lat', 'lng', 'imagen', 'afiliado'];

const shards = {};
let sin = 0;
for (const x of D) {
  const z = zonaDe(x.lat, x.lng);
  if (!z) { sin++; continue; }
  const o = {}; for (const k of KEEP) o[k] = x[k] ?? null;
  const p = x.precio, c = x.m2_construccion;
  o.pm2 = (p && c && c > 0) ? Math.round(p / c) : null;
  o.zona = z;
  (shards[z] = shards[z] || []).push(o);
}
const entries = Object.entries(shards).sort((a, b) => b[1].length - a[1].length);
console.log(`Inventario: ${D.length} propiedades → ${entries.length} zonas BrickBit (+${sin} sin zona) · SIN datos personales`);
console.log(`Subiendo a ${BACKEND} …\n`);

let okN = 0, total = 0;
for (const [zona, items] of entries) {
  try {
    const r = await fetch(BACKEND + '/api/listados-ingest', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-ingest-key': KEY },
      body: JSON.stringify({ slug: slug(zona), items }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { okN++; total += j.n || items.length; console.log(`  ✓ ${zona.padEnd(20)} ${items.length}`); }
    else { console.log(`  ✗ ${zona.padEnd(20)} ${j.error || ('HTTP ' + r.status)}`); }
  } catch (e) { console.log(`  ✗ ${zona.padEnd(20)} ${e.message}`); }
}
console.log(`\n✅ Subidas ${okN}/${entries.length} zonas · ${total} propiedades en el buscador.`);
console.log('   Ahora la búsqueda con IA (/api/buscar) ya tiene inventario. Pruébala en el buscador.');
