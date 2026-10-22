# leaderboard.json — schema 2.2

Produced by `src/sbffc_leaderboard.py` (via `src/build.py`); consumed by `web/sbffc-leaderboard.js` (which refuses data whose `schema_version` major ≠ 2).
Weeks are JSON object keys as **strings** ("15"). `null` points = week not played yet (after `as_of_week`).
Team keys are `"<sleeper_league_id>:<roster_id>"`.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | "2.2" | bump major on breaking changes (2.2 adds `tiebreak_notes`, `rules.wildcard_lock_week`, `rules.lock_week_final`, `wildcards.overrides`, `wildcards.tie_resolved`; 2.1 added `wildcards`, `counts.wildcards_status`, `counts.wildcard_pool`, Team `points_rank`/`in_wc_pool`, ChampRow `qual_status`; `counts.wildcards` is now the actual/projected count, not a fixed 15%) |
| `is_sample` | bool | true → page shows a SAMPLE DATA banner |
| `title`, `season` | string | header text |
| `generated_at` | ISO-8601 with offset | when the job ran (page shows it in `data-timezone`, default America/Chicago) |
| `as_of_week` | int | last week with any scored points (or `--as-of-week`) |
| `final_through_week` | int\|null | optional, set by commissioner once stat corrections are final |
| `status_note` | string | "unofficial until stat corrections" banner text |
| `tiebreak_notes` | {name: string} | free-text tiebreak policy from config/season.json (shown on the plain page) |
| `rules` | object | `reg_end`, `div_playoff_weeks`[2], `carry_weeks`[lo,hi], `champ_weeks`[], `consolation_weeks`[lo,hi], `wildcard_pct`, `wildcard_lock_week`, `lock_week_final` |
| `counts` | object | `teams`, `divisions`, `wildcards` (= `wildcards.count`), `wildcards_status` ("projected"\|"final"), `wildcard_pool` (= `wildcards.pool_size`), `championship`, `consolation`, `toilet_bowl` |
| `wildcards` | object | see Wildcards below |
| `teams` | {key: Team} | see Team below |
| `divisions` | [Division] | in config order |
| `championship` | {weeks[], standings[ChampRow]} | sorted by rank |
| `consolation`, `toilet_bowl` | {weeks[], standings[BracketRow]} | sorted by rank |
| `weekly_high` | [{week, team_key\|null, points\|null, ties[keys]}] | weeks 1..reg_end, overall (all divisions) |
| `most_points_overall` | {team_key, points} | most total points weeks 1..reg_end |

**Team**: `team_name, owner, division, league_id, roster_id, record{w,l,t}, record_str, reg_pts, div_rank, seed (1-4|null), qual_type ("division_seed"|"fifth_team"|"wild_card"|null), bracket ("championship"|"consolation"|"toilet_bowl"), carry_avg, points_rank (1 = most total points Weeks 1..reg_end, all divisions), in_wc_pool (bool), weekly{week: pts|null}, notes[]`

**Wildcards** (SBFFC rule: a team in the top 15% of all teams by total points that did *not* already qualify through its division):
`pct` (0.15), `pool_size` (floor(pct × teams), e.g. 41 of 276), `pool_division_qualifiers` (pool teams that are division seeds / 5th teams),
`count` (= pool_size − pool_division_qualifiers; varies by season), `cutoff_points` (points of the last pool team), `first_out_points`,
`tie_at_cutoff` (a points tie straddles the cutoff and involves a non-division-qualifier → commissioner ruling), `backfill` (false: pool spots taken by
division qualifiers are not refilled), `status` ("projected" until the regular season is final, then "final"), `final_after_week` (reg_end unless
`wildcard_lock_week` is set in config/season.json; final once `as_of_week` > it, `final_through_week` ≥ it, or `week12_final` is true), `through_week`, `pool[keys by points rank]`, `wild_cards[keys]`,
`overrides` ({added[keys], removed[keys]} from `wildcard_tie_ruling`), `tie_resolved` (true if a ruling was applied; `count` then includes it).

**Division**: `league_id, name, season, sleeper_status, num_teams, standings[team keys in SBFFC order], awards{best_record, most_points}, playoffs{semifinals[Game,Game], final Game, champion key|null, runner_up key|null}`
**Game**: `week, home{team_key, seed, points|null}, away{…}, winner key|null, note` (home = higher seed)

**ChampRow**: `rank, prev_rank, movement (prev_rank − rank; + = moved up; null until a championship week has been played), team_key, qual_type, qualified_via, qual_status ("projected"|"final"), carry_avg, weeks{wk: pts|null}, total`
Movement compares standings after the latest played championship week with the week before (for the first championship week, the baseline is carry-over only).

**BracketRow**: `rank, team_key, weeks{wk: pts|null}, total`

Ties: equal totals share a rank (listed by regular-season points) and get a note; SBFFC publishes no tiebreaker for these.
