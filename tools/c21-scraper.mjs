#!/usr/bin/env node
/* =============================================================================
   c21-scraper.mjs — Robot de inventario Century 21 México → BrickBit
   Scraping AUTORIZADO por la franquicia (acuerdo BrickBit × Century 21 MX).

   Uso (PowerShell o Terminal, dentro de la carpeta del proyecto):
     node tools/c21-scraper.mjs muestra          ← prueba con 1 página (30 s)
     node tools/c21-scraper.mjs todo             ← inventario completo (~10-25 min)
     node tools/c21-scraper.mjs todo --hasta 50  ← límite de páginas (pruebas)
     node tools/c21-scraper.mjs profundo         ← rescata estados grandes que
                                                    topan el buscador (CDMX, Edomex,
                                                    Q. Roo…): re-barre por municipio.
     node tools/c21-scraper.mjs profundo --estado ciudad-de-mexico   ← uno solo
     node tools/c21-scraper.mjs profundo --umbral 400                ← baja el corte

   Salidas (carpeta c21_out/):
     listados.ndjson   una propiedad por línea (se va guardando; sirve de respaldo)
     listados.json     el arreglo completo al terminar
     listados.csv      lo mismo en CSV (abre en Excel)
     estado.json       progreso para reanudar si se corta

   Cortesía con el servidor: 1 página a la vez, pausa de ~0.8 s entre páginas,
   reintentos con espera exponencial, y User-Agent que nos identifica.
============================================================================= */

import fs from 'node:fs';
import path from 'node:path';

const BASE = 'https://century21mexico.com';
const OUT = 'c21_out';
const UA = 'Mozilla/5.0 (compatible; BrickBitBot/1.0; +https://brickbit.co; scraping autorizado por Century 21 MX)';

const args = process.argv.slice(2);
const modo = args[0] || 'muestra';
const flag = (n, d) => {
  const i = args.indexOf('--' + n);
  return i >= 0 ? Number(args[i + 1]) : d;
};

fs.mkdirSync(OUT, { recursive: true });

/* ---------- red ---------- */
async function fetchText(url, intento = 1) {
  const MAX = 4;
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 30000);
    const r = await fetch(url, {
      signal: ctl.signal,
      headers: { 'user-agent': UA, 'accept-language': 'es-MX,es;q=0.9', accept: 'text/html,*/*' },
    });
    clearTimeout(t);
    if (r.status === 429 || r.status === 403) {
      if (intento >= MAX) throw new Error(`HTTP ${r.status} persistente — el sitio está limitando; espera unos minutos y reanuda con: node tools/c21-scraper.mjs todo`);
      const espera = 15000 * intento;
      console.log(`   ⏳ HTTP ${r.status}; esperando ${espera / 1000}s (cortesía)…`);
      await new Promise((s) => setTimeout(s, espera));
      return fetchText(url, intento + 1);
    }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.text();
  } catch (e) {
    if (intento >= MAX) throw e;
    await new Promise((s) => setTimeout(s, 2000 * 2 ** (intento - 1)));
    return fetchText(url, intento + 1);
  }
}
const pausa = () => new Promise((s) => setTimeout(s, 600 + Math.random() * 500));

/* ---------- utilidades de parseo ---------- */
const numero = (s) => {
  if (s == null) return null;
  const m = String(s).replace(/,/g, '').match(/-?[\d.]+/); // -? conserva el signo (longitudes)
  return m ? parseFloat(m[0]) : null;
};
const limpia = (s) => String(s || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

/* Estrategia 1: JSON-LD (schema.org) si el sitio lo trae */
function parseJsonLd(html) {
  const out = [];
  const re = /<script[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = re.exec(html))) {
    try {
      const j = JSON.parse(m[1]);
      const nodos = [];
      const mete = (x) => { if (!x) return; if (Array.isArray(x)) return x.forEach(mete); nodos.push(x); if (x['@graph']) mete(x['@graph']); if (x.itemListElement) mete(x.itemListElement.map((e) => e.item || e)); };
      mete(j);
      for (const n of nodos) {
        const t = String(n['@type'] || '');
        if (!/Residence|House|Apartment|RealEstate|Product|Offer|Place|Accommodation/i.test(t)) continue;
        const oferta = n.offers || {};
        const precio = numero(oferta.price ?? n.price);
        if (!precio) continue;
        out.push({
          url: n.url || n['@id'] || null,
          titulo: limpia(n.name || ''),
          precio, moneda: oferta.priceCurrency || 'MXN',
          ubicacion: limpia(typeof n.address === 'string' ? n.address : (n.address && [n.address.streetAddress, n.address.addressLocality, n.address.addressRegion].filter(Boolean).join(', ')) || ''),
          m2_construccion: numero(n.floorSize && (n.floorSize.value ?? n.floorSize)),
          m2_terreno: null,
          recamaras: numero(n.numberOfRooms ?? n.numberOfBedrooms),
          banos: numero(n.numberOfBathroomsTotal),
          estacionamientos: null,
          tipo: limpia(n.additionalType || t), operacion: null,
          imagen: (Array.isArray(n.image) ? n.image[0] : n.image) || null,
          lat: n.geo ? numero(n.geo.latitude) : null,
          lng: n.geo ? numero(n.geo.longitude) : null,
          _via: 'jsonld',
        });
      }
    } catch { /* JSON-LD malformado: seguimos */ }
  }
  return out;
}

