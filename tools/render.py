"""Render a team JSON into a standalone static page.

A plain generator with no dependencies: the prototype's job is to prove the
data model carries everything the sheet showed. Swapping this for Astro
templates later changes only this file.

Usage: python -I tools/render.py <site_dir> <team-slug>
"""
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V'}

STATUS_TINT = {
    'bleed': '#c4423c', 'burn': '#e07a35', 'tremor': '#cfa42a',
    'rupture': '#8b55b8', 'sinking': '#4477b0', 'poise': '#3fa08c',
    'charge': '#48b0d4',
}


def e(s):
    return html.escape(str(s)) if s is not None else ''


def nl2br(s):
    return e(s).replace('\n', '<br>')


def tint(statuses):
    for s in statuses:
        if s.lower() in STATUS_TINT:
            return STATUS_TINT[s.lower()]
    return '#c8a24a'


def tier_badge(t, cls='tier'):
    return '<span class="%s t%s">%s</span>' % (cls, t, ROMAN.get(t, t)) if t else ''


# ---------------------------------------------------------------- components

def gift_node(g, asset, size='md'):
    icon = asset('assets/gifts/%s.png' % g['gift']) if g.get('gift') else None
    img = ('<img loading="lazy" src="%s" alt="">' % e(icon)) if icon \
        else '<span class="noicon">?</span>'
    label = g.get('name') or 'Unidentified'
    unknown = '' if g.get('name') else ' unknown'
    return ('<figure class="gift %s%s">'
            '<span class="art">%s%s</span>'
            '<figcaption>%s</figcaption></figure>'
            % (size, unknown, img, tier_badge(g.get('tier')), e(label)))


def gift_slot(g, asset):
    """A fusion result with its ingredients above it, or a plain gift."""
    ings = g.get('ingredients') or []
    if not ings:
        return gift_node(g, asset)
    parts = []
    for i, ing in enumerate(ings):
        if i:
            parts.append('<span class="plus">+</span>')
        parts.append(gift_node(ing, asset, 'sm'))
    return ('<div class="fusion">'
            '<div class="ingredients">%s</div>'
            '<div class="yields" aria-label="fuses into"></div>'
            '%s</div>'
            % (''.join(parts), gift_node(g, asset, 'lg')))


def status_icons(statuses, asset, cls='tags'):
    """Status shown as the game's own icons rather than repeating the words."""
    if not statuses:
        return ''
    out = []
    for s in statuses:
        src = asset('assets/status/%s.png' % s.lower())
        if src:
            out.append('<img class="st" src="%s" alt="%s" title="%s">'
                       % (e(src), e(s), e(s)))
        else:
            out.append('<span class="st txt" style="--p:%s">%s</span>'
                       % (STATUS_TINT.get(s.lower(), '#8c8178'), e(s)))
    return '<p class="%s">%s</p>' % (cls, ''.join(out))


DIFF_COLOUR = {1: '#7fae5e', 2: '#a8ad52', 3: '#d79a3a', 4: '#d2703a', 5: '#c4423c'}


def difficulty_bar(label, level, asset, maximum=5):
    """The sheet's skull plus a segmented meter.

    Three detailed skull glyphs turn to mush at this size, so the skull is
    shown once as the marker and the level is carried by filled segments.
    """
    if not label:
        return ''
    src = asset('assets/ui/skull.png')
    mark = ('<img class="skull" src="%s" alt="Difficulty">' % e(src)) if src \
        else '<span class="skull">&#9760;</span>'
    segs = ''.join('<span class="seg%s"></span>' % (' on' if level and i < level else '')
                   for i in range(maximum))
    return ('<div class="difficulty" style="--d:%s">%s'
            '<span class="meter">%s</span><span class="dlabel">%s</span></div>'
            % (DIFF_COLOUR.get(level or 0, '#8c8178'), mark, segs, e(label)))


