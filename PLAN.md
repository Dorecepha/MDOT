# MDOT — Migrating the MDE Team Guides off Google Sheets

**Status: Bleed+Poise prototype standing.** Extraction, asset library and a
rendered page all work end to end. Evidence below is measured, not estimated.

Pipeline (re-runnable from scratch at any time):

```bash
python -I tools/extract.py site "Bleed+Poise" _import/raw/comfortable.xlsx _import/raw/niche.xlsx
node tools/optimise.mjs site
python -I tools/render.py site bleed-poise
```

Built so far:

| Output | State |
|---|---|
| `site/data/identities.json` | 388 identities, 264 with portraits, incl. nickname aliases |
| `site/data/gifts.json` | 167 EGO gift icons resolved to names (82 still ambiguous) |
| `site/data/teams/bleed-poise.json` | full guide: roster, substitutes, gifts, 10 floor packs, 2 checklists |
| `site/assets/` | 418 images, **9.5 MB** (from 102 MB of PNG — 91% smaller) |
| `site/bleed-poise.html` | rendered page, 35 KB |

Known gaps: 82 gift icons have no confident name (they only ever appear as
unlabelled fusion ingredients, so they render as "Unidentified" rather than
guessing); pack-name casing still drifts (`line 2`, `lcb regular check-up
bokgak`).

### Visual conventions

- **Status** is shown as the game's own icons, never as words — the title
  already says "Bleed+Poise". All seven were recovered from the workbooks and
  verified by eye; the sha mapping lives in `tools/status_icons.json`.
- **Difficulty** is the sheet's own skull plus a 5-segment meter. The sheet
  only uses Easy / Medium / Hard, mapped to 1 / 3 / 5 so finer tiers drop in
  without redrawing (`DIFFICULTY_LEVELS` in `tools/extract.py`).
- **Identity art is never cropped** — 78px thumbnail, `object-fit: contain`,
  beside the text rather than above it, so the explanation carries the card.
- **Fusions** render as small ingredients → join arrow → large result.
  Unknown ingredients show a dashed frame and "Unidentified". Two rules make
  this correct, and both were wrong at first:
  - A tier/name scan **must stop at the next block boundary** (`block_bounds`
    in `tools/extract.py`). Without it a fusion "+" separator and the Poise
    status icon in gutter columns picked up a tier and name from the pack
    *below*, which both invented fusions and attached the wrong icon to
    "Ragged Bamboo Hat" and "Old Dopo Robe".
  - An ingredient binds to the nearest result **at or to its left** on the
    first result row beneath it, never the nearest column overall. Ingredient
    strips are left-aligned with their result and run rightward to the next
    result's column.
- **Identity cards carry a left rail**: portrait, uptie numeral badged on its
  corner, and the acquisition banner as a small swatch beneath. Banner and
  uptie images are verified by hash in `tools/card_art.json`; anything
  unlisted still renders under a hash-derived slug, so a new season does not
  break the build. The rail is driven by one `--rail` custom property so
  portrait, banner and badge always scale together — 112px on the preferred
  loadout (two cards per row), 80px on the reference rosters (three per row).
  The grid minimum is tied to it so growing the art never squeezes the text.
- **Hierarchy**: the preferred loadout gets full-size cards; sacs,
  substitutes and warnings get a compact variant and a muted heading.
- A **sticky section index** sits under the hero; every section has an anchor.
- **Floors to Pick groups packs by floor range.** Six of this team's ten packs
  are all "Floors 5 to 10" — alternatives for one stage, not a sequence — so
  they sit under a single heading that says how many there are to choose
  from. Each pack then gets a full-width band rather than a column in a
  three-up grid, which is what made dense packs congested: the worst one has
  seven gifts including four fusions, and now fits on one row. Guidance prose
  flows into two columns so it does not run the full 1200px.

## 0. Editing model (the thing that has to stay easy)

The stated update pipeline is: new Identity drops → update `ID Catalogue` if
needed → update the affected teams (mostly swapping an icon and rewriting the
explanation) → occasionally change packs-to-take or a video link.

The data model is shaped around exactly that. Teams reference identities **by
slug**, never by embedded image:

```json
{ "role": "BL Filler", "id": "blade-lineage-faust",
  "notes": ["Exists here to be the 3rd BL ID and activate the BL gifts."] }
```

So swapping an ID is a one-line edit and the portrait, canonical name and
status tags follow automatically from `identities.json`. No image handling, no
copy-paste between tabs, and nothing to keep in sync across 25 guides — which
is the duplication that broke the spreadsheet in the first place.

Still to decide (deferred by agreement): whether the sheet stays the source of
truth with the extractor re-run on each update, or the JSON becomes canonical
and the sheet is archived. The second is the only one that actually escapes
the 226 MB problem; the first keeps re-importing it.

