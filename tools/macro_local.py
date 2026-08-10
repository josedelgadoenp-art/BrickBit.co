#!/usr/bin/env python3
"""
Trae de Banxico (SIE) los supuestos macro de la pro-forma y los deja en
data/macro.json, para que el analizador deje de usar tasas quemadas.

Banxico bloquea IPs de nube, así que esto se corre en local (igual que
riesgos_local.py y economia_local.py).

Token gratuito: https://www.banxico.org.mx/SieAPIRest/service/v1/token

Uso:
    export BANXICO_TOKEN=xxxxx           # o pásalo como argumento
    python3 tools/macro_local.py

Salida: data/macro.json  (cómmitealo; el sitio es estático)
"""
import json, os, sys, urllib.request, urllib.error
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, 'data', 'macro.json')
API = 'https://www.banxico.org.mx/SieAPIRest/service/v1/series'

# Series del SIE. Si Banxico renombra alguna, se corrige aquí y nada más.
SERIES = {
    'tiie28':   'SF43783',   # TIIE a 28 días
    'objetivo': 'SF61745',   # Tasa objetivo de Banxico
    'fix':      'SF43718',   # Tipo de cambio FIX (USD/MXN)
}
SERIE_INPC = 'SP1'           # INPC general; la inflación anual se calcula abajo

# Diferencial hipotecario sobre la tasa objetivo. Es un SUPUESTO, no un dato:
# el analizador lo marca en ámbar. Ajústalo si tienes mejor referencia.
SPREAD_HIPOTECARIO = 3.5


def _pedir(ruta, token):
    req = urllib.request.Request(API + ruta, headers={'Bmx-Token': token,
                                                      'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['bmx']['series']


def _ultimo(serie):
    """Último dato utilizable de una serie (Banxico manda 'N/E' en días sin dato)."""
    for d in reversed(serie.get('datos') or []):
        if d.get('dato') not in (None, '', 'N/E'):
            return float(d['dato'].replace(',', '')), d['fecha']
    return None, None


def main():
    token = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('BANXICO_TOKEN', '')).strip()
    if not token:
        sys.exit('Falta el token. export BANXICO_TOKEN=xxx  (gratis en '
                 'https://www.banxico.org.mx/SieAPIRest/service/v1/token)')

    out = {'fuente': 'Banxico · Sistema de Información Económica (SIE)',
           'spread_hipotecario_supuesto': SPREAD_HIPOTECARIO}

    # Tasas y tipo de cambio: último dato oportuno.
    ids = ','.join(SERIES.values())
    try:
        series = {s['idSerie']: s for s in _pedir(f'/{ids}/datos/oportuno', token)}
    except urllib.error.HTTPError as e:
        sys.exit(f'Banxico respondió {e.code}. ¿Token válido? ¿IDs de serie correctos?')
    except Exception as e:
        sys.exit(f'No se pudo consultar Banxico: {e}')

    for nombre, sid in SERIES.items():
        val, fecha = _ultimo(series.get(sid, {}))
        if val is None:
            print(f'⚠ sin dato para {nombre} ({sid})')
            continue
        out[nombre] = val
        out[nombre + '_fecha'] = fecha

    # Inflación anual: INPC del último mes contra el mismo mes del año previo.
    hoy = date.today()
    ini = (hoy - timedelta(days=430)).isoformat()
    try:
        inpc = _pedir(f'/{SERIE_INPC}/datos/{ini}/{hoy.isoformat()}', token)[0]
        datos = [d for d in inpc['datos'] if d.get('dato') not in (None, '', 'N/E')]
        if len(datos) >= 13:
            ult = float(datos[-1]['dato'].replace(',', ''))
            hace_un_anio = float(datos[-13]['dato'].replace(',', ''))
            out['inflacion_anual'] = round(100 * (ult / hace_un_anio - 1), 2)
            out['inflacion_fecha'] = datos[-1]['fecha']
        else:
            print('⚠ INPC: no hay 13 meses para calcular la variación anual')
    except Exception as e:
        print(f'⚠ INPC no disponible: {e}')

    # Tasa hipotecaria sugerida = objetivo + spread. Derivada, no observada.
    if 'objetivo' in out:
        out['hipotecaria_est'] = round(out['objetivo'] + SPREAD_HIPOTECARIO, 2)
        out['hipotecaria_metodo'] = f'tasa objetivo Banxico + {SPREAD_HIPOTECARIO} pp (supuesto)'

    out['generado'] = hoy.isoformat()
    with open(SALIDA, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print('✓ data/macro.json')
    for k in ('objetivo', 'tiie28', 'inflacion_anual', 'hipotecaria_est', 'fix'):
        if k in out:
            print(f'  {k:18s} {out[k]}')


if __name__ == '__main__':
    sys.exit(main())
