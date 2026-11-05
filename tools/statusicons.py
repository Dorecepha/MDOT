"""Identify the status icons (Bleed, Poise, …) among the embedded images.

Inference: a status icon recurs on every team tab whose name contains that
status, and nowhere consistently else. Intersecting the status sets of the
tabs an icon appears on therefore leaves exactly its own status.

Only icons used heavily on a tab count toward that tab, which filters out the
one-off affinity marks that sit beside individual gifts.

Usage: python -I tools/statusicons.py <outdir> <workbook.xlsx> [more.xlsx ...]
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook

STATUSES = ('Bleed', 'Burn', 'Tremor', 'Rupture', 'Sinking', 'Poise', 'Charge')
SHARED = ('WELCOME', 'FAQ', 'Teams List', 'ID Catalogue',
          'F11-F15 Packs', 'New Reference Sheet')
MIN_USES = 3


def tab_statuses(tab):
    found = [s for s in STATUSES if re.search(s, tab, re.I)]
    return set(found)


def main():
    outdir = sys.argv[1]
    books = [Workbook(p) for p in sys.argv[2:]]

    per_tab = collections.defaultdict(collections.Counter)  # sha -> tab -> n
    blob = {}
    for wb in books:
        for tab in wb.sheets:
            if tab in SHARED or not tab_statuses(tab):
                continue
            for im in wb.images(tab):
                per_tab[im['sha256']][tab] += 1
                blob.setdefault(im['sha256'], (wb, im['member']))

    all_tabs = set()
    for wb in books:
        all_tabs |= {t for t in wb.sheets if t not in SHARED and tab_statuses(t)}

    proposals = {}
    for sha, tabs in per_tab.items():
        heavy = [t for t, n in tabs.items() if n >= MIN_USES]
        if len(heavy) < 3:
            continue
        common = set(STATUSES)
        for t in heavy:
            common &= tab_statuses(t)
        if len(common) != 1:
            continue
        status = common.pop()
        # must appear on most tabs carrying that status, else it is incidental
        carriers = [t for t in all_tabs if status in tab_statuses(t)]
        coverage = len(heavy) / max(1, len(carriers))
        proposals.setdefault(status, []).append(
            {'sha256': sha, 'uses': sum(tabs.values()), 'tabs': len(heavy),
             'coverage': round(coverage, 2)})

    os.makedirs(outdir, exist_ok=True)
    out = {}
    for status, cands in sorted(proposals.items()):
        cands.sort(key=lambda c: (-c['coverage'], -c['uses']))
        print('%-9s %d candidate(s)' % (status, len(cands)))
        for i, c in enumerate(cands[:4]):
            wb, member = blob[c['sha256']]
            name = '%s-%d.png' % (status.lower(), i)
            with open(os.path.join(outdir, name), 'wb') as fh:
                fh.write(wb.read_member(member))
            print('   %-16s uses=%-4d tabs=%-3d coverage=%.2f  %s'
                  % (name, c['uses'], c['tabs'], c['coverage'], c['sha256'][:12]))
        out[status] = cands[:4]

    with open(os.path.join(outdir, 'proposals.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
