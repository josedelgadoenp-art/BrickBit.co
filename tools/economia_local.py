#!/usr/bin/env python3
"""
Genera los datos de "Economía de la zona" a nivel MUNICIPIO para el analizador.

Entradas (ya en el repo):
  data/denue_municipal.csv     censo DENUE por municipio (lo produce scripts/ingerir_denue*.py)
  data/mexico_municipios.json  polígonos municipales (GeoJSON)

Salidas:
  data/economia_municipal.json  DENUE + percentiles nacionales por municipio
  data/municipios_shape.json    polígonos compactos para resolver punto → municipio
  data/economia_zonas.json      las 32 zonas, ahora con su percentil nacional

Tras correrlo hay que pegar el contenido de economia_zonas.json en la constante
ECON de analizador.html (va inline para que la tarjeta no dependa de un fetch).

Uso:  python3 tools/economia_local.py
"""
import csv, json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(RAIZ, 'data', *p)

# Precisión de coordenadas: 4 decimales ≈ 11 m. Suficiente para ubicar un
# predio dentro de su municipio y ~6× más ligero que el GeoJSON original.
DEC = 4
ESC = 10 ** DEC


def leer_denue():
    with open(D('denue_municipal.csv'), encoding='utf-8') as fh:
        filas = list(csv.DictReader(fh))
    out = {}
    for r in filas:
        cve = r['cvegeo'].strip().zfill(5)
        neg = int(r['n_estab'] or 0)
        if neg <= 0:
            continue
        com, ser, ind = int(r['comercio'] or 0), int(r['servicios'] or 0), int(r['industria'] or 0)
        base = com + ser + ind
        pct = lambda x: round(100 * x / base) if base else 0
        out[cve] = {
            'n': r['municipio'].strip(),
            'e': r['estado'].strip(),
            'neg': neg,
            'emp': int(r['empleo'] or 0),
            'com': pct(com), 'ser': pct(ser), 'ind': pct(ind),
            'ali': int(r['alimentos'] or 0),
            'res': round(float(r['resiliencia'] or 0), 3),
            'altas': int(r['altas_recientes'] or 0),
            'ind_esp': int(r['indicadoras'] or 0),
        }
    return out


def percentiles(muni):
    """Percentil nacional (0-100) de cada municipio en las métricas que la
    tarjeta muestra. Da contexto: 462,732 negocios no dice nada por sí solo."""
    claves = list(muni)
    metricas = {
        'neg': lambda m: m['neg'],
        'emp': lambda m: m['emp'],
        'res': lambda m: m['res'],
        # Aperturas relativas al tamaño del municipio: mide dinamismo, no volumen.
        'din': lambda m: (m['altas'] / m['neg']) if m['neg'] else 0,
    }
    for nombre, fn in metricas.items():
        pares = sorted(claves, key=lambda c: fn(muni[c]))
        n = len(pares)
        for i, c in enumerate(pares):
            muni[c].setdefault('pct', {})[nombre] = round(100 * i / (n - 1)) if n > 1 else 50
    return muni


def compactar_geo():
    """Polígonos → enteros escalados y aplanados, con bbox para descarte rápido.
    Formato por municipio: [minLng, minLat, maxLng, maxLat, [anillo, ...]]
    donde cada anillo es [lng0, lat0, lng1, lat1, ...] en enteros × 10^DEC."""
    with open(D('mexico_municipios.json'), encoding='utf-8') as fh:
        g = json.load(fh)
    out = {}
    for f in g['features']:
        p = f['properties']
        cve = '%02d%03d' % (int(p['state_code']), int(p['mun_code']))
        geom = f['geometry']
        anillos = geom['coordinates'] if geom['type'] == 'Polygon' else [r for poly in geom['coordinates'] for r in poly]
        planos, xs, ys = [], [], []
        for anillo in anillos:
            plano, prev = [], None
            for lng, lat in anillo:
                x, y = round(lng * ESC), round(lat * ESC)
                if (x, y) == prev:      # descarta vértices repetidos tras redondear
                    continue
                prev = (x, y)
                plano += [x, y]
                xs.append(x); ys.append(y)
            if len(plano) >= 8:          # un anillo útil tiene ≥4 puntos
                planos.append(plano)
        if not planos:
            continue
        out[cve] = [min(xs), min(ys), max(xs), max(ys), planos]
    return out


