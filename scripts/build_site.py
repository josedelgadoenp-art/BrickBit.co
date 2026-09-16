"""Build an explicit public distribution without publishing repository source."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for pattern in ('*.html', '*.js', '*.png', '*.ico'):
        for source in ROOT.glob(pattern):
            shutil.copy2(source, DIST / source.name)
    for name in ('robots.txt', 'sitemap.xml'):
        shutil.copy2(ROOT / name, DIST / name)
    for name in ('assets', 'data', 'zona', 'mycouple'):
        shutil.copytree(ROOT / name, DIST / name,
                        ignore=shutil.ignore_patterns('gnp_medicos_sin_pago_directo.txt',
                                                     '*.md', '*.py', '__pycache__', '.*'))
    (DIST / 'docs').mkdir()
    shutil.copy2(ROOT / 'docs/presentacion-brickbit.html', DIST / 'docs')
    print(f'Public distribution: {len(list(DIST.rglob("*")))} entries')


if __name__ == '__main__':
    build()
