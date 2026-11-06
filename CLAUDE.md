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
5. **A note merged across one or two card slots belongs to those cards;
   wider is section prose.** Measured: card notes are 6 or 12 columns wide,
   section prose is 18+. The Pequod substitutes share a single 12-wide note
   anchored at the left slot, so walk back along the stride to find a merge
   that reaches a given column. Treating anything over 6 as prose silently
   dropped that note; treating anything merged as a card note duplicates the
   Floor 1 Sacs "Explanation:" paragraph onto the first card.
6. **Tidy gift and pack names with `name_case`**, which leaves any token
   carrying an internal capital or a dot alone (`BokGak`, `A.B.s`) and keeps
   single-character tokens as written (the `'n` in `Hot 'n Juicy`).

## Verified mappings — extend, don't regenerate

Hand-checked by eye; keyed by image sha256 prefix. Re-deriving them by
inference was tried and was unreliable.

- `tools/status_icons.json` — the seven status icons.
- `tools/card_art.json` — acquisition banners and uptie numerals.
- `tools/name_overrides.json` — canonical spellings no casing rule can
  derive, mostly acronyms the sheet writes inconsistently (`A.B.S`,
  `AEDD`). Keyed by the lowercased sheet name, applied after `name_case`.
  Add here rather than contorting `name_case`, which must stay safe for
  the hundreds of names it already gets right.
- `tools/fusion_recipes.json` — fusion ingredient names, supplied by the
  guidemaker because the sheet never labels ingredient icons. **Written in
  the sheet's own left-to-right order and matched by position.** Tiers are
  a cross-check only: the sheet's tier is authoritative, and a disagreement
  is reported, never used to reorder. (Reordering on recipe tiers was tried
  and was wrong — when a tier is the thing mis-recorded, matching on it
  scrambles the names.) A recipe whose ingredient count or names disagree
  with what was extracted is reported and skipped, never force-fitted.

Unlisted images still render under a hash-derived slug, so a new season
never breaks the build; add an entry to give it a name.

## Visual conventions

Settled with the guidemaker; see `PLAN.md` for the full list.

**The brief is passing a maintainer review, not generic polish.** The other
maintainers dislike the look of vibecoded sites, and the page has to be
approved before the sheets can be retired. So: no uniform rounded cards, no
`system-ui`, no uppercase-letterspaced micro-labels, no hero glow, no
backdrop blur. Those are the tells that got the first version rejected.

**Typography and palette come from the workbooks, not from taste.** Run
`python -I tools/sheetstyle.py _import/raw/*.xlsx` to re-measure. What it
found, weighted by styled cells:

- Fonts: Arial 72% (body), Georgia 2.9% and **Lora** 2.5% (serif display),
  **Silkscreen** 0.7% (pixel accent). Lora and Silkscreen are OFL and
  self-hosted in `site/fonts/` (latin subsets only, ~113 KB); Arial needs no
  download and matches the sheet exactly.
- Fills are warm brown, not neutral black: `#240E02` 25%, `#2E2E2E` 21%,
  `#3E2921` 20%, `#352215` 16%, `#523528` 14%.
- Text golds are saturated yellows: `#F1C232`, `#E9B119`, `#F4C003`.

**Silkscreen is a bitmap face — use it sparingly.** Applying it to every
micro-label made them illegible and gimmicky. It is now limited to the
section index plates, tier badges, the difficulty word, and the team-code
label and button. Other small labels are Lora italic, which reads as a
printed manual rather than a dashboard.

Structure is a field manual: chamfered corners via `clip-path` (never
`border-radius`), hairline gold rules, decimal-leading-zero section plates,
and an SVG paper grain over the page.

- Status is shown as **game icons, never words** — the team title already
  says "Bleed+Poise".
- **Deployment order is meaningful.** The sheet's loadout reads left to
  right as slots 1-N (5 here, 7 on some teams), and cards are extracted in
  column order, so the slot number is just the position. Rendered as a
  gold serif ordinal beside the role and name, **not** as a badge on the
  art — it describes the slot, not the identity. Only the loadout is
  numbered; sacs and substitutes are not a deployment order.
- Footage cards link to the run; they carry an explicit "Watch run"
  affordance rather than relying on the cursor.
- Difficulty is the sheet's skull plus a **5-segment meter** (Easy 1,
  Medium 3, Hard 5).
- Identity art is **never cropped** — `object-fit: contain`.
- The card's left rail is driven by one `--rail` property so portrait,
  banner and uptie badge scale together. The grid minimum is tied to it, so
  growing the art never squeezes the text.
- Fusions render as small ingredients → arrow → large result. Unknown
  ingredients show a dashed frame and "Unidentified" — **never invent a
  name**.
- **Booster-pack art** is a tall portrait in column D of a floor block;
  `find_pack_art` matches on shape and position so the warning glyph and
  status icons in that column are not mistaken for it. Only three packs
  across both workbooks have art, so it renders as a left rail that is
  simply absent otherwise rather than a reserved empty slot. Dropping a
  file at `site/assets/packs/<pack-slug>.webp` makes it appear with no
  code change.
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