# Las 32 zonas cuyo nombre no coincide literal con el del DENUE.
# CDMX es agregado de sus 16 alcaldías, así que no tiene clave municipal única.
ZONA_CVE = {
    'Cancún': '23005',        # Benito Juárez, Q.R.
    'La Paz': '03003',        # La Paz, B.C.S. (hay otra La Paz en Edomex)
    'Pachuca': '13048',       # Pachuca de Soto, Hgo.
    'Villahermosa': '27004',  # Centro, Tab.
    'Chilpancingo': '12029',  # Chilpancingo de los Bravo, Gro.
    'Ciudad de México': None,
}


def _norm(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower())
                   if unicodedata.category(c) != 'Mn').strip()


def zonas_con_percentil(muni):
    """Añade a las 32 zonas su percentil nacional, para que la tarjeta dé
    contexto sin descargar el padrón municipal completo."""
    with open(D('economia_zonas.json'), encoding='utf-8') as fh:
        zonas = json.load(fh)
    por_nombre = {}
    for cve, m in muni.items():
        por_nombre.setdefault(_norm(m['n']), []).append(cve)

    # Distribuciones nacionales para ubicar valores agregados (CDMX) que no son
    # un municipio del padrón.
    dist = {k: sorted((m['neg'] if k == 'neg' else m['emp'] if k == 'emp' else
                       m['res'] if k == 'res' else (m['altas'] / m['neg'] if m['neg'] else 0))
                      for m in muni.values()) for k in ('neg', 'emp', 'res', 'din')}

    def pct_de(valor, serie):
        lo, hi = 0, len(serie)
        while lo < hi:
            mid = (lo + hi) // 2
            if serie[mid] < valor: lo = mid + 1
            else: hi = mid
        return round(100 * lo / (len(serie) - 1)) if len(serie) > 1 else 50

    sin_match = []
    for nombre, z in zonas.items():
        cve = ZONA_CVE.get(nombre, '__auto__')
        if cve == '__auto__':
            base = z['muni'].split('(')[0].split(',')[0].split('·')[0].strip()
            cand = por_nombre.get(_norm(base), [])
            cve = cand[0] if len(cand) == 1 else None
        if cve and cve in muni:
            z['cve'] = cve
            z['pct'] = dict(muni[cve]['pct'])
        else:
            # Agregado (CDMX): se ubica su valor dentro de la distribución municipal.
            z['pct'] = {
                'neg': pct_de(z['neg'], dist['neg']),
                'emp': pct_de(z['emp'], dist['emp']),
                'res': pct_de(z['res'], dist['res']),
                'din': pct_de(z['altas'] / z['neg'] if z['neg'] else 0, dist['din']),
            }
            z['agg'] = 1
            if nombre not in ZONA_CVE:
                sin_match.append(nombre)
    if sin_match:
        print('⚠ zonas sin clave municipal (se usó su agregado): %s' % ', '.join(sin_match))
    return zonas


def main():
    muni = percentiles(leer_denue())
    shapes = compactar_geo()

    huerfanos = [c for c in shapes if c not in muni]
    for c in huerfanos:
        del shapes[c]

    with open(D('economia_municipal.json'), 'w', encoding='utf-8') as fh:
        json.dump({'meta': {'fuente': 'DENUE / INEGI', 'municipios': len(muni),
                            'nota': 'pct = percentil nacional 0-100 entre municipios con actividad'},
                   'muni': muni}, fh, ensure_ascii=False, separators=(',', ':'))
    with open(D('municipios_shape.json'), 'w', encoding='utf-8') as fh:
        json.dump({'meta': {'dec': DEC, 'formato': '[minLng,minLat,maxLng,maxLat,[anillo...]] en enteros x10^dec'},
                   'geo': shapes}, fh, separators=(',', ':'))

    zonas = zonas_con_percentil(muni)
    with open(D('economia_zonas.json'), 'w', encoding='utf-8') as fh:
        json.dump(zonas, fh, ensure_ascii=False, separators=(',', ':'))

    for f in ('economia_municipal.json', 'municipios_shape.json', 'economia_zonas.json'):
        print('%-28s %8.1f KB' % (f, os.path.getsize(D(f)) / 1024))
    print('municipios con DENUE: %d · con polígono: %d' % (len(muni), len(shapes)))
    if huerfanos:
        print('descartados (polígono sin DENUE): %d' % len(huerfanos))


if __name__ == '__main__':
    sys.exit(main())
