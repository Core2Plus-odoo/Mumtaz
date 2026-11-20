#!/usr/bin/env python3
"""Check every link in the Jewel site, on disk and optionally on the live host.

Why this is worth a script
--------------------------
nginx serves the landing page for any path it does not recognise, so on this
site a broken link does not 404. It silently shows the homepage. A visitor
taps "Pricing", lands back where they started, and concludes the site is
broken or stale — which is exactly what happened on 11 Nov 2026.

So "the link exists in the HTML" is not the question. The questions are
whether the target exists, and whether the live host serves something real
for it.

The preview page's hash router
------------------------------
`website/jewel/preview/index.html` switches screens in JavaScript: it reads
`location.hash`, looks the key up in its `titles` object and clicks the
matching `.navb[data-s=...]`. So `preview/#pos` is a VALID link even though
no element has `id="pos"`.

A naive anchor check reports all eleven of those as broken. This one parses
the router's own key list out of the page and validates against that, which
is why it does not cry wolf.

Usage:
  scripts/check_links.py                               # on-disk only
  scripts/check_links.py --site https://jewel.mumtaz.digital   # also live
  scripts/check_links.py --root website/jewel
"""
import argparse
import html.parser
import pathlib
import re
import sys
from urllib.parse import urldefrag, urlparse


class Doc(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'a' and a.get('name'):
            self.ids.add(a['name'])
        for key in ('href', 'src'):
            if a.get(key):
                self.links.append(a[key].strip())


def parse(path):
    d = Doc()
    d.feed(path.read_text(encoding='utf-8', errors='replace'))
    return d


def router_keys(path):
    """Hash keys the preview page accepts, read from its own titles object."""
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return set()
    m = re.search(r'var titles\s*=\s*\{(.*?)\n\s*\};', text, re.S)
    if not m:
        return set()
    return set(re.findall(r'^\s*([A-Za-z0-9_]+)\s*:\s*\[', m.group(1), re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='website/jewel')
    ap.add_argument('--site', default=None,
                    help='also check this live host for catch-all responses')
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    if not root.is_dir():
        print(f'No such directory: {root}', file=sys.stderr)
        return 2

    docs = {f: parse(f) for f in sorted(root.rglob('*.html'))}
    routers = {f: router_keys(f) for f in docs}

    broken, external, mail = [], set(), set()
    page_targets = set()
    ok_pages = ok_anchors = 0

    for f, doc in docs.items():
        rel = f.relative_to(root)
        for href in doc.links:
            if href.startswith(('http://', 'https://', '//')):
                external.add(href)
                continue
            if href.startswith(('mailto:', 'tel:')):
                mail.add((str(rel), href))
                continue
            if href.startswith('data:') or href in ('#', ''):
                continue

            target, frag = urldefrag(href)

            if not target:                              # same page
                if frag and frag not in doc.ids and frag not in routers.get(f, set()):
                    broken.append((rel, href, f'no id="{frag}" in this page'))
                else:
                    ok_anchors += 1
                continue

            if target.startswith('/'):
                # Absolute path: cannot be resolved against the repo. Record it
                # so the live pass can judge it, and say so rather than guess.
                page_targets.add(target.lstrip('/'))
                continue

            cand = (f.parent / target).resolve()
            if cand.is_dir():
                cand = cand / 'index.html'
            if not cand.exists():
                broken.append((rel, href, 'target does not exist'))
                continue
            ok_pages += 1
            try:
                rel_t = cand.relative_to(root)
                # Probe the real target, not its parent directory. Probing
                # the parent reported /site/img/ as a 404 "ok" while saying
                # nothing about whether the images themselves load.
                if rel_t.name == 'index.html':
                    page_targets.add(str(rel_t.parent) + '/')
                else:
                    page_targets.add(str(rel_t))
            except ValueError:
                pass

            if frag:
                tdoc = docs.get(cand)
                keys = routers.get(cand, set())
                if tdoc is None:
                    ok_anchors += 1
                elif frag in tdoc.ids or frag in keys:
                    ok_anchors += 1
                else:
                    broken.append(
                        (rel, href, f'no id="{frag}" and the page has no such hash key'))

    print(f'Scanned {len(docs)} HTML files under {root}')
    print(f'Resolved: {ok_pages} page links, {ok_anchors} anchors')

    rc = 0
    if broken:
        rc = 1
        print(f'\nBROKEN ({len(broken)}):')
        for f, href, why in broken:
            print(f'  {str(f):34} {href:34} {why}')
    else:
        print('No broken internal links or anchors.')

    if mail:
        print('\nmailto/tel — check for placeholder addresses:')
        for f, href in sorted(mail):
            print(f'  {f:34} {href}')

    if external:
        print('\nExternal hosts:')
        for host in sorted({urlparse(u).netloc for u in external}):
            print(f'  {host}')

    # ---- live pass ---------------------------------------------------------
    if args.site:
        import hashlib
        import time
        import urllib.request

        base = args.site.rstrip('/')

        def get(path):
            url = f'{base}/{path.lstrip("/")}'
            try:
                with urllib.request.urlopen(url, timeout=25) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()
            except Exception as e:                      # noqa: BLE001
                return 0, str(e).encode()

        print(f'\nLive check against {base}')
        _, probe = get(f'catchall-probe-{int(time.time()*1000)}/')
        probe_sha = hashlib.sha256(probe).hexdigest()
        print(f'  catch-all fingerprint: {len(probe)} bytes')

        for t in sorted(page_targets):
            if t in ('./', '.', ''):
                continue
            code, body = get(t)
            if hashlib.sha256(body).hexdigest() == probe_sha:
                print(f'  BROKEN LIVE  /{t:30} {code}  serves the landing page')
                rc = 1
            elif code == 401:
                # Deliberate: the demo system sits behind an allow-list and the
                # page that links it says so.
                print(f'  gated        /{t:30} {code}  auth required (expected)')
            elif code < 200 or code >= 400:
                print(f'  BROKEN LIVE  /{t:30} {code}  not served')
                rc = 1
            else:
                print(f'  ok           /{t:30} {code}  {len(body)} bytes')

    return rc


if __name__ == '__main__':
    sys.exit(main())