def id_card(c, asset, compact=False):
    p = asset('assets/' + c['portrait']) if c.get('portrait') else None
    img = ('<img loading="lazy" src="%s" alt="">' % e(p)) if p \
        else '<span class="noportrait">%s</span>' % e((c.get('nickname') or '?')[:1])
    role = '<p class="role">%s</p>' % e(c['role']) if c.get('role') else ''
    # the canonical name only restates the nickname, so it lives in the
    # tooltip rather than as a second line of visible text
    title = c.get('nickname') or c.get('name')
    warn = '' if c.get('resolved') else \
        '<span class="unres" title="not found in the reference sheet">?</span>'
    notes = ''
    if c.get('notes'):
        notes = '<ul class="notes">%s</ul>' % ''.join('<li>%s</li>' % e(n) for n in c['notes'])
    # uptie numeral badges the portrait; the acquisition banner sits under
    # the name, both as they appear on the sheet
    up = c.get('uptie') or {}
    upsrc = asset('assets/' + up['src']) if up.get('src') else None
    badge = ('<span class="uptie" title="Uptie %s"><img src="%s" alt="Uptie %s"></span>'
             % (e(up.get('label') or ''), e(upsrc), e(up.get('label') or ''))) if upsrc else ''

    bn = c.get('banner') or {}
    bnsrc = asset('assets/' + bn['src']) if bn.get('src') else None
    banner = ('<p class="source"><img src="%s" alt="%s" title="%s"></p>'
              % (e(bnsrc), e(bn.get('label') or 'Source'),
                 e(bn.get('label') or ''))) if bnsrc else ''

    # portrait, uptie badge and source banner form one left rail, so the
    # banner stays small and the text column is left to the explanation
    return ('<article class="idcard%s">'
            '<div class="art"><div class="pic">%s%s</div>%s</div>'
            '<div class="meta"><div class="hd">%s<h4 title="%s">%s%s</h4></div>'
            '%s%s</div></article>'
            % (' compact' if compact else '', img, badge, banner, role,
               e(c.get('name') or title), e(title), warn,
               status_icons(c.get('statuses'), asset), notes))


# ---------------------------------------------------------------------- page

