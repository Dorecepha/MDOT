"""Extract MDOT reference data and one team guide into the site data model.

Produces:
    site/data/identities.json   canonical ID list: sinner, full name, nickname, portrait
    site/data/gifts.json        EGO gift icon -> canonical name index (majority vote)
    site/data/teams/<slug>.json one team guide
    site/assets/<category>/     deduplicated, slugged image files

Usage:
    python -I tools/extract.py <site_dir> <team-tab> <workbook.xlsx> [more.xlsx ...]
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from xlsx import Workbook, index_to_col

REF_TAB = 'New Reference Sheet'
TIER_RE = re.compile(r'^(I{1,3}|IV|V|-)$')
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5}

# The sheet only uses Easy/Medium/Hard today, spaced evenly across a 5-bar
# scale so finer tiers can be slotted in later without redrawing anything.
DIFFICULTY_LEVELS = {
    'very easy': 1, 'easy': 1, 'medium': 3, 'normal': 3,
    'hard': 5, 'very hard': 5,
}
DIFFICULTY_MAX = 5
# The sheet's bullet glyph survives export as a replacement char; strip that
# plus the usual bullet/dash prefixes so notes render as clean list items.
BULLET_RE = re.compile(r'^[\s•●▪◆·∙–—\-•�]+')

SHARED_TABS = ('WELCOME', 'FAQ', 'Teams List', 'ID Catalogue',
               'F11-F15 Packs', 'New Reference Sheet')


def slugify(s):
    s = s.lower().strip()
    s = s.replace('&', ' and ')
    s = re.sub(r"[''‘’]", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-') or 'unnamed'


def clean(s):
    """Normalise whitespace and the mojibake bullet the sheet uses."""
    if not s:
        return s
    s = s.replace('�', '•').replace(' ', ' ')
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in s.split('\n')]
    return '\n'.join(ln for ln in lines if ln).strip()


def bullets(s):
    """Split a notes cell into individual bullet strings."""
    s = clean(s)
    if not s:
        return []
    out = []
    for ln in s.split('\n'):
        ln = BULLET_RE.sub('', ln).strip()
        if ln:
            out.append(ln)
    return out


# ---------------------------------------------------------------- references

def build_identities(wb):
    """Parse the <sinner>_picture / _name / _nickname row triples."""
    cells = wb.cells(REF_TAB)
    imgs = wb.images(REF_TAB)

    # column A holds the named-range labels
    labels = {r: v.strip().lower() for (r, c), v in cells.items() if c == 0}
    img_at = {}
    for im in imgs:
        img_at.setdefault((im['row'], im['col']), im)

    groups = {}
    for row, label in labels.items():
        m = re.match(r'^([a-z_]+)_(picture|name|nickname)$', label)
        if m:
            groups.setdefault(m.group(1), {})[m.group(2)] = row

    identities = []
    portraits = {}
    for sinner, rows in sorted(groups.items()):
        rname = rows.get('name')
        if rname is None:
            continue
        rpic = rows.get('picture')
        rnick = rows.get('nickname')
        for (r, c), v in sorted(cells.items()):
            if r != rname:
                continue
            full = clean(v)
            if not full:
                continue
            nick = clean(cells.get((rnick, c), '')) if rnick is not None else ''
            im = None
            if rpic is not None:
                # portraits can float a row either way of their label row
                for dr in (0, -1, 1):
                    im = img_at.get((rpic + dr, c))
                    if im:
                        break
            slug = slugify(nick or full)
            if im:
                portraits[slug] = im
            identities.append({
                'slug': slug,
                'sinner': sinner.replace('_', ' ').title(),
                'name': full,
                'nickname': nick or None,
                'statuses': [],
                'portrait': ('identities/%s.png' % slug) if im else None,
            })
    return identities, portraits


STATUS_WORDS = ('bleed', 'burn', 'tremor', 'rupture', 'sinking', 'poise', 'charge')
CAT_TAB = 'ID Catalogue'


def build_id_statuses(wb):
    """Read `ID Catalogue`: a column-B status combo heads each block of IDs.

    Returns {lowercased id name: [Status, ...]}. The catalogue is the only
    place that records which statuses an identity actually carries, and it is
    what makes "which teams can run Poise" answerable later.
    """
    if CAT_TAB not in wb.sheets:
        return {}
    cells = wb.cells(CAT_TAB)
    headers = sorted((r, clean(v)) for (r, c), v in cells.items()
                     if c == 1 and clean(v))

    out = {}
    for i, (r, head) in enumerate(headers):
        parts = [p.strip() for p in re.split(r'[+]', head)]
        statuses = [p.title() for p in parts if p.lower() in STATUS_WORDS]
        if not statuses:
            continue  # the title row and "Triple Status IDs:" banner
        end = headers[i + 1][0] if i + 1 < len(headers) else max(
            rr for rr, _ in cells) + 1
        for (rr, c), v in cells.items():
            if not (r <= rr < end) or c < 3 or (c - 3) % 6:
                continue
            nm = clean(v)
            if nm and len(nm) < 70 and '\n' not in nm:
                out.setdefault(nm.lower(), [])
                for s in statuses:
                    if s not in out[nm.lower()]:
                        out[nm.lower()].append(s)
    return out


def block_bounds(cells):
    """Rows that start a new block: section headers and floor/prose headings.

    Scanning for a gift's tier must never cross one of these, or a separator
    glyph in a gutter column picks up the tier and name of the block below.
    """
    rows = set()
    for (r, c), v in cells.items():
        v = clean(v)
        if not v:
            continue
        if c == 1:
            rows.add(r)
        elif c == 3 and (FLOOR_RE.match(v)
                         or (len(v) > 40 and v.rstrip().endswith(':'))):
            rows.add(r)
    return sorted(rows)


def limit_for(bounds, r):
    """First block boundary strictly below r, or None."""
    for b in bounds:
        if b > r:
            return b
    return None


def probe(cells, r, c, limit=None):
    """Look below an icon for its tier and name.

    Returns (tier, label, tier_rows). A gift slot always has a tier numeral
    under it; warning signs and status icons sit in gutter columns and have
    none. A fusion *result* reaches its name after exactly one tier row and
    owns that name; anything else is an ingredient.

    `limit` is the next block boundary — the scan stops there so a slot can
    never borrow a tier or a name from the following pack.
    """
    tier = None
    label = None
    tier_rows = 0
    last = None
    for dr in range(1, 10):
        if limit is not None and r + dr >= limit:
            break
        v = clean(cells.get((r + dr, c), ''))
        if not v:
            continue
        if TIER_RE.match(v):
            if last != r + dr:
                tier_rows += 1
                last = r + dr
            if tier is None and v != '-':
                tier = ROMAN.get(v)
            continue
        label = v
        break
    return tier, label, tier_rows


def is_result(tier, label, tier_rows):
    return bool(label) and tier_rows == 1


def build_gift_index(books):
    """icon sha -> canonical gift name, by majority vote across all team tabs."""
    votes = collections.defaultdict(collections.Counter)
    best_blob = {}
    for wb in books:
        for tab in wb.sheets:
            if tab in SHARED_TABS:
                continue
            cells = wb.cells(tab)
            bounds = block_bounds(cells)
            for im in wb.images(tab):
                sha = im['sha256']
                best_blob.setdefault(sha, (wb, im['member']))
                # Only learn names from slots that actually own the label.
                # Ingredient icons sit above a result and would otherwise all
                # vote for the result's name.
                tier, label, tier_rows = probe(cells, im['row'], im['col'],
                                               limit_for(bounds, im['row']))
                if tier is None or not is_result(tier, label, tier_rows):
                    continue
                if 2 < len(label) < 60:
                    votes[sha][label] += 1

    index = {}
    conflicts = []
    for sha, ctr in votes.items():
        name, n = ctr.most_common(1)[0]
        total = sum(ctr.values())
        conf = n / total
        if conf < 0.6 or n < 2:
            conflicts.append((sha, dict(ctr.most_common(3))))
            continue
        index[sha] = {'name': name_case(name), 'slug': slugify(name),
                      'confidence': round(conf, 2), 'votes': n}
    return index, conflicts, best_blob


# ---------------------------------------------------------------- team parse

def section_rows(cells):
    """[(row, HEADER)] from column B, in order."""
    return sorted((r, clean(v)) for (r, c), v in cells.items() if c == 1 and clean(v))


def row_group(items, tol=0):
    """Group (row, col, value) by row."""
    out = collections.defaultdict(dict)
    for r, c, v in items:
        out[r][c] = v
    return out


CARD_STRIDE = 6
UPTIE_OFFSET = 3  # the uptie numeral sits three columns right of the banner

# A note merged across one or two card slots belongs to those cards; anything
# wider is section prose. Measured on Bleed+Poise: card notes are 6 or 12
# columns, section prose is 18 or more.
MAX_SHARED_NOTE = 2 * CARD_STRIDE

# Words kept lowercase mid-name, and tokens always upper.
NAME_MINOR = {'and', 'or', 'to', 'the', 'of', 'for', 'in', 'on', 'a', 'an',
              'with', 'at', 'by', 'from'}
NAME_UPPER = {'lcb', 'ego', 'mde', 'id', 'ids', 'bl', 'hos', 'aoe', 'cqc',
              'k', 'n', 'w', 'r', 't'}


def name_case(s):
    """Tidy a gift or pack name without destroying deliberate styling.

    The sheet is inconsistent — `lcb regular check-up bokgak`, `line 2`,
    `embers` — but some names carry intentional capitals (`BokGak`) or dots
    (`A.B.s`), so any token already carrying an internal capital or a dot is
    left exactly as written.
    """
    if not s:
        return s
    out = []
    for i, word in enumerate(s.split()):
        lead, trail, core = '', '', word
        while core and not core[0].isalnum():
            lead, core = lead + core[0], core[1:]
        while core and not core[-1].isalnum():
            trail, core = core[-1] + trail, core[:-1]
        if not core:
            out.append(word)
            continue
        if '.' in word or any(ch.isupper() for ch in core[1:]):
            out.append(word)          # A.B.s, BokGak, MD7 — leave alone
            continue
        low = core.lower()
        if len(core) == 1:
            out.append(word)          # "'n" in "Hot 'n Juicy"
        elif low in NAME_UPPER:
            out.append(lead + core.upper() + trail)
        elif low in NAME_MINOR and i > 0:
            out.append(lead + low + trail)
        else:
            out.append(lead + core[0].upper() + core[1:] + trail)
    return ' '.join(out)


def id_cards(cells, r0, r1, identity_lookup, merge_width=None, imgs=None):
    """Read ID-card blocks: name row, then the notes row beneath it.

    `merge_width` maps a merged cell's top-left to how many columns it spans.
    A section-wide note (the "Explanation:" paragraph under Floor 1 Sacs, say)
    is merged across the whole sheet but anchored at column D — the same cell
    a per-card note would occupy. Anything wider than one card is therefore
    section prose and belongs to the callout, not the card.
    """
    merge_width = merge_width or {}
    img_at = {(i['row'], i['col']): i for i in (imgs or [])}
    rows = collections.defaultdict(dict)
    for (r, c), v in cells.items():
        if r0 <= r < r1:
            rows[r][c] = clean(v)

    cards = []
    for r in sorted(rows):
        cols = sorted(rows[r])
        # a name row has >=2 entries on a 6-column stride starting at D(3)
        names = [c for c in cols if (c - 3) % 6 == 0 and c >= 3]
        if not names:
            continue
        vals = [rows[r][c] for c in names]
        if any(len(v) > 70 or '\n' in v for v in vals):
            continue
        if not any(identity_lookup(v) for v in vals):
            continue
        # notes sit in the next populated row on the same stride, ignoring
        # rows that only hold a section-wide merged paragraph
        notes_row = None
        for rr in range(r + 1, min(r + 5, r1)):
            hits = [c for c in names if (rr, c) in cells]
            if not hits:
                continue
            if all(merge_width.get((rr, c), 1) > MAX_SHARED_NOTE for c in hits):
                continue
            notes_row = rr
            break

        def note_for(col):
            """Note text covering this card.

            A note merged across two card slots (the Pequod substitutes share
            one) is anchored at the left slot, so walk back along the stride
            to find a merge that reaches this column.
            """
            if notes_row is None:
                return ''
            for c0 in range(col, max(names[0] - 1, col - MAX_SHARED_NOTE), -CARD_STRIDE):
                if (notes_row, c0) not in cells:
                    continue
                w = merge_width.get((notes_row, c0), 1)
                if w > MAX_SHARED_NOTE:
                    return ''
                if c0 + w > col:
                    return cells[(notes_row, c0)]
                break
            return ''
        # Role labels ("BL Filler", "The Best BL ID") sit above the names, with
        # the portrait/banner rows in between — so look back further than the
        # notes lookahead.
        role_row = None
        for rr in range(r - 1, max(r0, r - 10), -1):
            vals = [clean(cells.get((rr, c), '')) for c in names]
            got = [v for v in vals if v]
            if len(got) >= max(1, len(names) - 2) and all(len(v) < 70 for v in got):
                role_row = rr
                break
        # Between the role label and the name sit two per-card images: the
        # acquisition banner (season pass / event) in the name's own column,
        # and the uptie numeral three columns right of it.
        art_row = None
        for rr in range(r - 1, max(role_row or r0, r - 6), -1):
            if sum(1 for c in names if (rr, c) in img_at) >= max(1, len(names) - 2):
                art_row = rr
                break

        for c in names:
            nm = rows[r][c]
            ident = identity_lookup(nm)
            banner = img_at.get((art_row, c)) if art_row is not None else None
            uptie = img_at.get((art_row, c + UPTIE_OFFSET)) if art_row is not None else None
            cards.append({
                'raw': nm,
                'id': ident['slug'] if ident else slugify(nm),
                'resolved': bool(ident),
                'name': ident['name'] if ident else nm,
                'bannerSha': banner['sha256'] if banner else None,
                'uptieSha': uptie['sha256'] if uptie else None,
                # the community short name the sheet actually used, kept as the
                # display label with the canonical name as the subtitle
                'nickname': (ident or {}).get('nickname') or nm,
                'statuses': (ident or {}).get('statuses') or [],
                'portrait': (ident or {}).get('portrait'),
                'role': clean(cells.get((role_row, c), '')) if role_row is not None else None,
                'notes': bullets(note_for(c)),
            })
        break
    return cards


def gift_rows(cells, imgs, r0, r1, gift_index):
    """Collect gift icons in a row band with their tier and resolved name."""
    by_pos = {(im['row'], im['col']): im for im in imgs}
    bounds = block_bounds(cells)
    out = []
    for (r, c), im in sorted(by_pos.items()):
        if not (r0 <= r < r1):
            continue

        # A gift slot always carries a tier numeral in its own column a few
        # rows down. Warning signs, fusion "+" separators and status icons sit
        # in the gutter columns and never do, which is what separates them.
        nb = limit_for(bounds, r)
        tier, labelled, tier_rows = probe(cells, r, c,
                                          min(r1, nb) if nb else r1)
        if tier is None:
            continue
        role = 'result' if is_result(tier, labelled, tier_rows) else 'ingredient'

        g = gift_index.get(im['sha256'])
        # An ingredient only gets a name if the index learned one from a
        # labelled slot elsewhere; never inherit the result's own label.
        name = (g or {}).get('name') or (labelled if role == 'result' else None)
        if role == 'result' and not name:
            continue
        out.append({'row': r, 'col': c, 'sha': im['sha256'],
                    'gift': (g or {}).get('slug') or (slugify(name) if name else None),
                    'name': name_case(name), 'labelled': labelled, 'role': role,
                    'resolved': bool(g), 'tier': tier})
    return out


def fuse(gifts):
    """Attach ingredient icons to the fusion result they sit above.

    Ingredients are laid out centred on their result's column, so each one
    binds to the nearest result column. Blocks with no ingredients come back
    as a plain list of results.
    """
    results = [g for g in gifts if g['role'] == 'result']
    ingredients = [g for g in gifts if g['role'] == 'ingredient']

    def strip(g):
        return {'gift': g['gift'], 'name': g['name'], 'sha': g['sha'],
                'tier': g['tier'], 'resolved': g['resolved']}

    if not results:
        return [dict(strip(g), ingredients=[]) for g in ingredients]

    # An ingredient strip is laid out left-aligned with its result and runs
    # rightward until the next result's column, so an ingredient belongs to
    # the nearest result at or to its LEFT on the first result row beneath
    # it — not to whichever result column happens to be closest.
    rows = sorted({r['row'] for r in results})
    buckets = {id(r): [] for r in results}
    for ing in ingredients:
        below = [rr for rr in rows if rr > ing['row']]
        if not below:
            continue
        row = below[0]
        same = sorted((r for r in results if r['row'] == row),
                      key=lambda r: r['col'])
        left = [r for r in same if r['col'] <= ing['col']]
        owner = left[-1] if left else same[0]
        buckets[id(owner)].append(ing)

    out = []
    seen = set()
    for r in results:
        # the same fusion result can be anchored twice in one block
        key = (r['gift'], r['tier'])
        if key in seen:
            continue
        seen.add(key)
        items = sorted(buckets[id(r)], key=lambda g: g['col'])
        out.append(dict(strip(r), ingredients=[strip(i) for i in items]))
    return out


FLOOR_RE = re.compile(r'^Floors?\b', re.I)


def parse_floors(cells, imgs, r0, r1, gift_index):
    """Split the FLOORS TO PICK band into per-floor blocks.

    A floor block starts where column D holds a "Floor N:" label. The pack name
    is the next column-D text in the block, the guidance prose sits out at
    column AD, and every gift icon between belongs to that floor.
    """
    # Two kinds of block open in column D: a "Floor N:" pack block, and a
    # prose checklist heading ("...gifts you should get before the MDE
    # floors:"). The tail of every team tab is checklists, not packs.
    starts = []
    for r in range(r0, r1):
        v = clean(cells.get((r, 3), ''))
        if not v:
            continue
        if FLOOR_RE.match(v):
            starts.append((r, v, 'floor'))
        elif len(v) > 40 and v.rstrip().endswith(':'):
            starts.append((r, v, 'checklist'))

    floors = []
    for i, (r, label, kind) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else r1
        pack = None
        marker = None
        if kind == 'floor':
            for rr in range(r + 1, end):
                v = clean(cells.get((rr, 3), ''))
                if v and not FLOOR_RE.match(v) and not v.rstrip().endswith(':'):
                    pack = name_case(v)
                    break
        else:
            # the warning-sign glyph bookends a checklist row at column D
            for im in imgs:
                if r <= im['row'] < end and im['col'] == 3:
                    marker = im['sha256']
                    break
        info = None
        for rr in range(r, end):
            for c in (29, 28, 30):
                v = clean(cells.get((rr, c), ''))
                if v and len(v) > 40:
                    info = v
                    break
            if info:
                break
        gifts = fuse(gift_rows(cells, imgs, r, end, gift_index))
        floors.append({
            'kind': kind,
            'marker': marker,
            'label': label.rstrip(':'),
            'pack': pack,
            'packSlug': slugify(pack) if pack else None,
            'gifts': gifts,
            'info': bullets(info) if info else [],
        })
    return floors


def main():
    site = sys.argv[1]
    team_tab = sys.argv[2]
    paths = sys.argv[3:]
    books = [Workbook(p) for p in paths]
    primary = next((b for b in books if team_tab in b.sheets), None)
    if primary is None:
        print('team tab %r not found' % team_tab)
        return 1

    os.makedirs(os.path.join(site, 'data', 'teams'), exist_ok=True)

    # ---- references
    refbook = next(b for b in books if REF_TAB in b.sheets)
    identities, portraits = build_identities(refbook)
    id_statuses = build_id_statuses(refbook)
    gift_index, conflicts, blob_src = build_gift_index(books)

    # attach catalogue statuses via either the canonical name or the nickname
    for i in identities:
        for key in (i['name'], i.get('nickname')):
            if key and key.lower() in id_statuses:
                for st in id_statuses[key.lower()]:
                    if st not in i['statuses']:
                        i['statuses'].append(st)

    by_slug = {i['slug']: i for i in identities}
    alias = {}
    for i in identities:
        alias[i['name'].lower()] = i
        if i['nickname']:
            alias[i['nickname'].lower()] = i
        alias[i['slug']] = i

    def lookup(nm):
        if not nm:
            return None
        k = clean(nm).lower()
        return alias.get(k) or alias.get(slugify(nm))

    # ---- assets
    def write_asset(category, slug, wb, member):
        d = os.path.join(site, 'assets', category)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, slug + '.png')
        # optimise.mjs replaces each PNG with a WebP; don't resurrect the PNG
        # on the next run or every rebuild re-converts the whole library
        if not os.path.exists(p) and not os.path.exists(p[:-4] + '.webp'):
            with open(p, 'wb') as fh:
                fh.write(wb.read_member(member))
        return '%s/%s.png' % (category, slug)

    for slug, im in portraits.items():
        write_asset('identities', slug, refbook, im['member'])
    for sha, g in gift_index.items():
        wb, member = blob_src[sha]
        write_asset('gifts', g['slug'], wb, member)

    # ---- team
    cells = primary.cells(team_tab)
    imgs = primary.images(team_tab)
    links = primary.hyperlinks(team_tab)
    secs = section_rows(cells)
    # how many columns each merged cell spans, keyed by its top-left
    merge_width = {(a[0], a[1]): b[1] - a[1] + 1 for a, b in primary.merges(team_tab)}
    maxrow = max(r for r, _ in cells) + 1

    def band(name_fragment):
        """Row range of the section whose header contains the fragment."""
        frag = name_fragment.upper()
        for i, (r, h) in enumerate(secs):
            if frag in h.upper():
                end = secs[i + 1][0] if i + 1 < len(secs) else maxrow
                return r, end
        return None, None

    def find_text(pred, limit=None):
        for (r, c), v in sorted(cells.items()):
            if limit and r > limit:
                break
            v2 = clean(v)
            if pred(v2):
                return r, c, v2
        return None, None, None

    header = {}
    for (r, c), v in sorted(cells.items()):
        v = clean(v)
        if v.startswith('Team Code'):
            nxt = cells.get((r + 1, c)) or ''
            header['teamCode'] = clean(nxt) or v.split(':', 1)[-1].strip()
        elif v.startswith('LAST UPDATED'):
            header['lastUpdated'] = v.split(':', 1)[-1].strip()
        elif v == 'Difficulty:':
            header['difficulty'] = clean(cells.get((r, c + 5), '')) or \
                                   clean(cells.get((r, c + 4), ''))
        elif v.startswith('Guidemaker'):
            header['credits'] = v

    title_r, title_c, title = find_text(lambda v: '\nby ' in v, limit=12)
    name = title.split('\n')[0].strip() if title else team_tab
    guidemaker = title.split('\nby ', 1)[1].strip() if title and '\nby ' in title else None
    _, _, desc = find_text(lambda v: v.startswith('This guide is for'), limit=16)

    # footage block: contributor row, avatar row, count row, link row, label row
    footage = []
    frow, _ = band('FOOTAGES')
    if frow is not None:
        avatars = {im['col']: im for im in imgs if frow <= im['row'] <= frow + 6}
        contrib_r = None
        for rr in range(frow, frow + 6):
            cs = [c for c in range(0, 48) if (rr, c) in cells and (c - 4) % 8 == 0]
            if len(cs) >= 3:
                contrib_r = rr
                break
        if contrib_r is not None:
            for c in sorted(c for c in range(0, 48) if (contrib_r, c) in cells and (c - 4) % 8 == 0):
                who = clean(cells[(contrib_r, c)])
                lc = c + 4
                url = None
                cnt = None
                label = None
                for dr in range(0, 8):
                    if (contrib_r + dr, lc) in links and not url:
                        url = links[(contrib_r + dr, lc)]
                    v = clean(cells.get((contrib_r + dr, lc), ''))
                    if v and re.match(r'^\d+(\.\d+)?$', v) and cnt is None:
                        cnt = int(float(v))
                    v2 = clean(cells.get((contrib_r + dr, c), ''))
                    if v2 and v2 != who and label is None and len(v2) < 60:
                        label = v2
                im = avatars.get(c)
                slug = slugify(who)
                avatar = write_asset('avatars', slug, primary, im['member']) if im else None
                footage.append({
                    'contributor': who, 'label': label, 'url': url,
                    'secretBossGifts': cnt, 'avatar': avatar,
                })

    team = {
        'slug': slugify(team_tab),
        'name': name,
        'tab': team_tab,
        'collection': os.path.splitext(os.path.basename(primary.path))[0],
        'statuses': [s for s in re.split(r'[+]', name.split('\n')[0]) if s and s.isalpha()],
        'guidemaker': guidemaker,
        'difficulty': header.get('difficulty'),
        'difficultyLevel': DIFFICULTY_LEVELS.get(
            (header.get('difficulty') or '').strip().lower()),
        'lastUpdated': header.get('lastUpdated'),
        'teamCode': header.get('teamCode'),
        'credits': header.get('credits'),
        'description': desc,
        'footage': footage,
        'sections': [],
    }

    for i, (r, h) in enumerate(secs):
        end = secs[i + 1][0] if i + 1 < len(secs) else maxrow
        H = h.upper()
        if 'FOOTAGE' in H or h == name or '\nby ' in h:
            continue
        entry = {'heading': h, 'row': r}
        if any(k in H for k in ('PREFERRED TEAM', 'SACS', 'SUBSTITUTE',
                                'BACKUP', 'SKILL REPLACEMENT', 'IDS FOR')):
            entry['kind'] = 'roster'
            entry['cards'] = id_cards(cells, r, end, lookup, merge_width, imgs)
        elif 'FLOORS TO PICK' in H:
            entry['kind'] = 'floors'
            entry['floors'] = parse_floors(cells, imgs, r, end, gift_index)
        elif 'EGO GIFT' in H:
            entry['kind'] = 'gifts'
            raw = gift_rows(cells, imgs, r, end, gift_index)
            entry['gifts'] = []
            for grp, sel in (('starting', lambda g: g['col'] < 15),
                             ('search', lambda g: g['col'] >= 15)):
                for g in fuse([x for x in raw if sel(x)]):
                    entry['gifts'].append(dict(g, group=grp))
        else:
            entry['kind'] = 'prose'
        notes = [clean(v) for (rr, c), v in sorted(cells.items())
                 if r <= rr < end and c > 1 and len(clean(v)) > 80]
        entry['notes'] = notes[:6]
        team['sections'].append(entry)

    # Fusion ingredients are never labelled anywhere in the sheet, so their
    # names come from recipes the guidemaker supplied. Matched by position,
    # left to right, and only when the recipe's shape agrees with what was
    # extracted — a mismatch is reported rather than guessed at.
    rpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'fusion_recipes.json')
    recipes = {}
    if os.path.exists(rpath):
        with open(rpath, encoding='utf-8') as fh:
            recipes = json.load(fh).get('recipes', {})

    recipe_stats = {'applied': 0, 'named': 0, 'mismatch': []}

    def apply_recipes(slots):
        for g in slots:
            ings = g.get('ingredients') or []
            rec = recipes.get(g.get('gift') or '')
            if not rec or not ings:
                continue
            if len(rec) != len(ings):
                recipe_stats['mismatch'].append(
                    '%s: sheet shows %d ingredient(s), recipe lists %d'
                    % (g.get('name'), len(ings), len(rec)))
                continue

            # Some ingredient strips run descending by tier, so position is
            # not reliable. When the recipe's tiers are all distinct and the
            # multiset agrees with what was extracted, match on tier; the
            # tiers come from the sheet and are authoritative.
            ext = [i.get('tier') for i in ings]
            want = [r.get('tier') for r in rec]
            chosen = list(rec)
            if (len(set(want)) == len(want)
                    and sorted(x for x in ext if x) == sorted(x for x in want if x)):
                by_tier = {r['tier']: r for r in rec}
                if all(t in by_tier for t in ext):
                    chosen = [by_tier[t] for t in ext]

            # If the icon index already named an ingredient, the recipe must
            # agree with it — otherwise one of the two is wrong, and guessing
            # would bake in a mislabelled icon.
            clash = [(i['name'], sp['name']) for i, sp in zip(ings, chosen)
                     if i.get('name') and i['name'].lower() != sp['name'].lower()]
            if clash:
                recipe_stats['mismatch'].append(
                    '%s: recipe disagrees with extracted names %s'
                    % (g.get('name'), clash))
                continue

            for ing, spec in zip(ings, chosen):
                if not ing.get('name'):
                    ing['name'] = spec['name']
                    ing['gift'] = slugify(spec['name'])
                    ing['fromRecipe'] = True
                    recipe_stats['named'] += 1
                if ing.get('tier') is None:
                    ing['tier'] = spec.get('tier')
            recipe_stats['applied'] += 1

    for s in team['sections']:
        apply_recipes(s.get('gifts') or [])
        for f in s.get('floors') or []:
            apply_recipes(f.get('gifts') or [])

    # Gift slots resolved by their own label never went through the icon
    # index, so write their art here too.
    def write_gift_assets(slots):
        for g in slots:
            sha, gslug = g.get('sha'), g.get('gift')
            if sha and gslug and sha in blob_src:
                wbm, member = blob_src[sha]
                write_asset('gifts', gslug, wbm, member)
            write_gift_assets(g.get('ingredients') or [])

    for s in team['sections']:
        write_gift_assets(s.get('gifts') or [])
        for f in s.get('floors') or []:
            write_gift_assets(f.get('gifts') or [])

    # Identity-card art: acquisition banner and uptie numeral. Names come
    # from the verified mapping; anything unlisted still ships, keyed by its
    # hash, so a new season renders without a code change.
    here = os.path.dirname(os.path.abspath(__file__))
    artmap = {'banners': {}, 'upties': {}}
    apath = os.path.join(here, 'card_art.json')
    if os.path.exists(apath):
        with open(apath, encoding='utf-8') as fh:
            loaded = json.load(fh)
        artmap['banners'] = loaded.get('banners', {})
        artmap['upties'] = loaded.get('upties', {})

    def attach_art(card, key, category, mapping):
        sha = card.pop(key + 'Sha', None)
        if not sha:
            card[key] = None
            return
        meta = mapping.get(sha[:10]) or {}
        slug = meta.get('slug') or ('%s-%s' % (category[:-1], sha[:10]))
        if sha in blob_src:
            wbm, member = blob_src[sha]
            write_asset(category, slug, wbm, member)
        card[key] = {'slug': slug, 'label': meta.get('label'),
                     'level': meta.get('level'),
                     'src': '%s/%s.png' % (category, slug)}

    for sec in team['sections']:
        for card in sec.get('cards') or []:
            attach_art(card, 'banner', 'banners', artmap['banners'])
            attach_art(card, 'uptie', 'upties', artmap['upties'])

    # Status icons, from the hand-verified sha mapping in tools/status_icons.json
    simap = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'status_icons.json')
    if os.path.exists(simap):
        with open(simap, encoding='utf-8') as fh:
            for st, sha in json.load(fh).items():
                if sha in blob_src:
                    wbm, member = blob_src[sha]
                    write_asset('status', st.lower(), wbm, member)

    # the skull that sits beside "Difficulty:" becomes the difficulty bar unit
    for (rr, cc), v in cells.items():
        if clean(v) == 'Difficulty:':
            for im in imgs:
                if im['row'] == rr:
                    write_asset('ui', 'skull', primary, im['member'])
                    break
            break

    # the warning glyph that bookends the checklist rows, as a real UI asset
    for s in team['sections']:
        for f in s.get('floors', []):
            sha = f.get('marker')
            if sha and sha in blob_src:
                wbm, member = blob_src[sha]
                write_asset('ui', 'warning', wbm, member)

    with open(os.path.join(site, 'data', 'identities.json'), 'w', encoding='utf-8') as fh:
        json.dump(identities, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(site, 'data', 'gifts.json'), 'w', encoding='utf-8') as fh:
        json.dump(sorted(gift_index.values(), key=lambda g: g['slug']),
                  fh, indent=2, ensure_ascii=False)
    with open(os.path.join(site, 'data', 'teams', team['slug'] + '.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(team, fh, indent=2, ensure_ascii=False)

    tagged = sum(1 for i in identities if i['statuses'])
    print('identities: %d (%d portraits, %d status-tagged)'
          % (len(identities), len(portraits), tagged))
    print('gift icons resolved: %d  (ambiguous: %d)' % (len(gift_index), len(conflicts)))
    print('fusion recipes applied: %d  (%d ingredients named)'
          % (recipe_stats['applied'], recipe_stats['named']))
    for m in recipe_stats['mismatch']:
        print('  RECIPE MISMATCH  %s' % m)
    print('team: %s' % team['name'])
    print('  difficulty=%s  updated=%s  code=%s'
          % (team['difficulty'], team['lastUpdated'],
             (team['teamCode'] or '')[:24] + '...'))
    print('  footage slots: %d' % len(footage))
    for s in team['sections']:
        extra = ''
        if s['kind'] == 'roster':
            got = sum(1 for c in s['cards'] if c['resolved'])
            extra = '%d cards (%d resolved)' % (len(s['cards']), got)
        elif s['kind'] == 'gifts':
            extra = '%d gifts' % len(s['gifts'])
        elif s['kind'] == 'floors':
            extra = '%d floors, %d gifts' % (
                len(s['floors']), sum(len(f['gifts']) for f in s['floors']))
        print('  [%-7s] %-42s %s' % (s['kind'], s['heading'][:42], extra))
    return 0


if __name__ == '__main__':
    sys.exit(main())
