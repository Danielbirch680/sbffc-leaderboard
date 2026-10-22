# config/season.json — every setting explained

JSON files can't hold comments, so the lines in `season.json` that start with `_` (like `"_sample_mode"`) are
notes for humans. The build ignores them. This page has the full explanation.

**Editing rules:** change only the value after the colon. Text goes in "double quotes". Numbers, `true`, `false`
and `null` have no quotes. Every line except the last one in a block ends with a comma. If you break the
format, the next run fails with a message naming the line and column, and the old page stays up until it's fixed.

| Setting | Example | What it does |
|---|---|---|
| `season` | `2026` | Season year shown on the page. |
| `title` | `"SBFFC Championship"` | Page heading. |
| `sample_mode` | `true` | `true` shows the made-up 276-team sample season with a SAMPLE DATA banner. Set it to `false` when all 23 league IDs are filled in. Even when it's `false`, the build stays on sample data until at least one ID is filled in, so the page never goes blank. |
| `divisions` | `{ "name": "Division 1", "sleeper_league_id": "1180315176641138688" }` | One line per division, in the order they appear on the page. `name` is what the page shows. `sleeper_league_id` is the long number in the league's Sleeper web address (`sleeper.com/leagues/<ID>/...`), or in the app under League → Settings → General. It must be digits only. With `sample_mode` off, every division needs an ID. |
| `wildcard_percent` | `15` | The wild-card pool is the top 15% of **all** teams by total points through the lock week, rounded down (276 teams → 41). A pool team that **didn't** qualify through its division (seed 1–4 or 5th team) is a wild card. Pool spots taken by division qualifiers are **not** backfilled, so the number of wild cards changes every season. |
| `wildcard_lock_week` | `12` | The week the wild-card count locks. Until then, the page labels the count "projected · final count TBD". |
| `week12_final` | `false` | Set it to `true` once Week 12 stat corrections are final. The page then shows the wild cards as final straight away. Without it, the count locks by itself once Week 13 scores start. Set it back to `false` at the start of each new season. |
| `wildcard_tie_ruling` | `{"add": ["Bluegrass Mafia"], "remove": ["Dixie Hogs"]}` | Use this only when the page flags a points tie at the wild-card cutoff. Enter exact team names (owner names also work if they're unique). `add` makes a team a wild card. `remove` takes one out. Clear both lists at the start of each new season. |
| `regular_season_last_week` | `12` | Last regular-season week. It's used for records, seeding and wild-card points. |
| `division_playoff_weeks` | `[13, 14]` | Division semifinal and final weeks (seed 1 v 4 and seed 2 v 3). |
| `carryover_average_weeks` | `[1, 14]` | Championship teams start with their average weekly score over these weeks. |
| `championship_weeks` | `[15, 16, 17]` | Points-championship weeks, added to the carry-over average. |
| `consolation_weeks` | `[13, 17]` | Weeks counted for the Consolation and Toilet Bowl brackets. |
| `final_through_week` | `null` | Optional. The last week whose stat corrections are final (for example `15`). The page displays it. Setting it to 12 or higher also finalizes the wild cards. |
| `status_note` | `"Scores are unofficial…"` | Banner text at the top of the page. |
| `tiebreak_notes` | text | The league's tiebreak policy in plain words. It's shown on the plain-table page and stored in leaderboard.json. **Changing this text doesn't change any math.** The math is in `src/sbffc_leaderboard.py`. |
| `display.timezone` | `"America/Chicago"` | Time zone used for the "Updated …" time. Use `America/New_York` for Eastern. |
| `display.prize_places` | `21` | How many championship places are highlighted as paying a prize. |
| `display.auto_refresh_seconds` | `300` | How often an open page re-checks for new scores. `0` turns it off. |
| `public_url` | `"https://danielbirch680.github.io/sbffc-leaderboard/"` | Where the page is published. Update it after moving the repo or adding a custom domain. The Squarespace snippet (`squarespace-code-block.txt`) uses this address. |

## What the build does with it
`src/build.py` reads this file. In **sample mode** it generates the invented season and runs it through the same rules
engine. In **live mode** it fetches every division from Sleeper's public API, which takes about 460 requests and about a
minute. It then applies the SBFFC rules and writes the site to `_site/`.
