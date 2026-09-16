"""Validate real HTML scripts, internal links and local assets before release."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.scripts, self.refs, self.ids, self.duplicates = [], [], set(), []
        self.active, self.kind, self.buffer = False, '', []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            if a['id'] in self.ids:
                self.duplicates.append(a['id'])
            self.ids.add(a['id'])
        for key in ('src', 'href'):
            if a.get(key):
                self.refs.append(a[key])
        if tag == 'script':
            self.active, self.kind, self.buffer = not a.get('src'), a.get('type', ''), []

    def handle_data(self, data):
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append((self.kind, ''.join(self.buffer)))
            self.active = False


def check():
    paths = sorted(ROOT.glob('*.html')) + sorted((ROOT / 'zona').glob('*.html'))
    paths += [ROOT / 'docs/presentacion-brickbit.html']
    pages = {p: Page(p.read_text()) for p in paths}
    aliases = {'/financial': 'financial.html', '/financial/gmm': 'gmm.html',
               '/financial/analisisfinanciero': 'analisisfinanciero.html',
               '/presentacion': 'docs/presentacion-brickbit.html',
               '/aviso-de-privacidad': 'aviso-de-privacidad.html'}
    errors, scripts = [], 0
    for path, page in pages.items():
        name = str(path.relative_to(ROOT))
        errors.extend(f'{name}: duplicate id {x}' for x in page.duplicates)
        for kind, code in page.scripts:
            if kind in ('application/json', 'application/ld+json', 'importmap'):
                try:
                    json.loads(code)
                except ValueError as e:
                    errors.append(f'{name}: invalid embedded JSON {e}')
                continue
            if kind not in ('', 'module', 'text/javascript'):
                continue
            scripts += 1
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs') as f:
                f.write(code)
                f.flush()
                result = subprocess.run(['node', '--check', f.name], capture_output=True, text=True)
                if result.returncode:
                    errors.append(f'{name}: {result.stderr[:450]}')
        for ref in page.refs:
            url = urlsplit(ref)
            if url.scheme or url.netloc or '${' in ref:
                continue
            if not url.path:
                # Some tool anchors are created dynamically by the application.
                continue
            route = url.path.rstrip('/')
            target = (ROOT / aliases[route]) if route in aliases else ((ROOT / route.lstrip('/')) if route.startswith('/') else path.parent / route)
            if target.is_dir():
                target = target / 'index.html'
            if not target.exists() and not target.suffix:
                target = target.with_suffix('.html')
            if not target.exists():
                errors.append(f'{name}: missing local resource {ref}')
            elif url.fragment and target.resolve() in pages and unquote(url.fragment) not in pages[target.resolve()].ids:
                errors.append(f'{name}: missing destination anchor {ref}')
    for path in [*ROOT.glob('*.js'), *(ROOT / 'assets').glob('brickbit-*.js'),
                 ROOT / 'backend/worker.js', *(ROOT / 'netlify/functions').glob('*.mjs')]:
        scripts += 1
        result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
        if result.returncode:
            errors.append(f'{path.name}: {result.stderr[:450]}')
    print(json.dumps({'pages':len(pages), 'scripts':scripts, 'errors':errors}, ensure_ascii=False, indent=2))
    return not errors


if __name__ == '__main__':
    raise SystemExit(0 if check() else 1)
