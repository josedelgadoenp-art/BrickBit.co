"""Keep static city pages and offline snapshots aligned with canonical JSON."""
from pathlib import Path
import html
import json
import re
import unicodedata
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
esc = html.escape


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()).strip('-')


def money(value):
    return f'${value:,.0f}'


def percent(value):
    return f'{value:+.1f}%'


def city_page(z, forecast, generated):
    name = z['nombre']
    safe = esc(name)
    url = 'https://brickbit.co/zona/' + slug(name) + '.html'
    growth5 = (forecast['5']['f'] - 1) * 100
    yield_class = '' if z['fuentes']['yield'].lower().startswith('real:') else 'amber'
    description = f'Explora {name}: plusvalía histórica SHF, referencia derivada de precio y escenarios inmobiliarios con sus fuentes y límites.'
    faqs = [
        (f'¿Qué representa el precio por m² en {name}?', f'La referencia de {money(z["precio_m2"])} por m² se deriva de la mediana estatal de vivienda SHF y la superficie media ENVI 2020. No es un precio observado de transacción ni la valuación de una propiedad.'),
        (f'¿Cuál es el pronóstico para {name}?', f'El escenario del modelo a cinco años es {percent(growth5)} de apreciación acumulada. Es una extrapolación sin validación, no un rendimiento garantizado.'),
        ('¿Cómo puedo evaluar una inversión?', 'Abre el analizador, introduce el precio y la renta del inmueble y ajusta el financiamiento, la vacancia y los costos. Compara escenarios y verifica los supuestos con sus fuentes.')
    ]
    structured = {'@context':'https://schema.org', '@type':'FAQPage', 'mainEntity':[
        {'@type':'Question', 'name':q, 'acceptedAnswer':{'@type':'Answer', 'text':a}} for q,a in faqs]}
    bars = ''
    maxgrowth = max(abs((v['f']-1)*100) for v in forecast.values()) or 1
    for horizon in [1,3,5,10]:
        f = forecast[str(horizon)]
        growth = (f['f']-1)*100
        bars += f'''<div class="forecast-row"><div><b>{horizon} año{'s' if horizon>1 else ''}</b><small>{'Extrapolación sin validar' if horizon>3 else 'Evaluación retrospectiva disponible'}</small></div><div class="forecast-track" aria-hidden="true"><span style="width:{max(1,abs(growth)/maxgrowth*100):.1f}%"></span></div><strong class="amber">{percent(growth)}</strong></div>'''
    return f'''<!doctype html>
<html lang="es-MX"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe} · Panorama inmobiliario | BrickBit</title><meta name="description" content="{esc(description,quote=True)}"><link rel="canonical" href="{url}"><meta property="og:title" content="{safe} · Panorama inmobiliario"><meta property="og:description" content="{esc(description,quote=True)}"><meta property="og:url" content="{url}"><meta property="og:image" content="https://brickbit.co/og-image.png"><meta name="theme-color" content="#0b111b"><link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/zona/zona.css"><link rel="stylesheet" href="/assets/brickbit-ui.css?v=20260911"><script type="application/ld+json">{json.dumps(structured,ensure_ascii=False).replace('<',chr(92)+'u003c')}</script></head>
<body class="bb-product bb-zone"><a class="bb-skip" href="#contenido">Saltar al contenido</a><div class="wrap">
<header class="nav"><a class="brand" href="/">brickbit</a><nav class="nav-links" aria-label="Plataforma"><a href="/zona/index.html">Todas las ciudades</a><a href="/mapa.html">Mapa</a><a href="/panel.html">Mi BrickBit</a></nav></header>
<main id="contenido"><div class="zone-heading"><div><span class="kicker">México / Panorama de ciudad</span><h1>{safe}</h1><p class="lead">Historia, contexto y escenarios para tu próxima decisión.</p></div><a class="btn btn-primary" href="/analizador.html?zona={quote(name)}">Analizar inversión ↗</a></div>
<div class="kpis"><div class="kpi"><div class="k">Referencia / m² · est.</div><div class="v amber">{money(z['precio_m2'])}</div><div class="s">Derivada de SHF / ENVI</div></div><div class="kpi"><div class="k">Plusvalía histórica</div><div class="v">{percent(z['plusvalia'])}</div><div class="s">Variación anual · SHF</div></div><div class="kpi"><div class="k">Rendimiento de zona</div><div class="v {yield_class}">{z['yield']:.1f}%</div><div class="s">Referencia de renta; no del inmueble</div></div><div class="kpi"><div class="k">Volatilidad histórica</div><div class="v">{z.get('volatilidad_anual',0):.1f}%</div><div class="s">Indicador histórico del modelo</div></div></div>
<div class="zone-layout"><section class="card" aria-labelledby="forecast-title"><span class="kicker">Escenarios del modelo · origen 2026</span><h2 id="forecast-title">El tiempo cambia el panorama.</h2><p class="lead">Apreciación acumulada estimada. Compara horizontes antes de tomar una decisión.</p>{bars}<div class="zone-range"><span>Valor proyectado a 5 años, est.</span><b>{money(z['precio_m2']*forecast['5']['f'])} / m²</b><small>Rango del modelo: {money(z['precio_m2']*forecast['5']['lo'])}–{money(z['precio_m2']*forecast['5']['hi'])} / m². Horizonte extrapolado.</small></div><p class="note">Los intervalos tienen un nivel nominal del 90%. Cobertura retrospectiva observada: 91.5% a un año y 86.6% a tres años. Las métricas incluyen el periodo de calibración. <a href="/index.html#validacion">Ver metodología ↗</a></p></section>
<aside class="card zone-context"><span class="kicker">Contexto y fuentes</span><h2>Lee detrás de la cifra.</h2><dl><dt>Fase del ciclo · derivada</dt><dd>{esc(z['ciclo'])}</dd><dt>Oportunidad · clasificación derivada</dt><dd>{esc(z['oportunidad'])}</dd><dt>Mediana estatal de vivienda SHF</dt><dd>{money(z.get('valor_mediano_vivienda_shf',0))}</dd><dt>Superficie media de referencia</dt><dd>{z.get('superficie_media_m2',0):.1f} m²</dd></dl><p class="note">Plusvalía: {esc(z['fuentes']['plusvalia'])}. Rendimiento: {esc(z['fuentes']['yield'])}. Pronóstico generado el {esc(generated)}.</p><p class="note amber">El precio/m² derivado no sustituye comparables ni un avalúo. Las cifras de zona no describen por sí solas un inmueble.</p></aside></div>
<section class="zone-faq"><h2>Para interpretar este mercado</h2><dl class="faq">{''.join('<dt>'+esc(q)+'</dt><dd>'+esc(a)+'</dd>' for q,a in faqs)}</dl></section>
<div class="cta-row"><a class="btn btn-primary" href="/analizador.html?zona={quote(name)}">Evaluar mis supuestos ↗</a><a class="btn btn-ghost" href="/zona/index.html">Explorar otra ciudad</a></div></main><footer>© 2026 BrickBit · Información orientativa. <a href="/aviso-de-privacidad">Aviso de privacidad</a></footer></div></body></html>'''


