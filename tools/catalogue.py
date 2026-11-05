"""Build the MDOT asset catalogue from both workbooks.

Walks every tab, records each anchored image with its section context, and
resolves EGO-gift icons to canonical names by majority vote across all labelled
occurrences in all tabs. Writes:

    _import/work/catalogue.json     full index, one entry per unique image
    _import/work/contact.html       visual contact sheet for human verification

Usage: python -I tools/catalogue.py <out_dir> <workbook.xlsx> [more.xlsx ...]
"""
import collections
import html
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xlsx import Workbook, index_to_col

# Section headers live in column B (index 1) on every team tab.
SECTION_COL = 1
TIER_RE = re.compile(r'^(I{1,3}|IV|V|-|\d+(\.\d+)?)$')

GIFT_SECTIONS = ('EGO GIFTS', 'FLOORS TO PICK')
SHARED_TABS = ('WELCOME', 'FAQ', 'Teams List', 'ID Catalogue',
               'F11-F15 Packs', 'New Reference Sheet')


def png_dims(blob):
    if blob[:8] == b'\x89PNG\r\n\x1a\n' and blob[12:16] == b'IHDR':
        return struct.unpack('>II', blob[16:24])
    if blob[:2] == b'\xff\xd8':  # JPEG: walk segments for SOF
        i = 2
        while i < len(blob) - 9:
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack('>HH', blob[i + 5:i + 9])
                return w, h
            seg = struct.unpack('>H', blob[i + 2:i + 4])[0]
            i += 2 + seg
    return None


def section_map(cells, maxrow):
    """row -> nearest section header at or above it (column B)."""
    headers = sorted((r, v) for (r, c), v in cells.items() if c == SECTION_COL)
    out = {}
    cur = ''
    hi = 0
    for r in range(maxrow + 1):
        while hi < len(headers) and headers[hi][0] <= r:
            cur = headers[hi][1]
            hi += 1
        out[r] = cur.strip().upper()
    return out


def name_below(cells, row, col, limit=8):
    """First non-tier text in the same column within `limit` rows below."""
    for dr in range(1, limit + 1):
        v = cells.get((row + dr, col))
        if v and not TIER_RE.match(v.strip()):
            return v.strip()
    return None


def main():
    outdir = sys.argv[1]
    books = sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)

    entries = {}   # sha -> record
    blobs = {}     # sha -> bytes

    for path in books:
        wb = Workbook(path)
        book = os.path.splitext(os.path.basename(path))[0]
        for tab in wb.sheets:
            cells = wb.cells(tab)
            imgs = wb.images(tab)
            if not imgs:
                continue
            maxrow = max([r for r, _ in cells] + [i['row'] for i in imgs])
            secs = section_map(cells, maxrow)

            for im in imgs:
                sha = im['sha256']
                if sha not in blobs:
                    blobs[sha] = wb.read_member(im['member'])
                blob = blobs[sha]
                rec = entries.setdefault(sha, {
                    'sha256': sha,
                    'bytes': len(blob),
                    'dims': png_dims(blob),
                    'ext': os.path.splitext(im['member'])[1].lower(),
                    'occurrences': 0,
                    'tabs': set(),
                    'sections': collections.Counter(),
                    'name_votes': collections.Counter(),
                })
                rec['occurrences'] += 1
                rec['tabs'].add('%s/%s' % (book, tab))
                sec = secs.get(im['row'], '')
                rec['sections'][sec] += 1

                if any(g in sec for g in GIFT_SECTIONS) and tab not in SHARED_TABS:
                    nm = name_below(cells, im['row'], im['col'])
                    if nm and len(nm) < 70:
                        rec['name_votes'][nm] += 1

    # classify
    out = []
    for sha, rec in entries.items():
        dims = rec['dims']
        w, h = dims if dims else (0, 0)
        aspect = (w / h) if h else 0
        votes = rec['name_votes']
        top = votes.most_common(1)[0] if votes else None
        total_votes = sum(votes.values())

        if aspect >= 1.8:
            kind = 'source-banner'
        elif 'FOOTAGES' in rec['sections'] and rec['occurrences'] <= 3:
            kind = 'contributor-avatar'
        elif top and top[1] >= 2 and top[1] / total_votes >= 0.6:
            kind = 'gift'
        elif len(rec['tabs']) >= 5 and max(w, h) <= 400:
            kind = 'status-or-ui'
        elif top:
            kind = 'gift-unconfirmed'
        else:
            kind = 'unclassified'

        out.append({
            'sha256': sha,
            'kind': kind,
            'name': top[0] if top else None,
            'name_confidence': round(top[1] / total_votes, 2) if top else None,
            'name_votes': dict(votes.most_common(4)),
            'bytes': rec['bytes'],
            'dims': list(dims) if dims else None,
            'ext': rec['ext'],
            'occurrences': rec['occurrences'],
            'tab_count': len(rec['tabs']),
            'sections': dict(rec['sections'].most_common(3)),
        })

    out.sort(key=lambda r: (r['kind'], -r['occurrences']))

    with open(os.path.join(outdir, 'catalogue.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    # raw blobs, content-addressed, for the organise step
    rawdir = os.path.join(outdir, 'blobs')
    os.makedirs(rawdir, exist_ok=True)
    for sha, blob in blobs.items():
        p = os.path.join(rawdir, sha[:16] + '.png')
        if not os.path.exists(p):
            with open(p, 'wb') as fh:
                fh.write(blob)

    # contact sheet
    by_kind = collections.defaultdict(list)
    for r in out:
        by_kind[r['kind']].append(r)
    parts = ["<!doctype html><meta charset=utf-8><title>MDOT asset contact sheet</title>",
             "<style>body{background:#14110f;color:#e8e0d5;font:13px system-ui;margin:24px}"
             "h2{border-bottom:1px solid #4a3f35;padding-bottom:6px;margin-top:36px}"
             ".g{display:flex;flex-wrap:wrap;gap:10px}"
             ".c{width:118px;background:#1f1a16;border:1px solid #3a322b;border-radius:6px;padding:6px}"
             ".c img{width:104px;height:104px;object-fit:contain;background:#0b0907;border-radius:4px}"
             ".n{font-size:10px;line-height:1.3;margin-top:4px;word-break:break-word}"
             ".m{font-size:9px;color:#8a7f72}</style>"]
    for kind in sorted(by_kind):
        rows = by_kind[kind]
        parts.append("<h2>%s <span class=m>(%d)</span></h2><div class=g>" % (kind, len(rows)))
        for r in rows:
            d = ('%dx%d' % tuple(r['dims'])) if r['dims'] else '?'
            parts.append(
                "<div class=c><img loading=lazy src='blobs/%s.png'>"
                "<div class=n>%s</div><div class=m>%s · %dKB · x%d</div></div>"
                % (r['sha256'][:16], html.escape(r['name'] or '—'), d,
                   r['bytes'] // 1024, r['occurrences']))
        parts.append("</div>")
    with open(os.path.join(outdir, 'contact.html'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(parts))

    counts = collections.Counter(r['kind'] for r in out)
    print("unique images: %d" % len(out))
    for k, v in counts.most_common():
        print("  %-20s %4d" % (k, v))
    named = [r for r in out if r['name']]
    print("resolved names: %d" % len(named))
    return 0


if __name__ == '__main__':
    sys.exit(main())
