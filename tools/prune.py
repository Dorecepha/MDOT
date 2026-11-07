"""Remove assets no rendered page references.

The extractor writes the whole library — every identity portrait in the
workbooks, every pack in the catalogue — but a published mock-up should only
carry the art its pages actually use. Everything removed here is
regenerable: portraits and icons from the workbooks via extract.py, pack art
from the wiki via fetchpacks.py.

Usage: python -I tools/prune.py <site_dir> [--dry-run]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REF_RE = re.compile(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']')


def main():
    site = sys.argv[1]
    dry = '--dry-run' in sys.argv

    referenced = set()
    pages = 0
    for name in os.listdir(site):
        if not name.endswith('.html'):
            continue
        pages += 1
        with open(os.path.join(site, name), encoding='utf-8') as fh:
            for m in REF_RE.finditer(fh.read()):
                ref = m.group(1).split('?')[0]
                if ref.startswith('assets/'):
                    referenced.add(os.path.normpath(ref))

    assets = os.path.join(site, 'assets')
    kept = removed = 0
    kept_b = removed_b = 0
    drop = []
    for root, _dirs, files in os.walk(assets):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.normpath(os.path.relpath(full, site))
            size = os.path.getsize(full)
            if rel in referenced:
                kept += 1
                kept_b += size
            else:
                removed += 1
                removed_b += size
                drop.append(full)

    if not dry:
        for f in drop:
            os.remove(f)
        for root, dirs, files in os.walk(assets, topdown=False):
            for d in dirs:
                p = os.path.join(root, d)
                if not os.listdir(p):
                    os.rmdir(p)

    missing = sorted(r for r in referenced
                     if not os.path.exists(os.path.join(site, r)))
    mb = lambda n: n / 1e6
    print('pages scanned: %d, asset references: %d' % (pages, len(referenced)))
    print('keep   %4d files  %6.1f MB' % (kept, mb(kept_b)))
    print('%s %4d files  %6.1f MB'
          % ('would remove' if dry else 'removed     ', removed, mb(removed_b)))
    if missing:
        print('\nREFERENCED BUT MISSING (%d):' % len(missing))
        for m in missing[:10]:
            print('  %s' % m)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
