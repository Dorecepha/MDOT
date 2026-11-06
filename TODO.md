# MDOT — to-do

Outstanding work. See `PLAN.md` for measured background and `CLAUDE.md` for
the rules a new session needs.

**Status: the Bleed+Poise page is complete and awaiting maintainer review.**
That review is the gate — the sheets cannot be retired until it passes, and
the maintainers specifically dislike the look of generated sites, so the
visual direction is part of the deliverable, not polish on top of it.

---

## Blocked on people, not code

- [ ] **Maintainer review of the Bleed+Poise page.** Everything else below is
      downstream of this.
- [ ] **Source of truth: sheet, JSON, or both?** The maintainers are
      undecided and running both in parallel is on the table. Worth knowing:
      keeping the sheet canonical means re-running the extractor forever and
      living with the 226 MB problem that started this; it does not get
      cheaper later. This decides how defensively the extractor must handle
      template drift, so settle it before porting the other 24.
- [ ] **Project Moon art licensing.** The repo re-hosts 264 identity
      portraits plus gift, status and pack icons. It is private today, but
      GitHub Pages needs it public on a free plan — so this stops being
      theoretical the moment you want to deploy.

## Content

- [x] ~~Pack art~~ — extraction implemented. Booster-pack cards are tall
      portraits in column D of a floor block; `find_pack_art` matches on
      shape and position so warning glyphs and status icons are not picked
      up. Only **3 packs across both workbooks** have art in the sheet
      (Mnestic Experience, Nocturnal Sweeping bokgak, faith and erosion), so
      one shows on this page. `tools/packart.py` sweeps all 25 tabs and has
      extracted every one that exists.
- [x] ~~Gift and pack name capitalisation~~ — `name_case` plus
      `tools/name_overrides.json` for acronyms it cannot derive.
- [x] ~~Unidentified gift icons on this page~~ — the guidemaker's seven
      recipes named the last 13. **0 of 67 gift slots are unidentified.**
- [ ] **Download the pack art.** The images were never missing — the sheet
      references them with `IMAGE()` formulas, so they are not in the
      `.xlsx`. `tools/packurls.py` recovers the URLs from the reference
      sheet's `floor_picture` / `floor_name` catalogue:
      **60 packs catalogued, covering 32 of the 33 used** (the 33rd is
      embedded and already extracted). All that remains is fetching them
      from `limbuscompany.wiki.gg` into `site/assets/packs/`. See
      `docs/pack-art.md`.
- [x] ~~Canonical pack names~~ — `tools/pack_art_urls.json` carries one
      name per pack slug, settling the disagreement between team tabs.
- [ ] **Fusion recipes for the other teams' packs.** The sheet never labels
      ingredient icons, so each new pack needs its recipe added to
      `tools/fusion_recipes.json`. Write ingredients in the sheet's
      left-to-right order; tiers are a cross-check only and a disagreement is
      reported, not acted on.

## Build out

- [ ] **Port the remaining 24 teams.** Expect template drift Bleed+Poise does
      not show: `PREFERRED TEAM [AND ORDER]`, `IDS FOR DESPERADO`,
      `BACKUP OPTIONS`, `FLOOR 1 SACS (OPTIONAL)`,
      `SUPPORT PASSIVES (TIME MORATORIUM)`. The extractor should fail loudly
      on an unrecognised section rather than silently dropping it.
      `MIDDLE` / `SAIKAI` / `IDEAL` are the odd ones and will surface most of
      it — worth doing first.
- [ ] **Index page** listing every team with difficulty, statuses and last
      updated. Replaces the `Teams List` tab, which stores difficulty and
      footage slots as fill colours rather than text.
- [ ] **Search and filter** — which teams use a given identity, filter by
      status, difficulty or required IDs. The payoff for normalising; the
      reverse index builds at compile time from the team JSON.
- [ ] **`WELCOME` and `FAQ`** become hand-authored Markdown rather than
      extracted.
- [ ] **Deploy to GitHub Pages** via Actions on push to `main`. Needs the
      repo public first.

## Polish

- [ ] Rows mixing tall fusion blocks with short plain gift chips leave a
      ragged baseline. Readable, but could align better.
- [ ] Decide whether Comfortable vs Niche stays a browsable split or
      collapses into one list with a `tier` field. The split was a Sheets
      limitation, not an editorial choice.