def main():
    site, slug = sys.argv[1], sys.argv[2]
    with open(os.path.join(site, 'data', 'teams', slug + '.json'), encoding='utf-8') as fh:
        t = json.load(fh)

    def asset(rel):
        base = rel.rsplit('.', 1)[0]
        for ext in ('.webp', '.png'):
            if os.path.exists(os.path.join(site, base + ext)):
                return base + ext
        return None

    warn_icon = asset('assets/ui/warning.png')
    out = []
    A = out.append

    A('<!doctype html><html lang="en"><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A('<title>%s — MDE Team Guide</title>' % e(t['name']))
    # version the stylesheet by mtime so a rebuild is never served stale
    css = os.path.join(site, 'style.css')
    ver = int(os.path.getmtime(css)) if os.path.exists(css) else 0
    A('<link rel="stylesheet" href="style.css?v=%d">' % ver)
    A('<body style="--accent:%s">' % tint(t.get('statuses') or []))

    A('<header class="hero"><div class="wrap">')
    A('<nav class="crumbs"><a href="index.html">MDE Teams</a><span>/</span>%s</nav>'
      % e((t.get('collection') or '').title()))
    # The title already says "Bleed+Poise", so the statuses are shown as the
    # game's icons and the spare room goes to the difficulty bar instead.
    A('<div class="titleline"><h1>%s</h1>%s</div>'
      % (e(t['name']), status_icons(t.get('statuses'), asset, 'heroicons')))
    A(difficulty_bar(t.get('difficulty'), t.get('difficultyLevel'), asset))
    A('<dl class="facts">')
    for k, v in (('Guidemaker', t.get('guidemaker')),
                 ('Last updated', t.get('lastUpdated')),
                 ('Footage', 'F11–F15')):
        if v:
            A('<div><dt>%s</dt><dd>%s</dd></div>' % (e(k), e(v)))
    A('</dl>')
    if t.get('teamCode'):
        A('<div class="code"><label>Team Code</label><code>%s</code>'
          '<button id="copy" data-code="%s">Copy</button></div>'
          % (e(t['teamCode'][:40] + '…'), e(t['teamCode'])))
    A('</div></header>')

    # ---- section index, so a long guide stays navigable mid-run
    def anchor(s):
        import re as _re
        return _re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

    nav = [('footage', 'Footage')] if t.get('footage') else []
    for s in t['sections']:
        head = s['heading']
        label = head if not head.isupper() else head.title()
        if s['kind'] == 'roster' and s.get('cards'):
            nav.append((anchor(head), label))
        elif s['kind'] == 'gifts' and s.get('gifts'):
            nav.append((anchor(head), label))
        elif s['kind'] == 'floors' and s.get('floors'):
            if any(f.get('kind') != 'checklist' for f in s['floors']):
                nav.append(('floors', 'Floors'))
            if any(f.get('kind') == 'checklist' for f in s['floors']):
                nav.append(('priority', 'Priority Gifts'))
        elif s['kind'] == 'prose' and s.get('notes'):
            nav.append((anchor(head), label))
    A('<nav class="sectionnav"><div class="wrap">%s</div></nav>'
      % ''.join('<a href="#%s">%s</a>' % (e(a), e(l)) for a, l in nav))

    A('<main class="wrap">')
    if t.get('description'):
        A('<section class="intro"><p>%s</p></section>' % nl2br(t['description']))

    if t.get('footage'):
        A('<section id="footage"><h2>Footage</h2><div class="footage">')
        for f in t['footage']:
            av = asset('assets/' + f['avatar']) if f.get('avatar') else None
            img = ('<img loading="lazy" src="%s" alt="">' % e(av)) if av \
                else '<span class="noportrait"></span>'
            inner = ('%s<div><strong>%s</strong><span>%s</span>'
                     '<span class="sb">%s secret boss gift(s)</span></div>'
                     % (img, e(f['contributor']),
                        e((f.get('label') or '').replace('\n', ' ')),
                        e(f.get('secretBossGifts') or 0)))
            A('<a class="fcard" href="%s" target="_blank" rel="noopener">%s</a>'
              % (e(f['url']), inner) if f.get('url')
              else '<div class="fcard">%s</div>' % inner)
        A('</div></section>')

    for s in t['sections']:
        kind, head = s['kind'], s['heading']
        title = head if not head.isupper() else head.title()

        if kind == 'roster' and s.get('cards'):
            # the preferred loadout leads; sacs, substitutes and warnings are
            # reference material and get a tighter card
            primary = 'PREFERRED TEAM' in head.upper()
            A('<section id="%s"%s><h2>%s</h2>'
              % (anchor(head), '' if primary else ' class="secondary"', e(title)))
            for n in s.get('notes', [])[:1]:
                A('<p class="callout">%s</p>' % nl2br(n))
            A('<div class="roster%s">%s</div></section>'
              % ('' if primary else ' tight',
                 ''.join(id_card(c, asset, not primary) for c in s['cards'])))

        elif kind == 'gifts' and s.get('gifts'):
            A('<section id="%s"><h2>%s</h2>' % (anchor(head), e(title)))
            for grp, label in (('starting', 'Starting Gifts'), ('search', 'Gift Search')):
                items = [g for g in s['gifts'] if g.get('group') == grp]
                if items:
                    A('<h3>%s</h3><div class="gifts">%s</div>'
                      % (e(label), ''.join(gift_slot(g, asset) for g in items)))
            for n in s.get('notes', [])[:2]:
                A('<p class="callout">%s</p>' % nl2br(n))
            A('</section>')

        elif kind == 'floors' and s.get('floors'):
            packs = [f for f in s['floors'] if f.get('kind') != 'checklist']
            lists = [f for f in s['floors'] if f.get('kind') == 'checklist']
            if packs:
                # Packs sharing a floor range are alternatives, not a queue of
                # ten equal cards — group them under one range heading and let
                # each pack have the full width so its gifts sit on one row.
                groups = []
                for f in packs:
                    if groups and groups[-1][0] == f['label']:
                        groups[-1][1].append(f)
                    else:
                        groups.append((f['label'], [f]))

                A('<section id="floors"><h2>Floors to Pick</h2>')
                for label, items in groups:
                    A('<div class="frange"><div class="rangehead">'
                      '<span class="fl">%s</span>%s</div>'
                      % (e(label),
                         '<span class="count">%d packs to choose from</span>' % len(items)
                         if len(items) > 1 else ''))
                    for f in items:
                        A('<article class="floor"><h3>%s</h3>' % e(f.get('pack') or '—'))
                        if f['gifts']:
                            A('<div class="gifts">%s</div>'
                              % ''.join(gift_slot(g, asset) for g in f['gifts']))
                        if f.get('info'):
                            A('<ul class="notes cols">%s</ul>'
                              % ''.join('<li>%s</li>' % e(x) for x in f['info']))
                        A('</article>')
                    A('</div>')
                A('</section>')
            for f in lists:
                mark = ('<img class="warn" src="%s" alt="Warning">' % e(warn_icon)) \
                    if warn_icon else '<span class="warn">!</span>'
                A('<section id="priority" class="checklist"><h2>%sPriority Gifts</h2>' % mark)
                A('<p class="lead">%s</p>' % e(f['label']))
                if f['gifts']:
                    A('<div class="gifts">%s</div>'
                      % ''.join(gift_slot(g, asset) for g in f['gifts']))
                if f.get('info'):
                    A('<ul class="notes">%s</ul>'
                      % ''.join('<li>%s</li>' % e(x) for x in f['info']))
                A('</section>')

        elif kind == 'prose' and s.get('notes'):
            A('<section id="' + anchor(head) + '"><h2>%s</h2>%s</section>'
              % (e(title), ''.join('<p class="callout">%s</p>' % nl2br(n)
                                   for n in s['notes'][:2])))

    if t.get('credits'):
        A('<section class="credits"><h2>Credits</h2><p>%s</p></section>' % nl2br(t['credits']))
    A('</main>')

    A("""<script>
document.getElementById('copy')?.addEventListener('click', async (ev) => {
  const b = ev.currentTarget;
  try { await navigator.clipboard.writeText(b.dataset.code); b.textContent = 'Copied'; }
  catch { b.textContent = 'Ctrl+C'; }
  setTimeout(() => (b.textContent = 'Copy'), 1600);
});
</script></body></html>""")

    path = os.path.join(site, slug + '.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out))
    print('wrote %s (%d KB)' % (path, os.path.getsize(path) // 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
