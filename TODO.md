# MDOT — to-do

Outstanding work, roughly in the order it probably wants doing. See `PLAN.md`
for the measured background and the conventions already settled.

## Decide first

- [ ] **Source of truth: sheet or JSON?** Either the workbooks stay canonical
      and `tools/extract.py` re-runs on every update, or the JSON becomes
      canonical and the sheets are archived read-only. Only the second
      actually escapes the 226 MB / merged-cell problem that started this;
      the first keeps re-importing it. This changes how much template drift
      the extractor must tolerate, so settle it before extracting the rest.

## Content gaps

- [ ] **Pack art.** The sheet *does* contain it, and the extractor currently
      drops it. Booster-pack cards are tall (380x690, 298x560), anchored in
      column D inside a floor block with the pack name as the first text
      below them. They have no tier numeral, so the gift rule correctly
      rejects them — but nothing else picks them up.

      Only three packs have art today, across both workbooks:

      | sha | pack | uses |
      |---|---|---|
      | `f91b7922b6` | Mnestic Experience | 21 |
      | `8e95885070` | Nocturnal Sweeping bokgak | 3 |
      | `915e660534` | faith and erosion | 2 |

      Two further tall images are decorative, not pack art (`Teams List` A1,
      and one at column AN on `Bleed+Burn+Poise`) — match on column D inside
      a floor block, not on shape alone, or those get swept in.

      So: add a pack-art rule to `parse_floors`, emit `assets/packs/<slug>`,
      and render it beside the pack heading. The renderer already carries
      `packSlug`. The remaining packs still need art from elsewhere
      (community wiki, game files) before every floor has one.
- [ ] **71 gift icons have no confident name**, rendering as "Unidentified".
      They only ever appear as unlabelled fusion ingredients, so the sheet
      contains nothing to learn from — better parsing cannot fix this. Needs
      an external gift list, or one manual pass naming them against a contact
      sheet (`python -I tools/catalogue.py _import/work <xlsx> <xlsx>` builds
      one at `_import/work/contact.html`).
- [ ] **Pack-name casing drifts** in the source (`line 2`, `lcb regular
      check-up bokgak`). Normalise on a canonical pack list rather than
      title-casing blindly, since some names are deliberately stylised.

## Build out

- [ ] **Extract the remaining 24 teams.** Expect template drift the
      Bleed+Poise tab does not show: `PREFERRED TEAM [AND ORDER]`,
      `IDS FOR DESPERADO`, `BACKUP OPTIONS`, `FLOOR 1 SACS (OPTIONAL)`,
      `SUPPORT PASSIVES (TIME MORATORIUM)`. The extractor should fail loudly
      on an unrecognised section rather than silently dropping it.
- [ ] **Index page** listing all teams with difficulty, statuses and last
      updated — replaces the `Teams List` tab. Note that tab stores
      difficulty and footage slots as *fill colours*, not text.
- [ ] **Search / filter**, the payoff for normalising: which teams use a
      given identity, filter by status, by difficulty, by required IDs. The
      reverse index can be built at compile time from the team JSON.
- [ ] **Shared pages**: `WELCOME` and `FAQ` become Markdown, authored
      directly from here on rather than re-extracted.
- [ ] **Deploy to GitHub Pages** via Actions on push to `main`.

## Polish

- [ ] Fusion rows mix tall fusion stacks with short plain chips, leaving a
      ragged baseline. Readable as-is, but could align better.
- [ ] Decide whether Comfortable vs Niche stays a browsable split or
      collapses into one list with a `tier` field. The split was a Sheets
      limitation, not an editorial choice.
- [ ] Identity portraits are Project Moon art. Re-hosting 264 of them on
      GitHub Pages is the same posture as the current sheet, but worth a
      deliberate decision.
