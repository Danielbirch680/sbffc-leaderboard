# SBFFC Leaderboard: Commissioner Guide

## What this is
The SBFFC divisions each run as a Sleeper league. This project reads all 23 leagues from Sleeper's public data and applies the
SBFFC rules: Week 1 all-play, seeding, the 5th-team rule, wild cards, and the carry-over average plus the Weeks 15–17 points
championship. It then publishes a leaderboard web page. During the season the page updates itself, so there's nothing to
install and nothing to run on your own computer. Everything is done on GitHub's website.

## Where things live
- **The page:** https://danielbirch680.github.io/sbffc-leaderboard/. The address changes if the repo moves; see HANDOFF.md.
  `leaderboard.html` is the same page. `leaderboard_basic.html` is a plain table. `leaderboard.json` is the raw data.
- **The settings:** `config/season.json` in this repo. It's the only file you normally touch. Every setting is
  explained in `docs/SETTINGS.md`.
- **The update job:** the **Actions** tab, workflow **"Update SBFFC leaderboard"**.

## Each season (about 15 minutes)
1. In the repo, open `config/season.json` and click the **pencil icon (Edit)**.
2. Set `"season"` to the new year.
3. For each division, paste its Sleeper league ID between the quotes, and fix the name if needed. The ID is the long
   number in the league's address: `sleeper.com/leagues/`**`1180315176641138688`**`/...`.
4. Reset `"week12_final": false`, `"final_through_week": null`, and empty both `wildcard_tie_ruling` lists (`[]`).
5. **Turn sample mode off:** change `"sample_mode": true` to `"sample_mode": false`.
6. Click **Commit changes** and commit directly to `main`. The page rebuilds within a couple of minutes. Check the
   **Actions** tab: a green check means it worked.

Tip: keep `"sample_mode": true` until **all 23** IDs are in. If sample mode is off and any division is missing an ID, the
build stops with a message naming that division, and the previous page stays up.

## Updating by hand
The page updates by itself every 15 minutes during game windows (Thursday, Sunday and Monday nights, plus December
Saturdays) and once a day otherwise. To update right now, go to **Actions → Update SBFFC leaderboard → Run workflow →
Run workflow**. A run takes about 2 minutes. Browsers and GitHub can cache the page for up to 10 more minutes.

## Marking Week 12 final (locks the wild cards)
A wild card is a team in the top 15% of all teams by points through Week 12 that **didn't** already qualify
through its division. There's no backfill, so the number of wild cards changes every year. Until the count is final,
the page shows it as *projected · final count TBD*.
The count becomes final on its own once Week 13 scores start. To lock it earlier, as soon as Week 12 stat corrections
are done, edit `config/season.json`, set `"week12_final": true`, and commit.

## A tie at the wild-card cutoff
If two or more teams are tied on points right at the 15% line and the tie decides who gets a spot, the page says
**"Points tie at the cutoff — awaiting commissioner ruling"**, and the affected teams carry a note. Use the league's rule
to decide who gets in, then record the ruling in `config/season.json` with exact team names:
```
"wildcard_tie_ruling": { "add": ["Team That Gets In"], "remove": ["Team That Is Out"] },
```
Use `add` for a team currently listed outside the wild cards and `remove` for a team currently inside them. Commit, and the
page then says the count includes a commissioner ruling. If a name doesn't match exactly one team, the run fails and
tells you why.
Other ties: SBFFC's rules don't publish a tiebreaker for division playoff games or championship totals. The page
currently sends the **higher seed** through in a tied division playoff game, and has tied championship totals **share a
rank**. Decide whether to keep these and update the `tiebreak_notes` text to match. Changing the actual math needs a small
code change in `src/sbffc_leaderboard.py`.

## Putting it on sbffc.com (Squarespace)
- **Core, Plus or Advanced plan:** open `<page address>/squarespace-code-block.txt`, select all and copy it. In Squarespace,
  edit a page, choose **Add Block → Code**, set the mode to **HTML**, paste, turn **Display Source** off, and save. The
  leaderboard then shows inside the sbffc.com page and refreshes itself. If it doesn't show while you're logged in, check
  in a logged-out or private browser window.
- **Simpler, same plans:** put `<iframe src="PAGE ADDRESS" style="width:100%;height:1600px;border:0"></iframe>` in a
  Code Block.
- **Basic plan:** Squarespace doesn't run JavaScript or iframes in Code Blocks on Basic. Add a **Button** or a
  navigation link to the page address instead.

## Custom address (e.g. leaderboard.sbffc.com)
1. Wherever sbffc.com's DNS is managed (Squarespace Domains if the domain was bought there), add a record:
   **CNAME**, host **`leaderboard`**, value **`<owner>.github.io`** (for example `sbffc.github.io`).
2. In this repo, go to **Settings → Pages → Custom domain**, enter `leaderboard.sbffc.com` and click **Save**. Once the
   check passes, tick **Enforce HTTPS**. DNS can take up to a day.
3. Set `"public_url": "https://leaderboard.sbffc.com/"` in `config/season.json`, then re-copy the Squarespace snippet.

## If it breaks
- **Red X in Actions:** click the run, then the failed step. The error explains the problem in plain words. The usual
  cause is a typo in `season.json` (a missing comma or quote) or a bad league ID. Fix it, commit, and the page
  rebuilds. The old page stays up in the meantime.
- **The page isn't updating:** check the Actions tab. GitHub **switches off scheduled runs after 60 days with no repo
  activity**. If you see a banner, click **Enable workflow**. Committing your season settings each year also keeps the
  schedule active. Scheduled runs can also start a few minutes late, so use **Run workflow** when it matters.
- **Sleeper is down or slow:** the run fails and the page keeps the last good scores. Run it again later.
- **Scores look wrong:** compare against Sleeper. Commissioner score edits made in Sleeper are picked up on the next run.
  Need help? Open an Issue in this repo or contact the maintainer listed in HANDOFF.md.

## Sleeper's terms (please read)
Sleeper's API is free and needs no key, but its documentation says it's for **non-commercial use**. The SBFFC collects
entry fees and pays prizes, so the league should **confirm with Sleeper** that this use is OK, or get permission,
before relying on it for a paid season. This project only reads public league data, about 460 requests per update,
well under Sleeper's limit of about 1,000 per minute.
