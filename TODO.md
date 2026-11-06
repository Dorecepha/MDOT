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
- [ ] **Art for the other 30 packs.** A sweep of all 25 tabs
      (`python -I tools/packart.py site _import/raw/*.xlsx`) finds **33
      distinct packs and only 3 with art in the source**: Mnestic
      Experience, Faith and Erosion, Nocturnal Sweeping Bokgak. The other
      30 need images from elsewhere — a community wiki or game files —
      dropped at `site/assets/packs/<pack-slug>.webp`. The renderer picks
      them up with no code change; run the sweep for the current slug list.
- [ ] **Canonical pack names.** The same pack is spelled differently across
      tabs (`Full-Stopped by a Bullet` vs `Full-stopped by a Bullet`,
      `LCB Regular Check-up BokGak` vs `… Bokgak`). Slugs already unify
      them, so the asset library is fine, but a `packs.json` holding one
      display name per slug is wanted before the index page.
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
