"""Download the latin subsets of a Google Fonts CSS and rewrite it to local paths.

Keeps the site free of runtime requests to third parties, and keeps the repo
small by dropping the cyrillic/vietnamese/etc. subsets the guides never use.

Usage: python -I tools/getfonts.py <google-css-file> <out_dir>
"""
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KEEP = ('latin', 'latin-ext')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

BLOCK = re.compile(r'/\*\s*([a-z0-9\-\[\]]+)\s*\*/\s*(@font-face\s*\{[^}]*\})',
                   re.I | re.S)


def field(block, name):
    m = re.search(name + r':\s*([^;]+);', block)
    return m.group(1).strip() if m else ''


def main():
    css_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    css = open(css_path, encoding='utf-8').read()

    out = []
    seen = {}
    kept = skipped = 0
    for subset, block in BLOCK.findall(css):
        if subset.lower() not in KEEP:
            skipped += 1
            continue
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        if not url:
            continue
        url = url.group(1)

        fam = field(block, 'font-family').strip("'\"")
        wght = field(block, 'font-weight') or '400'
        style = field(block, 'font-style') or 'normal'
        slug = '%s-%s%s-%s' % (fam.lower().replace(' ', '-'), wght,
                               '-italic' if style == 'italic' else '', subset)
        fname = slug + '.woff2'
        dest = os.path.join(outdir, fname)

        if url not in seen:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with open(dest, 'wb') as fh:
                fh.write(data)
            seen[url] = (fname, len(data))
            print('  %-42s %6.1f KB' % (fname, len(data) / 1024))
        kept += 1

        local = block.replace(url, 'fonts/' + seen[url][0])
        local = re.sub(r"url\(fonts/", "url('fonts/", local)
        local = re.sub(r"\.woff2\)", ".woff2')", local)
        out.append('/* %s */\n%s' % (subset, local))

    css_out = os.path.join(outdir, 'fonts.css')
    header = ('/* Self-hosted subsets of Lora and Silkscreen (SIL Open Font\n'
              '   License 1.1). Both typefaces are used in the source\n'
              '   spreadsheets; see PLAN.md. Latin subsets only. */\n\n')
    with open(css_out, 'w', encoding='utf-8') as fh:
        fh.write(header + '\n\n'.join(out) + '\n')

    total = sum(s for _, s in seen.values())
    print('\nkept %d faces (%d subsets skipped), %d files, %.1f KB total'
          % (kept, skipped, len(seen), total / 1024))
    print('wrote %s' % css_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
