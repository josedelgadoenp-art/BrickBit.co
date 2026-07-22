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
// slug robusto a puntuación: DEBE coincidir con slugZona() del Worker (que ahora
// también colapsa cualquier no-alfanumérico a "-"), o el buscador no empataría
// "García, Nuevo León" (display) con su shard "garcia-nuevo-leon".
const slug = (n) => String(n).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
function zonaDe(lat, lng) { if (lat == null || lng == null) return null; let best = null, bd = 1e9; for (const [n, la, lo] of zc) { const dd = hav(lat, lng, la, lo); if (dd < bd) { bd = dd; best = n; } } return bd <= 40 ? best : null; }
const med = (a) => { const s = a.filter((v) => v > 0).sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };

// SOLO campos públicos — se descartan teléfono, whatsapp, email y nombre del asesor
const KEEP = ['id', 'url', 'titulo', 'precio', 'moneda', 'operacion', 'tipo', 'colonia', 'municipio', 'estado', 'm2_construccion', 'm2_terreno', 'recamaras', 'banos', 'estacionamientos', 'lat', 'lng', 'imagen', 'afiliado'];

// Umbral mínimo de propiedades para que un municipio valga como "zona" propia.
// 3 recupera la cola de municipios chicos (con 3-4 inmuebles) que antes se
// descartaba; se puede subir con --minz N si se quiere zonas más robustas.
const MINZ = (() => { const i = args.indexOf('--minz'); const v = i >= 0 ? parseInt(args[i + 1], 10) : 3; return isNaN(v) || v < 2 ? 3 : v; })();

const shards = {};          // zonas ciudad (las 32 ancla, por cercanía de coordenadas)
const huerfanas = [];       // {x, o} fuera del radio de 40 km de toda ciudad ancla
for (const x of D) {
  const o = {}; for (const k of KEEP) o[k] = x[k] ?? null;
  const p = x.precio, c = x.m2_construccion;
  o.pm2 = (p && c && c > 0) ? Math.round(p / c) : null;
  const z = zonaDe(x.lat, x.lng);
  if (z) { o.zona = z; (shards[z] = shards[z] || []).push(o); }
  else { huerfanas.push({ x, o }); }
}

// Agrupar las huérfanas por municipio+estado → zonas dinámicas. Cada propiedad
// ya trae municipio y estado; el display "Municipio, Estado" y su slug quedan
// consistentes con slugZona() del Worker.
const grupos = {}; // slug -> { slug, nombre, items[], lats[], lngs[] }
let sinMunicipio = 0;
for (const { x, o } of huerfanas) {
  if (!x.municipio || !x.estado) { sinMunicipio++; continue; }
  const nombre = `${String(x.municipio).trim()}, ${String(x.estado).trim()}`;
  const s = slug(nombre);
  const g = grupos[s] || (grupos[s] = { slug: s, nombre, items: [], lats: [], lngs: [] });
  o.zona = nombre;
  g.items.push(o);
  if (x.lat != null) g.lats.push(x.lat);
  if (x.lng != null) g.lngs.push(x.lng);
}

// Registro de zonas por municipio (las que superan el umbral) con su yield real
// cuando hay suficientes rentas y ventas para medirlo con honestidad.
const registro = [];
const muniShards = {};
let muniProps = 0, colaProps = 0;
for (const g of Object.values(grupos)) {
  if (g.items.length < MINZ) { colaProps += g.items.length; continue; }
  muniProps += g.items.length;
  muniShards[g.slug] = g.items;
  const USD_MXN = 17.5; // TC de referencia (jul 2026); actualiza si el peso se mueve
  const norm = (i) => (i.moneda === 'USD' ? i.pm2 * USD_MXN : i.pm2);
  const ventas = g.items.filter((i) => i.operacion === 'venta');
  const rentas = g.items.filter((i) => i.operacion === 'renta');
  const vPm = med(ventas.map(norm)), rPm = med(rentas.map(norm));
  const yld = (vPm && rPm && ventas.length >= 5 && rentas.length >= 5)
    ? Math.round((rPm * 12 / vPm) * 1000) / 10 : null;   // yield bruto anual = renta_mensual·12 / venta
  const lat = g.lats.length ? +(g.lats.reduce((a, b) => a + b, 0) / g.lats.length).toFixed(4) : null;
  const lng = g.lngs.length ? +(g.lngs.reduce((a, b) => a + b, 0) / g.lngs.length).toFixed(4) : null;
  // pm2 = mediana real de $/m² de venta (MXN); la usa el mapa de "Mercado real".
  registro.push({ slug: g.slug, nombre: g.nombre, yield: yld, n: g.items.length, lat, lng, pm2: vPm ? Math.round(vPm) : null, municipio: true });
}
registro.sort((a, b) => b.n - a.n);

const entries = Object.entries(shards).sort((a, b) => b[1].length - a[1].length);
console.log(`Inventario: ${D.length} propiedades · SIN datos personales`);
console.log(`  · 32 ciudades ancla:     ${entries.reduce((s, e) => s + e[1].length, 0)} propiedades en ${entries.length} zonas`);
console.log(`  · Municipios (nuevos):   ${muniProps} propiedades en ${registro.length} zonas (mín. ${MINZ} c/u)`);
console.log(`  · Cola corta descartada: ${colaProps} (municipios con <${MINZ}) · ${sinMunicipio} sin municipio`);
console.log(`Subiendo a ${BACKEND} …\n`);

async function subir(slugZona, items, etiqueta) {
  try {
    const r = await fetch(BACKEND + '/api/listados-ingest', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-ingest-key': KEY },
      body: JSON.stringify({ slug: slugZona, items }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { console.log(`  ✓ ${etiqueta.padEnd(30)} ${items.length}`); return j.n || items.length; }
    console.log(`  ✗ ${etiqueta.padEnd(30)} ${j.error || ('HTTP ' + r.status)}`); return 0;
  } catch (e) { console.log(`  ✗ ${etiqueta.padEnd(30)} ${e.message}`); return 0; }
}

let okN = 0, total = 0;
for (const [zona, items] of entries) { const n = await subir(slug(zona), items, zona); if (n) { okN++; total += n; } }
console.log('  — municipios —');
for (const g of registro) { const n = await subir(g.slug, muniShards[g.slug], g.nombre); if (n) { okN++; total += n; } }

// Publicar el registro de zonas por municipio para que el buscador con IA las conozca.
await subir('_zonas', registro, '_zonas (registro de municipios)');

console.log(`\n✅ Subidas ${okN} zonas · ${total} propiedades en el buscador.`);
console.log(`   Cobertura: ${entries.length} ciudades + ${registro.length} municipios.`);
console.log('   La búsqueda con IA (/api/buscar) ya puede encontrar inmuebles fuera de las 32 capitales.');