/* Estrategia 2: "ventana de precio" — replica la estructura de tarjeta que ya
   validamos con la muestra de 400 (precio, m² Terreno, m² Construcción, Baños,
   Rec., Estac., tipo/operación, ubicación con comas, imagen del CDN). */
function parseVentanas(html) {
  const out = [];
  const re = /\$\s?([\d.,]+)\s*(MXN|USD)/g;
  let m;
  const usados = new Set();
  while ((m = re.exec(html))) {
    const i = m.index;
    if ([...usados].some((j) => Math.abs(j - i) < 120)) continue; // mismo card
    usados.add(i);
    const win = html.slice(i, i + 4000);
    const antes = html.slice(Math.max(0, i - 1500), i);
    const g = (rx, s = win) => { const mm = s.match(rx); return mm ? mm[1] : null; };

    // case-sensitive (mayúscula inicial) para no pescar dentro de slugs de URL;
    // [^<>"] evita cruzar atributos href
    const tipoM = win.match(/(Casa|Departamento|Terreno|Local(?:es)?|Oficinas?|Bodega|Edificio|Rancho|Inmueble)([^<>"]{0,30}?)\s+en\s+(venta|renta)/);
    const tipoOp = tipoM ? (tipoM[1] + tipoM[2]) : null;
    const opM = tipoM ? [null, tipoM[3]] : win.match(/\ben\s+(venta|renta)\b/);

    // ubicación: primer texto plano con ≥2 comas cerca del precio
    let ubic = null;
    for (const s of [win, antes]) {
      const txts = s.split(/<[^>]+>/).map((x) => x.replace(/\s+/g, ' ').trim());
      ubic = txts.find((x) => x.length > 8 && x.length < 170 && (x.match(/,/g) || []).length >= 2 && !x.includes('$'));
      if (ubic) break;
    }
    // url del detalle: ancla cercana que no sea de paginación
    let url = null;
    for (const s of [antes, win]) {
      const hs = [...s.matchAll(/href\s*=\s*["']([^"']+)["']/gi)].map((x) => x[1])
        .filter((h) => !/resultados|pagina|javascript|#|facebook|twitter|whats/i.test(h) && /\/[a-z0-9-]{6,}/i.test(h));
      if (hs.length) { url = hs[hs.length - 1]; break; }
    }
    if (url && url.startsWith('/')) url = BASE + url;

    out.push({
      url,
      titulo: limpia(g(/>([^<>]{15,120})<\/(?:h\d|a|strong)/i) || (tipoOp ? tipoOp : '')),
      precio: numero(m[1]), moneda: m[2],
      ubicacion: ubic || null,
      m2_terreno: numero(g(/([\d.,]+)\s*m²\s*(?:de\s*)?Terreno/i)),
      m2_construccion: numero(g(/([\d.,]+)\s*m²\s*(?:de\s*)?Construcci/i)),
      recamaras: numero(g(/([\d.,]+)\s*Rec\b/i)),
      banos: numero(g(/([\d.,]+)\s*Baño/i)),
      estacionamientos: numero(g(/([\d.,]+)\s*Estac/i)),
      tipo: tipoOp ? limpia(tipoOp) : null,
      operacion: opM ? opM[1].toLowerCase() : null,
      mantenimiento: numero(g(/\+\s*([\d.,]+)\s*mantenimiento/i)),
      imagen: g(/(https:\/\/cdn\.21online\.lat\/[^"'\s]+\.(?:jpg|jpeg|png|webp))/i),
      _via: 'ventana',
    });
  }
  return out;
}

/* Estrategia 3: JSON incrustado (Next.js __NEXT_DATA__, application/json,
   window.__NUXT__/__INITIAL_STATE__) — recorre el árbol y saca los objetos
   que "parecen propiedad" (precio + ubicación/título). */
const K = {
  precio: /^(precio|price|amount|valor|monto|list_?price|price_?value|sale_?price)$/i,
  moneda: /^(moneda|currency|price_?currency)$/i,
  constr: /^(construccion|construcción|m2_?construccion|construction|constructed|built|built_?area|building_?area|construction_?(?:size|area)|covered_?area|superficie_?construida|sup_?construccion|surface_?built)$/i,
  terreno: /^(terreno|land|land_?area|lot_?size|lot_?area|superficie_?terreno|sup_?terreno|land_?size)$/i,
  rec: /^(recamaras|recámaras|habitaciones|bedrooms|rooms|dormitorios|beds)$/i,
  banos: /^(banos|baños|banios|bathrooms|baths)$/i,
  estac: /^(estacionamientos|parking|garages|cocheras|parking_?spaces)$/i,
  tipo: /^(tipo|type|property_?type|tipo_?propiedad|category|categoria)$/i,
  oper: /^(operacion|operación|operation|tipo_?operacion|transaction|listing_?type)$/i,
  titulo: /^(titulo|título|title|name|nombre|headline)$/i,
  ubic: /^(ubicacion|ubicación|direccion|dirección|address|location|colonia|municipio|ciudad|estado|neighborhood|full_?address)$/i,
  url: /^(url|slug|link|permalink|detail_?url|canonical)$/i,
  img: /^(imagen|image|foto|photo|thumbnail|main_?image|cover|images|fotos|photos)$/i,
  lat: /^(lat|latitude|latitud)$/i,
  lng: /^(lng|lon|long|longitude|longitud)$/i,
};
const asNum2 = (v) => typeof v === 'number' ? v : numero(v);
function pick(o, rx) { for (const k of Object.keys(o)) if (rx.test(k)) return o[k]; return undefined; }
function esPropiedad(o) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return false;
  const p = asNum2(pick(o, K.precio));
  if (!p || p < 1000) return false;
  return !!(pick(o, K.ubic) || pick(o, K.titulo));
}
function mapProp(o) {
  const imgRaw = pick(o, K.img);
  const img = Array.isArray(imgRaw) ? (typeof imgRaw[0] === 'string' ? imgRaw[0] : (imgRaw[0] && (imgRaw[0].url || imgRaw[0].src))) : imgRaw;
  const tipo = limpia(pick(o, K.tipo) || '');
  const operRaw = limpia(pick(o, K.oper) || tipo || '');
  const oper = /renta|rent|lease/i.test(operRaw) ? 'renta' : /venta|sale|sell/i.test(operRaw) ? 'venta' : null;
  let url = pick(o, K.url);
  if (typeof url === 'string' && url.startsWith('/')) url = BASE + url;
  else if (typeof url === 'string' && !/^https?:/i.test(url)) url = BASE + '/' + url.replace(/^\/+/, '');
  const ub = pick(o, K.ubic);
  const ubic = typeof ub === 'object' && ub ? Object.values(ub).filter((v) => typeof v === 'string').join(', ') : ub;
  return {
    url: typeof url === 'string' ? url : null,
    titulo: limpia(pick(o, K.titulo) || ''),
    precio: asNum2(pick(o, K.precio)), moneda: limpia(pick(o, K.moneda) || 'MXN') || 'MXN',
    ubicacion: limpia(ubic || ''),
    m2_construccion: asNum2(pick(o, K.constr)), m2_terreno: asNum2(pick(o, K.terreno)),
    recamaras: asNum2(pick(o, K.rec)), banos: asNum2(pick(o, K.banos)), estacionamientos: asNum2(pick(o, K.estac)),
    tipo: tipo || null, operacion: oper,
    imagen: typeof img === 'string' ? img : null,
    lat: asNum2(pick(o, K.lat)), lng: asNum2(pick(o, K.lng)),
    _via: 'json',
  };
}
function walk(node, out, depth = 0) {
  if (!node || depth > 12) return;
  if (Array.isArray(node)) { for (const x of node) walk(x, out, depth + 1); return; }
  if (typeof node !== 'object') return;
  if (esPropiedad(node)) out.push(mapProp(node));
  for (const k of Object.keys(node)) walk(node[k], out, depth + 1);
}
function blobsJSON(html) {
  const blobs = []; let m;
  const reScript = /<script[^>]*(?:id\s*=\s*["']__NEXT_DATA__["']|type\s*=\s*["']application\/json["'])[^>]*>([\s\S]*?)<\/script>/gi;
  while ((m = reScript.exec(html))) blobs.push(m[1]);
  const reWin = /(?:window\.__NUXT__|__INITIAL_STATE__|__APOLLO_STATE__)\s*=\s*(\{[\s\S]*?\})\s*<\/script>/gi;
  while ((m = reWin.exec(html))) blobs.push(m[1]);
  return blobs;
}
function parseEmbeddedJson(html) {
  const out = [];
  for (const b of blobsJSON(html)) { try { walk(JSON.parse(b), out); } catch { /* no-JSON: ignorar */ } }
  const seen = new Set();
  return out.filter((x) => { const k = llave(x); if (seen.has(k)) return false; seen.add(k); return true; });
}

/* Estrategia 0 (la buena): window.REP_LOG_APP_PROPS.results — el sitio embebe
   las 100 propiedades de la página con 90 campos cada una. Es la plataforma
   Viviendi/21online que usa century21mexico.com. */
function mapRep(p) {
  const oper = /renta|rent/i.test(p.tipoOperacion || p.tipoOperacionTrans || '') ? 'renta'
    : /venta|sale/i.test(p.tipoOperacion || p.tipoOperacionTrans || '') ? 'venta' : null;
  let url = p.urlCorrectaPropiedad || null;
  if (typeof url === 'string' && url.startsWith('/')) url = BASE + url;
  const ubic = [p.calle, p.colonia, p.municipio, p.estado, p.pais].map((v) => (v == null ? '' : String(v).trim())).filter(Boolean).join(', ');
  const foto = p.fotos && Array.isArray(p.fotos.propiedadThumbnail) ? p.fotos.propiedadThumbnail[0] : (p.foto || null);
  return {
    id: p.idPropiedadesDB || p.id || null,
    url, titulo: limpia(p.encabezado || ''),
    precio: numero(p.precio), moneda: p.moneda || 'MXN',
    ubicacion: ubic || null,
    colonia: p.colonia || null, municipio: p.municipio || null, estado: p.estado || null, pais: p.pais || null,
    m2_construccion: numero(p.m2C), m2_terreno: numero(p.m2T),
    recamaras: numero(p.recamaras), banos: numero(p.banos), estacionamientos: numero(p.estacionamientos),
    tipo: limpia(p.tipoPropiedadTrans || p.tipoPropiedad || '') || null, operacion: oper,
    imagen: typeof foto === 'string' ? foto : null,
    lat: numero(p.lat), lng: numero(p.lon ?? p.lng),
    afiliado: limpia(p.nombreAfiliado || '') || null,
    _via: 'replog',
  };
}
function parseRepLog(html) {
  const m = html.match(/REP_LOG_APP_PROPS\s*=\s*\{/);
  if (!m) return [];
  const rk = html.indexOf('"results"', m.index);
  if (rk < 0) return [];
  const ab = html.indexOf('[', rk);
  if (ab < 0) return [];
  // extracción balanceada saltando el contenido de las cadenas
  let depth = 0, ae = -1;
  for (let k = ab; k < html.length; k++) {
    const c = html[k];
    if (c === '"') { k++; while (k < html.length && html[k] !== '"') { if (html[k] === '\\') k++; k++; } continue; }
    if (c === '[') depth++;
    else if (c === ']') { if (--depth === 0) { ae = k + 1; break; } }
  }
  if (ae < 0) return [];
  let arr;
  try { arr = JSON.parse(html.slice(ab, ae)); } catch { return []; }
  return Array.isArray(arr) ? arr.map(mapRep).filter((x) => x.precio && x.precio >= 1000) : [];
}

function parsePagina(html) {
  const rep = parseRepLog(html);
  if (rep.length) return rep; // fuente oficial embebida: úsala directo
  const cands = [parseEmbeddedJson(html), parseJsonLd(html), parseVentanas(html)]
    .sort((a, b) => b.length - a.length);
  return cands[0].filter((x) => x.precio && x.precio >= 1000);
}

const llave = (x) => x.url || [x.titulo, x.precio, x.ubicacion].join('|');

/* Estados de México (slugs del portal). El filtro en-pais_mexico ya limita a
   México; recorrer estado por estado garantiza cobertura completa sin toparse
   con el tope de resultados del buscador. */
const ESTADOS_MX = ['aguascalientes', 'baja-california', 'baja-california-sur', 'campeche', 'chiapas', 'chihuahua', 'ciudad-de-mexico', 'coahuila', 'colima', 'durango', 'estado-de-mexico', 'guanajuato', 'guerrero', 'hidalgo', 'jalisco', 'michoacan', 'morelos', 'nayarit', 'nuevo-leon', 'oaxaca', 'puebla', 'queretaro', 'quintana-roo', 'san-luis-potosi', 'sinaloa', 'sonora', 'tabasco', 'tamaulipas', 'tlaxcala', 'veracruz', 'yucatan', 'zacatecas'];
const urlEstado = (slug, p) => `${BASE}/v/resultados/en-pais_mexico/en-estado_${slug}/pagina_${p}`;
const urlMx = (p) => `${BASE}/v/resultados/en-pais_mexico/pagina_${p}`;
// ?json=true hace que el servidor devuelva el JSON de resultados YA filtrado
// (México por estado) en vez de la página con las "exclusivas" por defecto.
const urlEstadoJson = (slug, p) => `${urlEstado(slug, p)}?json=true`;
async function fetchJSON(url) { return JSON.parse(await fetchText(url)); }

/* ---------- sub-filtro por municipio (modo PROFUNDO) ----------
   El buscador del portal topa los resultados de un estado grande (CDMX, Edomex,
   Quintana Roo) en ~1,500-2,400 aunque haya más. La respuesta JSON no trae la
   lista de municipios (aggregations.ubicacion viene vacía), así que:
     1) tomamos los municipios que YA vimos en el scrapeo plano, y
     2) volvemos a pedir el estado filtrando por cada municipio. Cada subconjunto
        cae por debajo del tope, y la suma cubre el estado completo.
   El segmento de la ruta (en-municipio_ / en-ciudad_ / en-delegacion_ /
   en-alcaldia_) cambia entre plataformas, así que lo autodetectamos validando
   que los resultados devueltos caigan en el municipio pedido. */
const slugMun = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const MUN_SEG_CANDS = ['municipio', 'ciudad', 'delegacion', 'alcaldia', 'municipality', 'localidad'];
let MUN_SEG_HINT = null; // segmento que funcionó antes: pruébalo primero
const urlEstadoMunJson = (est, seg, mun, p) =>
  `${BASE}/v/resultados/en-pais_mexico/en-estado_${est}/en-${seg}_${mun}/pagina_${p}?json=true`;

async function detectMunSeg(est, munSlug) {
  const orden = MUN_SEG_HINT ? [MUN_SEG_HINT, ...MUN_SEG_CANDS.filter((s) => s !== MUN_SEG_HINT)] : MUN_SEG_CANDS;
  for (const seg of orden) {
    try {
      const d = await fetchJSON(urlEstadoMunJson(est, seg, munSlug, 1));
      const items = (d.results || []).map(mapRep).filter((x) => x.precio && x.precio >= 1000);
      if (items.length) {
        const match = items.filter((x) => slugMun(x.municipio) === munSlug).length;
        if (match >= Math.min(3, items.length)) { MUN_SEG_HINT = seg; return seg; }
      }
    } catch { /* siguiente candidato */ }
    await pausa();
  }
  return null;
}

/* Barre todos los municipios de un estado; escribe solo las propiedades nuevas
   (dedup contra `vistos`). Devuelve cuántas nuevas ganó. */
async function pasadaMunicipios(est, munVistos, nd, vistos, claveDe) {
  if (!munVistos.size) return 0;
  const primero = [...munVistos.keys()][0];
  const seg = await detectMunSeg(est, primero);
  if (!seg) { console.log(`     ⚠ ${est}: ningún filtro de municipio respondió; lo dejo con la pasada plana.`); return 0; }
  console.log(`     🔧 filtro activo: en-${seg}_`);
  let ganadas = 0;
  for (const [ms, mn] of munVistos) {
    let nMun = 0, totMun = null;
    for (let p = 1; p <= 200; p++) {
      let d;
      try { d = await fetchJSON(urlEstadoMunJson(est, seg, ms, p)); }
      catch (e) { console.log(`       ✗ ${mn} pág ${p}: ${e.message}`); break; }
      if (totMun == null) totMun = parseInt(String(d.totalHits || '').replace(/[^\d]/g, '')) || 0;
      const items = (d.results || []).map(mapRep).filter((x) => x.precio && x.precio >= 1000);
      const nuevas = items.filter((x) => !vistos.has(claveDe(x)));
      nuevas.forEach((x) => { vistos.add(claveDe(x)); nd.write(JSON.stringify({ ...x, _estado: est, _municipio: ms, _profundo: 1 }) + '\n'); });
      ganadas += nuevas.length; nMun += nuevas.length;
      await pausa();
      if (items.length === 0) break;
      if (totMun && p * 100 >= totMun) break;
    }
    if (nMun) console.log(`       · ${mn.padEnd(24)} +${nMun}${totMun ? '/' + totMun : ''}`);
  }
  return ganadas;
}

/* ---------- modo MUESTRA ---------- */
async function muestra() {
  const iE = args.indexOf('--estado');
  const estadoPrueba = iE >= 0 ? args[iE + 1] : 'nuevo-leon';
  console.log(`🔎 MODO MUESTRA — API JSON de México (estado: ${estadoPrueba})\n`);
  const url = urlEstadoJson(estadoPrueba, 1);
  console.log('   GET', url);
  let data;
  try { data = await fetchJSON(url); }
  catch (e) { console.log('   ✗ No devolvió JSON válido: ' + e.message + '\n   Súbeme la salida a Claude.'); return; }
  fs.writeFileSync(path.join(OUT, 'muestra_api.json'), JSON.stringify((data.results || []).slice(0, 3), null, 1));

  const items = (data.results || []).map(mapRep).filter((x) => x.precio && x.precio >= 1000);
  const pct = (k) => Math.round((items.filter((x) => x[k] != null).length / (items.length || 1)) * 100);
  console.log(`\n   Propiedades en la página: ${items.length}`);
  console.log(`   totalHits del estado: ${data.totalHits || '?'}`);
  console.log(`   Campos → precio ${pct('precio')}% · ubic ${pct('ubicacion')}% · municipio ${pct('municipio')}% · m²C ${pct('m2_construccion')}% · url ${pct('url')}% · foto ${pct('imagen')}%`);
  const grupo = (k) => { const g = {}; items.forEach((x) => { const v = x[k] || '?'; g[v] = (g[v] || 0) + 1; }); return Object.entries(g).map(([v, n]) => `${v} ${n}`).join(' · '); };
  console.log('   Por país: ' + grupo('pais'));
  console.log('   Por operación: ' + grupo('operacion'));
  console.log('\n   Ejemplos:');
  for (const x of items.slice(0, 3)) console.log(`   · $${(x.precio || 0).toLocaleString('es-MX')} ${x.moneda} — ${x.tipo || '?'} ${x.operacion || ''} — ${x.municipio || ''}, ${x.estado || ''}`);

  const esMx = items[0] && items[0].pais === 'México';
  const ok = items.length >= 10 && pct('precio') >= 90 && esMx;
  console.log(ok
    ? '\n✅ LISTO PARA TODO → corre:  node tools/c21-scraper.mjs todo'
    : !esMx && items.length
      ? '\n⚠️  Trae propiedades pero NO de México (' + (items[0] && items[0].pais) + '). Avísame.'
      : '\n⚠️  Respuesta incompleta. Súbeme c21_out/muestra_api.json a Claude.');
}

/* ---------- modo TODO ---------- */
async function todo() {
  const iEst = args.indexOf('--estado');
  const soloEstado = iEst >= 0 ? args[iEst + 1] : null;
  const hastaPag = flag('hasta', 400); // tope de páginas por estado (red de seguridad)
  const ndPath = path.join(OUT, 'listados.ndjson');
  const stPath = path.join(OUT, 'estado.json');
  const claveDe = (x) => (x.id ? 'id:' + x.id : llave(x));

  // reanudación: qué llaves ya tenemos y en qué estado/página nos quedamos
  const vistos = new Set();
  if (fs.existsSync(ndPath)) {
    for (const l of fs.readFileSync(ndPath, 'utf8').split('\n')) {
      if (!l.trim()) continue;
      try { vistos.add(claveDe(JSON.parse(l))); } catch {}
    }
  }
  const estados = soloEstado ? [soloEstado] : ESTADOS_MX;
  let startIdx = 0, startPag = 1;
  if (!soloEstado && fs.existsSync(stPath)) {
    try { const st = JSON.parse(fs.readFileSync(stPath, 'utf8')); startIdx = st.estadoIdx || 0; startPag = st.pagina || 1; } catch {}
  }
  console.log(`🚜 MODO TODO — México, ${estados.length} estado(s); reanudando en "${estados[startIdx] || '—'}" pág ${startPag}; ya guardadas: ${vistos.size}`);
  console.log('   Cortesía: ~1 página/seg. Puedes cortar con Ctrl+C y reanudar con el mismo comando.\n');

  const nd = fs.createWriteStream(ndPath, { flags: 'a' });
  let nuevasTotal = 0, debugGuardados = 0;
  const t0 = Date.now();

  for (let ei = startIdx; ei < estados.length; ei++) {
    const slug = estados[ei];
    const desdeP = ei === startIdx ? startPag : 1;
    let vacias = 0, nEstado = 0, totalEstado = null;
    for (let p = desdeP; p <= hastaPag; p++) {
      let data;
      try { data = await fetchJSON(urlEstadoJson(slug, p)); }
      catch (e) { console.log(`   ✗ ${slug} pág ${p}: ${e.message}`); break; }
      if (totalEstado == null) totalEstado = parseInt(String(data.totalHits || '').replace(/[^\d]/g, '')) || 0;
      const items = (data.results || []).map(mapRep).filter((x) => x.precio && x.precio >= 1000);
      const nuevas = items.filter((x) => !vistos.has(claveDe(x)));
      nuevas.forEach((x) => { vistos.add(claveDe(x)); nd.write(JSON.stringify({ ...x, _estado: slug, _pagina: p }) + '\n'); });
      nuevasTotal += nuevas.length; nEstado += nuevas.length;
      fs.writeFileSync(stPath, JSON.stringify({ estadoIdx: ei, pagina: p + 1, estado: slug, total: vistos.size, actualizado: new Date().toISOString() }));
      vacias = items.length === 0 ? vacias + 1 : 0;
      await pausa();
      if (items.length === 0 && vacias >= 1) break;      // sin resultados → fin del estado
      if (totalEstado && p * 100 >= totalEstado) break;   // ya cubrimos su total
    }
    const min = ((Date.now() - t0) / 60000).toFixed(1);
    console.log(`   ✓ ${slug.padEnd(18)} +${nEstado}${totalEstado ? '/' + totalEstado : ''}  ·  total ${vistos.size}  ·  ${min} min`);
    fs.writeFileSync(stPath, JSON.stringify({ estadoIdx: ei + 1, pagina: 1, total: vistos.size, actualizado: new Date().toISOString() }));
  }
  nd.end();
  void debugGuardados;
  consolidar();
  // Sugerir la pasada profunda si algún estado quedó cerca del tope del buscador.
  console.log('\n   💡 Para superar el tope en estados grandes (CDMX, Edomex, Q. Roo):');
  console.log('      node tools/c21-scraper.mjs profundo');
}

/* Consolida el ndjson en listados.json + listados.csv y resume. Lo usan tanto
   el modo TODO como el modo PROFUNDO (comparten el mismo respaldo ndjson). */
function consolidar() {
  const ndPath = path.join(OUT, 'listados.ndjson');
  const todos = fs.readFileSync(ndPath, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  fs.writeFileSync(path.join(OUT, 'listados.json'), JSON.stringify(todos));
  const cols = ['id', 'url', 'titulo', 'precio', 'moneda', 'operacion', 'tipo', 'ubicacion', 'colonia', 'municipio', 'estado', 'pais', 'm2_construccion', 'm2_terreno', 'recamaras', 'banos', 'estacionamientos', 'imagen', 'lat', 'lng', 'afiliado'];
  const esc = (v) => v == null ? '' : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v);
  fs.writeFileSync(path.join(OUT, 'listados.csv'), '﻿' + cols.join(',') + '\n' + todos.map((x) => cols.map((c) => esc(x[c])).join(',')).join('\n'));

  const ventas = todos.filter((x) => x.operacion === 'venta').length;
  const rentas = todos.filter((x) => x.operacion === 'renta').length;
  const conGeo = todos.filter((x) => x.lat != null).length;
  console.log(`\n✅ TERMINADO: ${todos.length} propiedades`);
  console.log(`   · ${ventas} en venta · ${rentas} en renta · ${todos.length - ventas - rentas} otros`);
  console.log(`   · ${conGeo} con coordenadas (${Math.round(conGeo / (todos.length || 1) * 100)}%)`);
  console.log('   Archivos en c21_out/: listados.json · listados.csv');
  console.log('   👉 Sube listados.json a Claude para integrarlo a BrickBit.');
  return todos.length;
}

/* ---------- modo PROFUNDO ----------
   Lee el respaldo listados.ndjson que ya generó `todo`, detecta los estados que
   toparon el buscador (≥ --umbral propiedades) y los vuelve a barrer municipio
   por municipio para rescatar las que quedaron fuera del tope. No re-scrapea la
   pasada plana: solo agrega lo nuevo. */
async function profundo() {
  const ndPath = path.join(OUT, 'listados.ndjson');
  if (!fs.existsSync(ndPath)) {
    console.log('⚠ No encuentro c21_out/listados.ndjson.\n   Corre primero el inventario base:  node tools/c21-scraper.mjs todo');
    return;
  }
  const umbral = flag('umbral', 900);
  const iEst = args.indexOf('--estado');
  const soloEstado = iEst >= 0 ? args[iEst + 1] : null;
  const claveDe = (x) => (x.id ? 'id:' + x.id : llave(x));

  // Reconstruir lo ya scrapeado: llaves vistas + municipios por estado.
  const vistos = new Set();
  const munPorEstado = new Map();   // estadoSlug -> Map(munSlug -> nombre)
  const countPorEstado = new Map(); // estadoSlug -> nº propiedades ya guardadas
  for (const l of fs.readFileSync(ndPath, 'utf8').split('\n')) {
    if (!l.trim()) continue;
    let x; try { x = JSON.parse(l); } catch { continue; }
    vistos.add(claveDe(x));
    const est = x._estado || slugMun(x.estado);
    if (!est) continue;
    countPorEstado.set(est, (countPorEstado.get(est) || 0) + 1);
    if (x.municipio) {
      if (!munPorEstado.has(est)) munPorEstado.set(est, new Map());
      const ms = slugMun(x.municipio);
      if (!munPorEstado.get(est).has(ms)) munPorEstado.get(est).set(ms, x.municipio);
    }
  }

  let objetivos = [...munPorEstado.keys()];
  if (soloEstado) objetivos = objetivos.filter((e) => e === soloEstado);
  else objetivos = objetivos.filter((e) => (countPorEstado.get(e) || 0) >= umbral);
  objetivos.sort((a, b) => (countPorEstado.get(b) || 0) - (countPorEstado.get(a) || 0));

  console.log('🔬 MODO PROFUNDO — sub-filtro por municipio para superar el tope del buscador.');
  console.log(`   Base: ${vistos.size} propiedades ya scrapeadas.`);
  console.log(`   Estados objetivo (≥${umbral} c/u)${soloEstado ? ` [solo ${soloEstado}]` : ''}: ` +
    (objetivos.map((e) => `${e}(${countPorEstado.get(e)})`).join(', ') || 'ninguno'));
  if (!objetivos.length) {
    console.log('   Nada que profundizar. Prueba --estado <slug> o baja el umbral con --umbral 400.');
    return;
  }
  console.log('   Cortesía: ~1 página/seg. Puedes cortar con Ctrl+C y reanudar con el mismo comando.\n');

  const nd = fs.createWriteStream(ndPath, { flags: 'a' });
  const t0 = Date.now();
  let ganadasTotal = 0;
  for (const est of objetivos) {
    const munVistos = munPorEstado.get(est) || new Map();
    console.log(`   ▸ ${est} — ${munVistos.size} municipios a barrer (base ${countPorEstado.get(est)})`);
    const g = await pasadaMunicipios(est, munVistos, nd, vistos, claveDe);
    ganadasTotal += g;
    console.log(`   ✓ ${est}: +${g} nuevas · total ${vistos.size} · ${((Date.now() - t0) / 60000).toFixed(1)} min\n`);
  }
  nd.end();
  consolidar();
  console.log(`\n🔬 PROFUNDO TERMINADO: +${ganadasTotal} propiedades nuevas · total ${vistos.size}`);
}

/* ---------- main ---------- */
const runner = modo === 'todo' ? todo : modo === 'profundo' ? profundo : muestra;
runner().catch((e) => {
  console.error('\n💥 Error:', e.message);
  console.error('   Puedes reanudar con el mismo comando (guarda el progreso en c21_out/).');
  process.exit(1);
});
