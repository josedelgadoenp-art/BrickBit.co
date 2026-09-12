import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import backtest_shf as model


class ModelRegression(unittest.TestCase):
    def test_future_observations_do_not_change_past_interval_calibration(self):
        before = model.residuos_hasta(2016, 3)
        original = copy.deepcopy(model.S)
        try:
            for series in model.S.values():
                for year in series:
                    if int(year) > 2016:
                        series[year] *= 10
            self.assertEqual(before, model.residuos_hasta(2016, 3))
        finally:
            model.S = original

    def test_published_metrics_are_reproducible(self):
        self.assertEqual(model.evaluar(), json.loads((ROOT / 'data/backtest_shf.json').read_text()))

    def test_distribution_never_contains_source_or_restricted_medical_list(self):
        import build_site
        build_site.build()
        for name in ['CLAUDE.md', 'app.py', 'supabase_schema.sql', 'backend', 'atlas', 'abak',
                     'netlify', 'tests', 'data/gnp_medicos_sin_pago_directo.txt']:
            self.assertFalse((ROOT / 'dist' / name).exists(), name)
        for name in ['index.html', 'mapa.html', 'assets/brickbit-home.js', 'data/forecast.json',
                     'zona/monterrey.html', 'mycouple/index.html', 'docs/presentacion-brickbit.html']:
            self.assertTrue((ROOT / 'dist' / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
