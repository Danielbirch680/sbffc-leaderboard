# SBFFC Leaderboard

Live leaderboard for the **Southern Bluegrass Fantasy Football Championship** ([sbffc.com](https://www.sbffc.com)).
Each of the 23 divisions is a Sleeper league. This repo pulls them all through Sleeper's public read-only API, applies the
SBFFC rules and publishes the results with GitHub Pages. It refreshes automatically during game windows.

**Page:** https://danielbirch680.github.io/sbffc-leaderboard/ (see `HANDOFF.md` for the move to the league's GitHub organization)

| You are… | Read |
|---|---|
| The commissioner | **[COMMISSIONER_GUIDE.md](COMMISSIONER_GUIDE.md)**: one-page runbook, no programming |
| Moving the repo to the league | **[HANDOFF.md](HANDOFF.md)** |
| Changing settings | **[docs/SETTINGS.md](docs/SETTINGS.md)** (the file is `config/season.json`) |
| A developer | This page plus [docs/SCHEMA.md](docs/SCHEMA.md) |

## Layout
```
config/season.json                 the only settings file (season, 23 league IDs, wild-card %, lock week, flags)
src/build.py                       one-command build: settings -> _site/   (sample or live)
src/sbffc_leaderboard.py           rules engine + Sleeper fetcher (Python standard library only)
src/make_sample_data.py            invented 276-team season used in sample mode
src/build_site.py                  assembles the published folder + Squarespace snippet
web/                               page sources: index.html, sbffc-leaderboard.css, sbffc-leaderboard.js
tests/test_rules.py                offline tests (rules, settings validation, full sample build)
tools/screenshot.py                optional: headless-Chrome render check (needs Playwright)
.github/workflows/update-leaderboard.yml   test -> build -> deploy Pages (push, manual, schedule)
docs/SETTINGS.md, docs/SCHEMA.md   settings reference, leaderboard.json format
```

## Published files (unchanged URLs)
`index.html`, `leaderboard.html` (same page), `leaderboard.json`, `leaderboard_basic.html` (no-JavaScript table),
`sbffc-leaderboard.css`, `sbffc-leaderboard.js`, `snippet-test.html` (the Squarespace snippet in a simulated page) and
`squarespace-code-block.txt` (paste into a Squarespace Code Block). The build output goes to `_site/`, which isn't committed.
GitHub Actions uploads it as the Pages artifact.

## Rules implemented
Week 1 all-play; head-to-head Weeks 2–12; division seeds (1 = best record, 2 = most points, 3–4 next best records;
ties: points, then H2H); 5th-team rule (ties the division's best record); division playoffs Weeks 13–14 (1v4, 2v3).
**Wild cards:** the top 15% of all teams by total points through Week 12 (rounded down, e.g. 41 of 276) form a pool. Pool teams
that didn't qualify through their division are wild cards. There's **no backfill**, so the count varies. It's shown as projected
until the regular season is final (Week 13 scores, `final_through_week` ≥ 12, or `week12_final: true`), and a tie at the cutoff
is flagged for a commissioner ruling (`wildcard_tie_ruling`). **Championship:** the average weekly score for Weeks 1–14 plus the
Weeks 15–17 total. Consolation (non-qualifiers ≥ .500) and Toilet Bowl use Weeks 13–17 totals. Weekly high score and most points are also shown.
Assumptions to confirm: a tied division playoff game goes to the higher seed, and tied championship totals share a rank.

## Run locally (Python 3.10+; no packages needed)
```bash
python3 tests/test_rules.py           # all tests, offline
python3 src/build.py                  # builds _site/ per config/season.json (sample until league IDs are filled in)
python3 -m http.server -d _site 8765  # open http://localhost:8765/
```
Options: `--sample` (force sample), `--as-of-week N` (pretend only weeks 1..N are played), `--cache DIR` (reuse league/roster
responses between local runs), `--config PATH`.

## Deploy
Repo **Settings → Pages → Source: GitHub Actions** (one time). The workflow runs on every push to `main`, on **Run workflow**,
and on a UTC schedule: every 15 min in Thursday, Sunday and Monday night game windows, December/January Saturdays, and daily at 14:17 UTC.
Edit the commented `cron:` lines to change it. No secrets are needed. A live run makes about 460 Sleeper requests, throttled to 750/min or fewer
(Sleeper asks for under 1000/min), and only one run happens at a time. GitHub Pages serves `leaderboard.json` with `Access-Control-Allow-Origin: *`,
so the Squarespace snippet can load it, and caches responses for about 10 minutes.

## Notes
- Sleeper's API documentation describes it as free for **non-commercial** use. The league collects entry fees, so confirm with Sleeper.
- There's no license file. All rights are reserved by the author unless a license is added.