def sync():
    states = json.loads((ROOT / 'data/estados.json').read_text())['estados']
    forecast = json.loads((ROOT / 'data/forecast.json').read_text())
    for z in states:
        (ROOT / 'zona' / (slug(z['nombre'])+'.html')).write_text(city_page(z,forecast['zonas'][z['nombre']],forecast['meta']['generado']))
    zones = [{**{k:z[k] for k in ['nombre','lat','lng','precio_m2','plusvalia']},'yld':z['yield']} for z in states]
    encoded = json.dumps(zones,ensure_ascii=False,separators=(',',':'))
    (ROOT / 'zonas.js').write_text('/* Generated from data/estados.json; price/m² is a derived reference. */\nwindow.BRICKBIT_ZONES = '+encoded+';\n')
    path = ROOT / 'zona3d.html'
    path.write_text(re.sub(r'const ZONES = \[[\s\S]*?\];', lambda _: 'const ZONES = '+encoded+';',path.read_text(),count=1))
    path = ROOT / 'index.html'
    payload = json.dumps({'estados':states,'forecast':forecast},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    path.write_text(re.sub(r'(<script id="market-data" type="application/json">)[\s\S]*?(</script>)',lambda m:m[1]+payload+m[2],path.read_text(),count=1))
    print(f'Synchronized {len(states)} city pages and public snapshots')


if __name__ == '__main__':
    sync()
