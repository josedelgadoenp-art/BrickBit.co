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

// --- Saneo de geocodificación rota del portal ---
// C21 pone coordenadas por DEFECTO (un punto en CDMX) a listados sin geo real:
// una "oficina en Tijuana" llega con lat/lng de Polanco y contamina la zona.
// Regla: si el ESTADO del texto queda a >150 km de las coordenadas, las
// coordenadas mienten → se anulan y el listado se enruta por municipio/estado.
const ANCLA_EDO = {};
for (const e of zonas) { const edo = (e.estado || e.nombre); if (!ANCLA_EDO[edo]) ANCLA_EDO[edo] = [e.lat, e.lng]; }
const normTxt = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const EDO_LL = {};
for (const e of zonas) EDO_LL[normTxt(e.nombre)] = [e.lat, e.lng];
let geoRotas = 0;

const shards = {};          // zonas ciudad (las 32 ancla, por cercanía de coordenadas)
const huerfanas = [];       // {x, o} fuera del radio de 40 km de toda ciudad ancla
for (const x of D) {
  if (x.lat != null && x.lng != null && x.estado) {
    // ancla de referencia del estado (por la capital que tenemos en estados.json)
    const cap = Object.entries(EDO_LL).find(([n]) => normTxt(x.estado).includes(n) || n.includes(normTxt(x.estado)));
    if (cap && hav(x.lat, x.lng, cap[1][0], cap[1][1]) > 150) { x.lat = null; x.lng = null; geoRotas++; }
  }
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
console.log(`  · Geocodificación rota anulada: ${geoRotas} listados (se enrutan por su municipio/estado de texto)`);
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

/* =============================================================================
   MEMORIA DEL MERCADO — cada corrida deja de ser una foto y se vuelve película.
   Por zona se mantiene en el KV (vía el mismo API, slugs reservados "_"):
     _seg-<slug>   seguimiento por propiedad: fecha de alta, recortes de precio,
                   bajas (¿vendida/retirada?) y días en mercado.
     _metricas     medianas reales del mes por zona: $/m² venta, $/m² renta,
                   $/m² terreno y yield bruto (renta·12/venta) con sus n.
     _hist         serie mensual de _metricas → el Índice BrickBit (pulso.html).
   Todo se calcula AQUÍ (local); el Worker solo guarda. Sin redeploy.
============================================================================= */
const HOY = new Date().toISOString().slice(0, 10);
const MES = HOY.slice(0, 7);
const USD_MXN = 17.5; // TC de referencia (jul 2026); actualiza si el peso se mueve
const normPm2 = (i) => (i.moneda === 'USD' ? (i.pm2 || 0) * USD_MXN : (i.pm2 || 0));
const esTerreno = (i) => (i.m2_terreno > 0 && (!i.m2_construccion || i.m2_construccion <= 0));

async function getKV(zonaKey) {
  try {
    const r = await fetch(`${BACKEND}/api/listados?zona=${encodeURIComponent(zonaKey)}`);
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function metricasDe(slugZ, nombre, items) {
  const ventas = items.filter((i) => i.operacion === 'venta' && !esTerreno(i));
  const rentas = items.filter((i) => i.operacion === 'renta' && !esTerreno(i));
  const terrenos = items.filter((i) => esTerreno(i) && i.operacion !== 'renta');
  const pm2v = med(ventas.map(normPm2));
  const pm2r = med(rentas.map(normPm2));
  const pm2t = med(terrenos.map((i) => {
    const p = i.moneda === 'USD' ? (i.precio || 0) * USD_MXN : (i.precio || 0);
    return i.m2_terreno > 0 ? p / i.m2_terreno : 0;
  }));
  // yield bruto solo con muestra suficiente en AMBOS lados (honestidad de datos)
  const yld = (pm2v && pm2r && ventas.length >= 5 && rentas.length >= 5)
    ? Math.round((pm2r * 12 / pm2v) * 1000) / 10 : null;
  return {
    slug: slugZ, nombre, f: HOY,
    pm2v: pm2v ? Math.round(pm2v) : null, nV: ventas.length,
    pm2r: pm2r ? Math.round(pm2r) : null, nR: rentas.length,
    pm2t: pm2t ? Math.round(pm2t) : null, nT: terrenos.length,
    yield: yld,
  };
}

// Diff del inventario nuevo contra el seguimiento previo del KV.
async function actualizarSeg(slugZ, items) {
  const prevArr = await getKV('_seg-' + slugZ);
  const prev = (Array.isArray(prevArr) && prevArr[0] && prevArr[0].items) ? prevArr[0] : null;
  const seg = { v: 1, base: prev ? prev.base : HOY, act: HOY, items: {}, bajas: prev ? (prev.bajas || {}) : {} };
  const va = prev ? prev.items : {};
  let altas = 0, recortes = 0, bajas = 0;
  for (const it of items) {
    if (!it.id || !(it.precio > 0)) continue;
    const id = String(it.id);
    const p = prevSafe(va[id]);
    if (p && p.m === (it.moneda || 'MXN')) {
      const reg = { alta: p.alta, p: it.precio, m: p.m, cambios: p.cambios || [] };
      if (it.precio !== p.p) {
        reg.cambios = reg.cambios.concat([{ f: HOY, de: p.p, a: it.precio }]).slice(-10);
        if (it.precio < p.p) recortes++;
      }
      seg.items[id] = reg;
    } else {
      seg.items[id] = { alta: HOY, p: it.precio, m: it.moneda || 'MXN', cambios: [] };
      if (prev) altas++;
      delete seg.bajas[id]; // si reaparece, deja de contar como baja
    }
  }
  // lo que estaba y ya no está → baja (vendida o retirada; no podemos saber cuál)
  for (const [id, p] of Object.entries(va)) {
    if (seg.items[id]) continue;
    const dias = Math.max(0, Math.round((new Date(HOY) - new Date(p.alta)) / 864e5));
    seg.bajas[id] = { baja: HOY, p: p.p, dias };
    bajas++;
  }
  // cap de bajas: conserva las 500 más recientes
  const bk = Object.entries(seg.bajas).sort((a, b) => (b[1].baja || '').localeCompare(a[1].baja || '')).slice(0, 500);
  seg.bajas = Object.fromEntries(bk);
  await subirSilencioso('_seg-' + slugZ, [seg]);
  return { altas, recortes, bajas, seguidas: Object.keys(seg.items).length };
}
function prevSafe(x) { return (x && typeof x === 'object' && x.alta && x.p > 0) ? x : null; }

async function subirSilencioso(slugZona, items) {
  try {
    const r = await fetch(BACKEND + '/api/listados-ingest', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-ingest-key': KEY },
      body: JSON.stringify({ slug: slugZona, items }),
    });
    return r.ok;
  } catch { return false; }
}

let okN = 0, total = 0;
const metricas = [];
const segTot = { altas: 0, recortes: 0, bajas: 0, seguidas: 0 };
async function procesarZona(slugZ, nombre, items) {
  const n = await subir(slugZ, items, nombre);
  if (n) { okN++; total += n; }
  metricas.push(metricasDe(slugZ, nombre, items));
  const s = await actualizarSeg(slugZ, items);
  for (const k of Object.keys(segTot)) segTot[k] += s[k];
}

for (const [zona, items] of entries) await procesarZona(slug(zona), zona, items);
console.log('  — municipios —');
for (const g of registro) await procesarZona(g.slug, g.nombre, muniShards[g.slug]);

// Publicar el registro de zonas por municipio para que el buscador con IA las conozca.
await subir('_zonas', registro, '_zonas (registro de municipios)');

// Métricas del mes (medianas reales por zona) + serie histórica mensual.
await subir('_metricas', metricas, '_metricas (medianas y yield)');
const histPrev = await getKV('_hist');
let hist = Array.isArray(histPrev) ? histPrev.filter((h) => h && h.f) : [];
const entradaMes = {
  f: MES,
  zonas: Object.fromEntries(metricas.map((m) => [m.slug,
    { pm2v: m.pm2v, nV: m.nV, pm2r: m.pm2r, nR: m.nR, pm2t: m.pm2t, yield: m.yield }])),
};
hist = hist.filter((h) => h.f !== MES).concat([entradaMes]).slice(-60); // re-corridas del mes: se reemplaza
await subir('_hist', hist, `_hist (índice mensual, ${hist.length} mes${hist.length === 1 ? '' : 'es'})`);

console.log(`\n✅ Subidas ${okN} zonas · ${total} propiedades en el buscador.`);
console.log(`   Cobertura: ${entries.length} ciudades + ${registro.length} municipios.`);
console.log(`   Seguimiento: ${segTot.seguidas} propiedades en memoria · ${segTot.altas} altas nuevas · ${segTot.recortes} recortes de precio · ${segTot.bajas} bajas detectadas.`);
console.log(`   Índice BrickBit: mes ${MES} registrado (${hist.length} mes${hist.length === 1 ? '' : 'es'} acumulados).`);
console.log('   La búsqueda con IA (/api/buscar) ya puede encontrar inmuebles fuera de las 32 capitales.');