## 1. Why Sheets keeps bricking

Measured from the two `.xlsx` exports:

| | Comfortable | Niche |
|---|---|---|
| File size | 112.6 MB | 115.4 MB |
| Embedded PNGs | 628 (111.7 MB) | 702 (114.6 MB) |
| Team tabs | 15 | 10 |
| Merged ranges (one team tab) | 467 | — |
| Anchored images (one team tab) | 215 | — |

**1,330 embedded images totalling 226 MB across the two workbooks.** 755 are unique by
content hash (116 MB); the other 110 MB is pure duplication, mostly the six shared tabs
being copy-pasted into both workbooks.

The row/column count was never the problem — 25 tabs × ~190 rows is nothing. The problem is
image payload plus ~467 merged ranges and conditional formatting per tab. That is what makes
Sheets refuse to save, and it is why the guides already had to be split into two workbooks.
A third split is the default future if nothing changes.

Images are also wildly oversized for their display size:

- Footage thumbnails: 0.9–1.8 MB each, 5 per team (`image76.png` alone is 1.49 MB)
- ID portraits: 500×500, 390×390, 256×256
- Gift icons: 120×120, 74×74
- UI chrome (tier badges, frames): 1–17 KB, reused hundreds of times

Properly sized WebP plus YouTube thumbnail URLs for footage should land the entire site
under ~5 MB. That is a >40× reduction and is the migration's main technical payoff.

## 2. Why this migration is tractable

Every team tab is the **same rigid template**. Content sits at fixed column strides — 6
columns for ID cards (D, J, P, V, AB, AH, AN), 3 columns for gift icon + tier badge pairs
(D, G, J, M, P, S, V, Y, …) — and sections always appear in this vertical order:

```
Header   → team name · guidemaker · 5 footage slots · description · difficulty
            · last updated · Team Code
Roster   → Preferred Team (role label + ID + notes) · Floor 1 Sacs · Substitutes
Warnings → Skill Replacement Warning (per-ID caveats)
Gifts    → Graces · Starting Gifts · Gift Search (tier numerals I–IV)
Floors   → per floor: pack name + gift list + floor information
```

Images anchor at the same strides as their text labels, so an extractor can map
**image → anchor cell → adjacent ID/gift name** deterministically. Portraits reuse identical
bytes across tabs, so the ID→portrait mapping is built once and cross-validated: if the same
hash always sits beside "Blade of the House of Spiders Ryoshu", that is the portrait.

This turns a 25-page manual rewrite into one extractor plus a human review pass.

## 3. Data quality issues the sheet has been hiding

Casing and spelling drift across tabs. Sheets tolerated this because nothing joined on
these strings; a searchable database will not:

| Team tab says | `ID Catalogue` says |
|---|---|
| `Index Apprentice Don QUixote` | `Don Quixote` |
| `hornet Meursault` | `Hornet Meursault` |
| `S Corp. hong Lu` | `S Corp. Hong Lu` |

**Consequence:** a filter like "teams using Hornet Meursault" silently misses tabs with the
lowercase variant. The extractor must normalize against a canonical identity list and
**fail loudly** on any name it cannot resolve, rather than guessing. Expect a one-time
cleanup pass of maybe 20–50 such mismatches.

Also note: `DIFFICULTY` and `FOOTAGE SLOTS` on `Teams List` are **fill colours, not text**.
Two changelog entries read "Colour-coding update." Any CSV-based extraction silently loses
this dimension — which is why extraction goes through `.xlsx`, never CSV.

## 4. Proposed data model

Per-team files plus shared reference collections. One team becomes
`src/content/teams/bleed-poise.json`:

