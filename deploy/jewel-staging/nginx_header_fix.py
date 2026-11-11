#!/usr/bin/env python3
"""Put the response headers where nginx will actually send them.

The trap
--------
nginx does NOT merge `add_header` across configuration levels. A level
inherits the parent's add_header directives *only if it defines none of its
own*. One `add_header` inside a `location` therefore discards every
`add_header` from the enclosing `server` block for requests that location
handles.

On jewel.mumtaz.digital that meant four headers were silently not sent on any
HTML page:

    add_header Cache-Control $jewel_cache always;                 (server)
    add_header X-Content-Type-Options "nosniff" always;           (server)
    add_header X-Frame-Options "SAMEORIGIN" always;               (server)
    add_header Referrer-Policy "strict-origin-when-cross-origin"; (server)

because `location = /` and `location /` each carried a lone

    add_header X-Robots-Tag "noindex, nofollow" always;

`nginx -t` passes: it is valid configuration that quietly drops directives.
Only fetching the page reveals it.

What this does
--------------
Writes the server-level add_header directives into a snippet and `include`s
that snippet in every location that needs them, so each level carries its own
copy. Locations are chosen conservatively:

  * must already contain an add_header   (otherwise it inherits correctly
                                          and needs no help)
  * must NOT set Cache-Control itself    (/site/ has `expires` plus its own
                                          Cache-Control; a second one would
                                          send the header twice)
  * must NOT contain proxy_pass          (the Odoo proxy's headers are its
                                          own business)

X-Robots-Tag is deliberately left out of the snippet: the locations that want
it already set it, and putting it in both places would duplicate the header.

Usage:  nginx_header_fix.py <config> <snippet-include-path> [--check]
Writes the modified config to stdout. --check only reports what it would do.
"""
import re
import sys

# A literal, not a $variable from a map. The map had to live in the http
# context (/etc/nginx/conf.d), which on this host is SHARED WITH THE LIVE
# C2P CONSOLE -- jewel.mumtaz.digital is a separate site on the production
# VPS, not a separate server. Nothing global is needed: these headers go
# into the HTML-serving locations, where the right value is known.
CACHE_LINE = 'add_header Cache-Control "no-cache, must-revalidate" always;'


def split_blocks(lines, start):
    """Yield (open_index, close_index, header_line) for blocks one level
    below `start`, which must be the index of a line opening a block."""
    depth = 0
    i = start
    inner_start = None
    inner_depth = None
    while i < len(lines):
        line = lines[i]
        opens = line.count('{')
        closes = line.count('}')
        if inner_start is None and depth == 1 and opens:
            inner_start = i
            inner_depth = depth
        depth += opens - closes
        if inner_start is not None and depth == inner_depth:
            yield (inner_start, i, lines[inner_start])
            inner_start = None
        if depth == 0 and i > start:
            return
        i += 1


def find_server_block(lines, server_name):
    """The TLS server block that serves content, not the redirect."""
    best = None
    i = 0
    while i < len(lines):
        if re.match(r'\s*server\s*\{', lines[i]):
            depth = 0
            j = i
            while j < len(lines):
                depth += lines[j].count('{') - lines[j].count('}')
                if depth == 0:
                    break
                j += 1
            body = '\n'.join(lines[i:j + 1])
            if server_name in body and 'return 301' not in body:
                if re.search(r'listen[^;]*443', body) or re.search(r'^\s*root\s', body, re.M):
                    best = (i, j)
                    break
        i += 1
    return best


def main():
    if len(sys.argv) < 3:
        sys.exit('usage: nginx_header_fix.py <config> <include-path> [--check]')
    path, include_path = sys.argv[1], sys.argv[2]
    check = '--check' in sys.argv
    server_name = 'jewel.mumtaz.digital'

    lines = open(path, encoding='utf-8').read().split('\n')
    block = find_server_block(lines, server_name)
    if not block:
        sys.exit(f'no content server block for {server_name}')
    s, e = block

    # Server-level add_header directives: inside the server block but not
    # inside any location within it.
    inner = [(a, b) for a, b, _ in split_blocks(lines, s)]

    def in_location(idx):
        return any(a <= idx <= b for a, b in inner)

    server_headers = [
        lines[i].strip() for i in range(s + 1, e)
        if re.match(r'\s*add_header\s', lines[i]) and not in_location(i)
    ]
    # An earlier version of this tooling inserted a server-level
    #   add_header Cache-Control $jewel_cache always;
    # backed by a map in /etc/nginx/conf.d -- the http context, which on this
    # host is shared with the live C2P console. The map is being removed, so
    # that line would reference an undefined variable and nginx -t would
    # FAIL. Drop it here, and delete it from the config below.
    server_headers = [h for h in server_headers if '$jewel_cache' not in h]
    if not any('Cache-Control' in h for h in server_headers):
        server_headers.append(CACHE_LINE)
    # X-Robots-Tag stays with the locations that set it; see the docstring.
    snippet = [h for h in server_headers if 'X-Robots-Tag' not in h]

    targets = []
    for a, b, head in split_blocks(lines, s):
        if not re.match(r'\s*location\s', head):
            continue
        body = '\n'.join(lines[a:b + 1])
        if 'add_header' not in body:
            continue              # inherits correctly already
        if 'Cache-Control' in body:
            continue              # sets its own; a second would duplicate
        if 'proxy_pass' in body:
            continue              # not ours
        if f'include {include_path}' in body:
            continue              # already done
        targets.append((a, head.strip()))

    if check:
        print('snippet would contain:')
        for h in snippet:
            print('   ', h)
        print('include would be added to:')
        for _, head in targets:
            print('   ', head)
        print('SNIPPET_LINES=%d TARGETS=%d' % (len(snippet), len(targets)))
        return

    out = list(lines)
    # Remove the stale $jewel_cache line (server level only; a location that
    # set its own Cache-Control is left alone).
    for i in range(e, s, -1):
        if '$jewel_cache' in out[i] and not in_location(i):
            del out[i]
            # indices after this shift, but targets are applied in reverse
            # order below and all lie after s, so recompute conservatively.
            targets = [(a - 1 if a > i else a, h) for a, h in targets]
    for a, _ in sorted(targets, reverse=True):
        indent = re.match(r'(\s*)', out[a]).group(1)
        out.insert(a + 1, f'{indent}    include {include_path};')
    sys.stdout.write('\n'.join(out))
    print('\n'.join(snippet), file=sys.stderr)


if __name__ == '__main__':
    main()
