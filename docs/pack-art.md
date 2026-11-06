# Pack art

## The images are not in the workbooks

The guides reference pack art through Google Sheets' `IMAGE("…")` function
rather than embedding it. Those cells have no cached value, so they read as
empty to any reader and the pictures never reach an `.xlsx` export. Three
packs were pasted in as real images; every other pack looked, from the
export alone, as though it simply had no art.

`New Reference Sheet` holds the authoritative catalogue as a named-range
pair — `floor_picture` (the `IMAGE()` formulas) over `floor_name` (the pack
names) — the same shape as the identity lookup. Row 143 of that sheet
documents the convention in the guidemaker's own words.

## Recovering the URLs

```bash
python -I tools/packurls.py --width 420 _import/raw/comfortable.xlsx _import/raw/niche.xlsx
```

Writes `tools/pack_art_urls.json` as `slug -> {name, url}`. `--width`
rewrites wiki.gg thumbnail URLs to ask for a larger rendering; 420 suits the
148px display size on retina.

Current coverage: **60 packs catalogued, 32 of the 33 used in the guides.**
The remaining one, Mnestic Experience, is embedded in the sheet and already
extracted — so every pack in use is accounted for.

This file is also the source of **canonical pack names**. Team tabs disagree
with each other (`Full-Stopped by a Bullet` vs `Full-stopped by a Bullet`),
and the catalogue settles it.

## Where the files go

```
site/assets/packs/<pack-slug>.png      (or .webp)
```

The filename must be the pack slug exactly, as in `pack_art_urls.json`.
A `.png` is fine — `node tools/optimise.mjs site` converts it to `.webp`,
caps it at 420px and deletes the PNG. Art is attached whenever a file exists
for the slug, whether it was extracted from the sheet or put there by hand,
so nothing else needs changing.

After adding or replacing files:

```bash
node tools/optimise.mjs site
python -I tools/extract.py site "Bleed+Poise" _import/raw/comfortable.xlsx _import/raw/niche.xlsx
python -I tools/render.py site bleed-poise
```

## Shape

Tall booster-pack cards, roughly **0.55 aspect** (the embedded ones are
380x690). Rendered 148px wide beside each pack in Floors to Pick.
