#!/usr/bin/env node
/* =============================================================================
   c21-scraper.mjs — Robot de inventario Century 21 México → BrickBit
   Scraping AUTORIZADO por la franquicia (acuerdo BrickBit × Century 21 MX).

   Uso (PowerShell o Terminal, dentro de la carpeta del proyecto):
     node tools/c21-scraper.mjs muestra          ← prueba con 1 página (30 s)
     node tools/c21-scraper.mjs todo             ← inventario completo (~10-25 min)
     node tools/c21-scraper.mjs todo --desde 500 ← reanudar manualmente
     node tools/c21-scraper.mjs todo --hasta 50  ← límite de páginas (pruebas)

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
  const m = String(s).replace(/,/g, '').match(/[\d.]+/);
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

function parsePagina(html) {
  const ld = parseJsonLd(html);
  const vent = parseVentanas(html);
  // usa la estrategia que más encontró; si empatan, combina por url
  const items = vent.length >= ld.length ? vent : ld;
  // filtra falsos positivos obvios (sin precio o precio ridículo)
  return items.filter((x) => x.precio && x.precio >= 1000);
}

const llave = (x) => x.url || [x.titulo, x.precio, x.ubicacion].join('|');

/* ---------- modo MUESTRA ---------- */
async function muestra() {
  console.log('🔎 MODO MUESTRA — 1 página de resultados\n');
  const url = `${BASE}/v/resultados/pagina_1`;
  console.log('   GET', url);
  const html = await fetchText(url);
  fs.writeFileSync(path.join(OUT, 'muestra_pagina1.html'), html);
  const items = parsePagina(html);
  const tot = html.match(/([\d.,]{4,})\s*(?:propiedades|inmuebles|resultados)/i);
  const pct = (k) => Math.round((items.filter((x) => x[k] != null).length / (items.length || 1)) * 100);
  console.log(`\n   Propiedades detectadas en la página: ${items.length}`);
  if (tot) console.log(`   El sitio menciona un total de: ${tot[1]}`);
  console.log(`   Campos completos → precio ${pct('precio')}% · ubicación ${pct('ubicacion')}% · m² constr ${pct('m2_construccion')}% · tipo ${pct('tipo')}% · url ${pct('url')}% · imagen ${pct('imagen')}%`);
  console.log('\n   Ejemplos:');
  for (const x of items.slice(0, 3)) console.log(`   · $${(x.precio || 0).toLocaleString('es-MX')} ${x.moneda} — ${x.tipo || '?'} ${x.operacion || ''} — ${(x.ubicacion || 's/ubic').slice(0, 60)}`);
  fs.writeFileSync(path.join(OUT, 'muestra_parseado.json'), JSON.stringify(items, null, 1));
  const ok = items.length >= 10 && pct('precio') >= 90 && pct('ubicacion') >= 70;
  console.log(ok
    ? '\n✅ LISTO PARA TODO → corre:  node tools/c21-scraper.mjs todo'
    : '\n⚠️  El parseo se ve incompleto. Sube a Claude estos 2 archivos de la carpeta c21_out: muestra_pagina1.html y muestra_parseado.json — ajusto el robot con la estructura real.');
}

/* ---------- modo TODO ---------- */
async function todo() {
  const desde = flag('desde', null);
  const hasta = flag('hasta', 1600);
  const ndPath = path.join(OUT, 'listados.ndjson');
  const stPath = path.join(OUT, 'estado.json');

  // reanudación
  const vistos = new Set();
  let inicio = 1;
  if (fs.existsSync(ndPath)) {
    for (const l of fs.readFileSync(ndPath, 'utf8').split('\n')) {
      if (!l.trim()) continue;
      try { vistos.add(llave(JSON.parse(l))); } catch {}
    }
  }
  if (fs.existsSync(stPath)) {
    try { inicio = (JSON.parse(fs.readFileSync(stPath, 'utf8')).ultimaPagina || 0) + 1; } catch {}
  }
  if (desde) inicio = desde;
  console.log(`🚜 MODO TODO — desde página ${inicio} (tope ${hasta}); ya guardadas: ${vistos.size}`);
  console.log('   Cortesía: ~1 página/seg. Puedes cortar con Ctrl+C y reanudar con el mismo comando.\n');

  const nd = fs.createWriteStream(ndPath, { flags: 'a' });
  let vacias = 0, nuevasTotal = 0, debugGuardados = 0;
  const t0 = Date.now();

  for (let p = inicio; p <= hasta; p++) {
    let html;
    try { html = await fetchText(`${BASE}/v/resultados/pagina_${p}`); }
    catch (e) { console.log(`   ✗ página ${p}: ${e.message}`); break; }
    const items = parsePagina(html);
    const nuevas = items.filter((x) => !vistos.has(llave(x)));
    nuevas.forEach((x) => { vistos.add(llave(x)); nd.write(JSON.stringify({ ...x, _pagina: p }) + '\n'); });
    nuevasTotal += nuevas.length;
    fs.writeFileSync(stPath, JSON.stringify({ ultimaPagina: p, total: vistos.size, actualizado: new Date().toISOString() }));

    if (items.length === 0 && html.length > 15000 && debugGuardados < 2) {
      fs.writeFileSync(path.join(OUT, `debug_pagina_${p}.html`), html);
      debugGuardados++;
    }
    vacias = nuevas.length === 0 ? vacias + 1 : 0;
    if (p % 10 === 0 || vacias >= 3) {
      const min = ((Date.now() - t0) / 60000).toFixed(1);
      console.log(`   pág ${p} · acumuladas ${vistos.size} (+${nuevasTotal} esta corrida) · ${min} min`);
    }
    if (vacias >= 4) { console.log('\n   4 páginas seguidas sin propiedades nuevas → fin del inventario.'); break; }
    await pausa();
  }
  nd.end();

  // consolidar JSON + CSV
  const todos = fs.readFileSync(ndPath, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  fs.writeFileSync(path.join(OUT, 'listados.json'), JSON.stringify(todos));
  const cols = ['url', 'titulo', 'precio', 'moneda', 'operacion', 'tipo', 'ubicacion', 'm2_construccion', 'm2_terreno', 'recamaras', 'banos', 'estacionamientos', 'mantenimiento', 'imagen', 'lat', 'lng'];
  const esc = (v) => v == null ? '' : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v);
  fs.writeFileSync(path.join(OUT, 'listados.csv'), '﻿' + cols.join(',') + '\n' + todos.map((x) => cols.map((c) => esc(x[c])).join(',')).join('\n'));

  const ventas = todos.filter((x) => x.operacion === 'venta').length;
  console.log(`\n✅ TERMINADO: ${todos.length} propiedades (${ventas} en venta, ${todos.length - ventas} renta/otros)`);
  console.log('   Archivos en c21_out/: listados.json · listados.csv');
  console.log('   👉 Sube listados.json (o el .csv) a Claude para integrarlo a BrickBit.');
}

/* ---------- main ---------- */
(modo === 'todo' ? todo() : muestra()).catch((e) => {
  console.error('\n💥 Error:', e.message);
  console.error('   Puedes reanudar con: node tools/c21-scraper.mjs todo');
  process.exit(1);
});
