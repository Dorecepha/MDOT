# CLAUDE.md

Guidance for working in this repo. Read `PLAN.md` for the measured background
and `TODO.md` for outstanding work.

## What this is

MDOT migrates Limbus Company **Mirror Dungeon Expert** team guides out of two
Google Sheets workbooks into a static site. Source workbooks, both by
guidemaker Vladsault:

| Workbook | Sheet ID | Team tabs |
|---|---|---|
| MDE Comfortable Teams Guide | `1NEYBZESiLSdVHsQgHQWm7NN0uWYBKRPMxTmYfb6YFLo` | 15 |
| MDE Niche Teams Guide | `1cs-i4qZ0aN2P4-5HxTNWBoyXOyPm9CoemTx-jqkuXF0` | 10 |

They kept bricking because they hold **1,330 embedded PNGs totalling 226 MB**
plus ~467 merged ranges per team tab — not because of row count. Only
Bleed+Poise is ported so far; the other 24 are pending.

## Pipeline

```bash
python -I tools/extract.py site "<Tab Name>" _import/raw/comfortable.xlsx _import/raw/niche.xlsx
node tools/optimise.mjs site
python -I tools/render.py site <team-slug>
```

Raw `.xlsx` exports are gitignored (112 MB each). Re-download with:

```bash
curl -L "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=xlsx" -o _import/raw/<name>.xlsx
```

Preview with the `site` config in `.claude/launch.json` (port 4179).

## Environment constraints — these have bitten before

- **`pip` is unavailable.** No `openpyxl`, no Pillow. `tools/xlsx.py` reads
  the workbooks with stdlib `zipfile` + `ElementTree`. Keep it that way.
  `npm` *does* work; `sharp` handles image conversion.
- **`python -I` strips the script's own directory from `sys.path`.** Every
  tool re-adds just that directory explicitly. Keep `-I`: the workbooks are
  untrusted downloads and must not be able to shadow an import.
- **The Windows console is cp1252**; the sheet carries CJK and typographic
  punctuation. `-I` ignores `PYTHONIOENCODING`, so scripts call
  `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`.
- **Never extract via CSV.** The gviz CSV export silently collapses empty
  rows, so its row numbers do not line up with image anchor rows. It also
  drops fill colours, and `Teams List` stores difficulty and footage slots
  as colours with no text.
- **`write_asset` skips a file that already exists**, including when a WebP
  is present, so rebuilds stay fast. If an icon was written from a *wrong*
  source, delete the directory (`rm -rf site/assets/gifts`) and re-extract —
  a plain re-run will keep serving the stale image.

## How the sheet encodes things

Conventions of the source, so they survive re-import:

- Team tabs use one rigid template. **Column B** holds section headers,
  **column D** holds floor labels and pack names, **column AD** holds floor
  guidance prose. ID cards sit on a 6-column stride from D; gift slots on a
  3- or 4-column stride.
- **`New Reference Sheet` is the lookup table** — `<sinner>_picture` /
  `_name` / `_nickname` row triples, column-aligned, keyed in column A. It
  yields both the portrait library and the nickname alias map.
- **`ID Catalogue`** groups IDs under status-combo headings in column B;
  that is the only source of per-identity statuses.
- **Names drift.** Team tabs write `hornet Meursault`, `S Corp. hong Lu`,
  `Index Apprentice Don QUixote`. Always resolve through the alias map and
  **fail loudly** on a miss. Never guess.
- Pack names sit at the **end** of their block, not next to the floor label.

### Icon classification rules

These took several wrong attempts; do not re-derive them casually.

1. **A real gift icon always has a tier numeral (I–V) directly below it in
   its own column.** Warning signs, fusion "+" separators and status icons
   live in gutter columns and never do. This single rule removes every
   spurious gift.
2. **Tier/name scans must stop at the next block boundary** (`block_bounds`).
   Without it, a separator in a gutter column borrows the tier and name of
   the pack *below* — which both invents fusions and attaches the wrong art
   to real gifts.
3. **A fusion result** reaches its name after exactly one tier row and owns
   that label. Anything else is an ingredient. Learn icon→name **only from
   results**, or every ingredient votes for its result's name.
4. **Ingredients bind to the nearest result at or to their LEFT** on the
   first result row beneath them. Strips are left-aligned with their result
   and run rightward to the next result's column. Nearest-column binding is
   wrong and produces plausible-looking garbage.
5. **A note merged wider than one card is section prose**, not a card note —
   otherwise the Floor 1 Sacs "Explanation:" paragraph duplicates onto the
   first card.

## Verified mappings — extend, don't regenerate

Hand-checked by eye; keyed by image sha256 prefix. Re-deriving them by
inference was tried and was unreliable.

- `tools/status_icons.json` — the seven status icons.
- `tools/card_art.json` — acquisition banners and uptie numerals.

Unlisted images still render under a hash-derived slug, so a new season
never breaks the build; add an entry to give it a name.

## Visual conventions

Settled with the guidemaker; see `PLAN.md` for the full list.

- Status is shown as **game icons, never words** — the team title already
  says "Bleed+Poise".
- Difficulty is the sheet's skull plus a **5-segment meter** (Easy 1,
  Medium 3, Hard 5).
- Identity art is **never cropped** — `object-fit: contain`.
- The card's left rail is driven by one `--rail` property so portrait,
  banner and uptie badge scale together. The grid minimum is tied to it, so
  growing the art never squeezes the text.
- Fusions render as small ingredients → arrow → large result. Unknown
  ingredients show a dashed frame and "Unidentified" — **never invent a
  name**.
- Floor packs are grouped by floor range (six of Bleed+Poise's ten packs are
  all "Floors 5 to 10" — alternatives, not a sequence), each a full-width
  band so dense packs keep their gifts on one row.

## Working agreements

- The guidemaker edits this themselves and is comfortable with git. No CMS.
- Verify rendering changes in the browser; the stylesheet is mtime-versioned
  because the preview pane caches aggressively.
- Report gaps honestly. 71 gift icons have no recoverable name; they render
  as "Unidentified" rather than a guess, and that is deliberate.
- Do not commit `_import/raw/` (226 MB) or `site/assets` PNGs that have a
  WebP sibling.