```json
{
  "slug": "bleed-poise",
  "name": "Bleed+Poise",
  "collection": "comfortable",
  "statuses": ["Bleed", "Poise"],
  "difficulty": "Easy",
  "guidemaker": "Vladsault",
  "lastUpdated": "2026-10-25",
  "teamCode": "H4sIAAAAAAAAChXMoQ6AIBRA0Z+yGi48lOfmgDGDWTd0BiN8vlhPOFIpTQ…",
  "description": "This guide is for the Bleed+Poise double status team…",
  "footageWindow": "F11-F15",
  "footage": [
    { "contributor": "vladsault", "label": "No Commentary (Current Team)",
      "mdTier": "MD7", "url": "https://youtu.be/…", "secretBossGifts": 1 }
  ],
  "loadouts": [
    { "name": "Preferred Team",
      "note": "Only 5 IDs are used so that Ryoshu starts with 3 skill slots from turn 1…",
      "slots": [
        { "role": "Erasing You, Erasing Every HoS ID",
          "id": "blade-of-the-house-of-spiders-ryoshu",
          "notes": ["She will be the main focus of the team since…"] }
      ] }
  ],
  "floorOneSacs": { "explanation": "The new ego gift \"Spiderweb Entangled in Red\"…",
                    "ids": ["index-nursefather-yi-sang", "…"] },
  "substitutes": { "note": "Always have 5 bleed and …",
                   "entries": [ { "id": "hornet-meursault", "notes": ["…"] } ] },
  "skillReplacementWarnings": [
    { "id": "pequod-heathcliff",
      "warnings": ["Skill 3 doesn't gain poise, so it doesn't count as a poise skill"] }
  ],
  "egoGifts": {
    "starting": [ { "gift": "wound-clerid", "tier": 2 }, { "gift": "awe", "tier": 2 } ],
    "startingNote": "You could also start with the poise ego gifts, but…",
    "search":   [ { "gift": "prestige-card", "tier": 3 } ],
    "searchNote": "You will need a lot of Cost to get all of the required EGO gifts"
  },
  "floors": [
    { "floor": "1", "pack": "automated-factory",
      "gifts": [ { "gift": "hoarfrost-footprint", "tier": 4 } ],
      "info": "Don't forget to kill all HoS sacs in this floor…" }
  ]
}
```

Shared collections, each keyed by slug — these are the six duplicated tabs, deduplicated
into one source of truth:

- `identities.json` — canonical name, sinner, statuses, portrait asset, **aliases** (this is
  where `hornet Meursault` resolves to `hornet-meursault`)
- `gifts.json` — name, tier, icon, status affinity
- `packs.json` — name, floors where available
- `contributors.json` — guidemakers and footage providers
- `faq.md`, `welcome.md` — prose, authored directly as Markdown from here on

Because IDs and gifts are referenced by slug rather than repeated as free text, the search
you asked for ("which teams use Pequod Ishmael", filter by status/difficulty/required ID)
becomes a trivial reverse index built at compile time.

## 5. Recommended sequence

**Step 1 — Lock the schema by hand (do this first).**
Hand-write `bleed-poise.json` completely, from the real tab. It is the messiest case: two
loadout variants and 5-vs-6-vs-7 ID branching buried in the notes. If the schema survives
this tab it survives all 25. Writing the extractor first means discovering the schema is
wrong at team 20.

**Step 2 — Build the extractor.**
`tools/` already has the start of it (see §6). Emits 25 JSON files + the shared collections.
Hard requirement: unresolvable ID/gift names abort the run with a report. No silent guesses.

**Step 3 — Asset pipeline.**
Dedupe the 755 unique images by hash, drop UI chrome (becomes CSS/SVG), drop footage
thumbnails (use YouTube's own thumbnail URLs), re-encode portraits and gift icons to WebP at
2× display size. Target: ~5 MB total.

**Step 4 — Site.**
Astro with content collections and Zod schemas. Zod validates every team file at build time,
so a malformed guide fails the build instead of silently rendering wrong — the safety net
Sheets never gave you. Static output, no client JS except the search index.

**Step 5 — Deploy.**
GitHub Pages via Actions on push to `main`. Set Sheets to read-only and link it as an
archive; do not keep it as a parallel source of truth.

**Step 6 — Cutover.**
Announce, redirect, keep the Sheets archive reachable for one patch cycle.

## 6. What already exists

| File | Purpose |
|---|---|
| `tools/cellmap.py` | Dump non-empty cells of a CSV export as an A1-addressed map |
| `tools/zipsurvey.py` | Report where an `.xlsx`'s weight sits, by part and media type |
| `tools/mediadedupe.py` | Hash all embedded images, report unique count and duplication |
| `tools/anchors.py` | Map embedded images to anchor cells; list merged ranges |

All stdlib-only — `pip` is unavailable in this environment, so the extractor should stay
dependency-free (`zipfile` + `xml.etree` is sufficient for everything needed here).

`_import/raw/` holds the two 112 MB workbook exports. **Do not commit it** — add to
`.gitignore` before the first commit. Re-download with:

```bash
curl -L "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=xlsx" -o out.xlsx
```

## 7. Open questions

1. **Portrait licensing / sourcing.** The portraits are Project Moon art. Re-hosting 755
   images on GitHub Pages is the same posture as the current sheet, but worth a deliberate
   decision. An alternative is pulling icons from an existing community CDN if one is
   stable.
2. **`MIDDLE`, `SAIKAI`, `IDEAL`** are named teams rather than status combos. Confirm whether
   they need a different page shape or just a `statuses: []` plus a display name.
3. **Comfortable vs Niche** — keep as a browsable distinction, or collapse into a single team
   list with a `tier` field and filter? The split was a Sheets limitation, not editorial.
