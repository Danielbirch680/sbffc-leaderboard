#!/usr/bin/env python3
"""
SBFFC cross-league leaderboard engine (Sleeper API, read-only).  Output schema: see docs/SCHEMA.md
Normally run through src/build.py, which reads config/season.json. This module can also run on its own
with an engine-format config (see main()).

Given one Sleeper league ID per SBFFC division, fetches league/users/rosters and weekly matchups,
recomputes SBFFC standings with SBFFC rules (NOT Sleeper's own standings) and writes
leaderboard.json (+ a minimal no-JS leaderboard_basic.html fallback).

Rules implemented (sbffc.com/scoring-rules and /prizes, 2026 text):
  * Week 1 all-play: top half of division scores = W, bottom half = L (tie straddling cut = T; assumption).
  * Weeks 2..reg_end head-to-head by Sleeper matchup_id.
  * Division seeds: 1 best record; 2 most points (if that's seed 1, next best record); 3-4 next best
    records. Record ties -> total points, then H2H among tied teams.
  * 5th-team rule: non-seeded team whose record ties the division's best record -> championship.
  * Wild cards: the top-15% POOL = the floor(wildcard_pct * total_teams) teams with the most total points
    (all divisions, weeks 1..reg_end). A pool team that did NOT already qualify through its division
    (seed 1-4 or 5th team) is a wild card. Pool teams that qualified via their division stay division
    qualifiers; their pool spots are NOT backfilled (prizes/scoring-rules text). So the wild-card count
    varies (0..pool size). Status is "projected" until the regular season is final (see wildcard_final_after_week),
    then "final". The commissioner can settle a points tie at the cutoff with wildcard_overrides (add/remove).
  * Division playoffs: wk13 seed1 v seed4, seed2 v seed3; wk14 final. Points tie -> higher seed (assumption).
  * Championship: avg weekly pts weeks carry_weeks (1-14) + sum champ_weeks (15-17).
  * Consolation: non-qualifiers with >= .500 record; Toilet Bowl: the rest. Both = total pts weeks 13-17.
  * Weekly high score (weeks 1..reg_end) and overall most points through reg_end.
Weekly team points = matchup 'custom_points' (commissioner override) if set, else 'points'.
A week counts as "played" once any team in any division has non-zero points (or per --as-of-week).
"""
import argparse, json, math, os, time, urllib.request, urllib.error, html, datetime
from collections import defaultdict

SCHEMA_VERSION = "2.2"
API = "https://api.sleeper.app/v1"
MIN_INTERVAL = 0.08          # ~12 req/s (=750/min), under Sleeper's ~1000/min guidance
_last = [0.0]

def get(path, cache_dir, refresh=False, offline=False):
    fn = os.path.join(cache_dir, path.strip("/").replace("/", "__") + ".json")
    if os.path.exists(fn) and (not refresh or offline):
        with open(fn) as f:
            return json.load(f)
    if offline:
        raise FileNotFoundError(fn)
    for attempt in range(4):
        wait = MIN_INTERVAL - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "sbffc-leaderboard/2.2 (+https://www.sbffc.com)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            os.makedirs(cache_dir, exist_ok=True)
            with open(fn, "w") as f: json.dump(data, f)
            return data
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3: raise
            time.sleep(2 ** attempt)

# ---------------------------------------------------------------- fetch
def fetch_division(league_id, weeks, cfg):
    cache, offline = cfg.get("cache_dir", "cache"), cfg.get("offline", False)
    refresh = set(cfg.get("refresh_weeks", []))
    lg = get(f"/league/{league_id}", cache, offline=offline)
    users = get(f"/league/{league_id}/users", cache, offline=offline)
    rosters = get(f"/league/{league_id}/rosters", cache, offline=offline)
    umap = {u["user_id"]: u for u in users}
    name = (cfg.get("division_names") or {}).get(str(league_id)) or lg.get("name") or str(league_id)
    teams = {}
    for r in rosters:
        u = umap.get(r.get("owner_id"), {})
        teams[r["roster_id"]] = {
            "key": f"{league_id}:{r['roster_id']}", "league_id": str(league_id), "division": name,
            "roster_id": r["roster_id"], "owner": u.get("display_name") or "(unowned)",
            "team_name": (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}",
            "avatar": u.get("avatar"), "weekly": {}, "matchup_id": {}, "notes": []}
    for w in weeks:
        ms = get(f"/league/{league_id}/matchups/{w}", cache, refresh=(w in refresh), offline=offline)
        for m in ms or []:
            t = teams.get(m["roster_id"])
            if not t: continue
            pts = m.get("custom_points")
            if pts is None: pts = m.get("points") or 0.0
            t["weekly"][w] = round(float(pts), 2)
            t["matchup_id"][w] = m.get("matchup_id")
    return lg, name, list(teams.values())

# ---------------------------------------------------------------- rules
def compute_records(teams, reg_end):
    for t in teams:
        t.update(w=0, l=0, t=0); t["h2h"] = defaultdict(lambda: [0, 0, 0])
    s1 = sorted(teams, key=lambda t: t["weekly"].get(1, 0.0), reverse=True)
    half = len(teams) // 2
    if len(s1) >= 2 and reg_end >= 1:
        hi, lo = s1[half - 1]["weekly"].get(1, 0.0), s1[half]["weekly"].get(1, 0.0)
        for i, t in enumerate(s1):
            p = t["weekly"].get(1, 0.0)
            if hi == lo and p == hi: t["t"] += 1
            elif i < half: t["w"] += 1
            else: t["l"] += 1
    for w in range(2, reg_end + 1):
        groups = defaultdict(list)
        for t in teams:
            mid = t["matchup_id"].get(w)
            if mid is not None: groups[mid].append(t)
        for g in groups.values():
            if len(g) != 2: continue
            a, b = g; pa, pb = a["weekly"].get(w, 0.0), b["weekly"].get(w, 0.0)
            if pa == 0 and pb == 0: continue          # unplayed week
            if pa > pb: a["w"] += 1; b["l"] += 1; a["h2h"][b["key"]][0] += 1; b["h2h"][a["key"]][1] += 1
            elif pb > pa: b["w"] += 1; a["l"] += 1; b["h2h"][a["key"]][0] += 1; a["h2h"][b["key"]][1] += 1
            else: a["t"] += 1; b["t"] += 1; a["h2h"][b["key"]][2] += 1; b["h2h"][a["key"]][2] += 1
    for t in teams:
        t["reg_pts"] = round(sum(t["weekly"].get(w, 0.0) for w in range(1, reg_end + 1)), 2)
        g = t["w"] + t["l"] + t["t"]
        t["win_pct"] = (t["w"] + 0.5 * t["t"]) / g if g else 0.0

def rank_by_record(cands):
    def h2h_pct(t, grp):
        w = l = ti = 0
        for o in grp:
            if o is t: continue
            a = t["h2h"].get(o["key"], [0, 0, 0]); w += a[0]; l += a[1]; ti += a[2]
        n = w + l + ti
        return (w + 0.5 * ti) / n if n else 0.5
    out = sorted(cands, key=lambda t: (-t["win_pct"], -t["reg_pts"]))
    res, i = [], 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and out[j+1]["win_pct"] == out[i]["win_pct"] and out[j+1]["reg_pts"] == out[i]["reg_pts"]:
            j += 1
        grp = out[i:j+1]
        if len(grp) > 1:
            grp = sorted(grp, key=lambda t: -h2h_pct(t, grp))
            for t in grp: t["notes"].append("record+points tie: H2H tiebreak applied")
        res += grp; i = j + 1
    return res

def seed_division(teams):
    order = rank_by_record(teams)
    for i, t in enumerate(order, 1): t["div_rank"] = i
    seeds = [order[0]]
    most = max(teams, key=lambda t: t["reg_pts"])
    if most is not seeds[0]: seeds.append(most)
    for t in order:
        if len(seeds) >= 4: break
        if t not in seeds: seeds.append(t)
    for i, t in enumerate(seeds, 1):
        t["seed"] = i; t["qual_type"] = "division_seed"; t["qualified_via"] = f"Division seed {i}"
    best = order[0]["win_pct"]
    for t in order:
        if "seed" not in t and t["win_pct"] == best:
            t["qual_type"] = "fifth_team"; t["qualified_via"] = "5th team (tied best record)"
    return order, seeds

def play(a, b, week, played):
    """Single H2H game by weekly points; tie -> higher (lower-number) seed advances."""
    pa, pb = a["weekly"].get(week), b["weekly"].get(week)
    g = {"week": week, "home": {"team_key": a["key"], "seed": a["seed"], "points": pa if week in played else None},
         "away": {"team_key": b["key"], "seed": b["seed"], "points": pb if week in played else None},
         "winner": None, "note": None}
    if week in played:
        if (pa or 0) > (pb or 0): g["winner"] = a["key"]
        elif (pb or 0) > (pa or 0): g["winner"] = b["key"]
        else: g["winner"] = a["key"] if a["seed"] < b["seed"] else b["key"]; g["note"] = "tie: higher seed advances (assumed)"
    return g

def division_playoffs(seeds, cfg, played, by_key):
    w1, w2 = cfg["div_playoff_weeks"]
    if len(seeds) < 4: return None
    s = {t["seed"]: t for t in seeds}
    semi = [play(s[1], s[4], w1, played), play(s[2], s[3], w1, played)]
    final = None
    if all(g["winner"] for g in semi):
        a, b = by_key[semi[0]["winner"]], by_key[semi[1]["winner"]]
        final = play(a, b, w2, played)
    else:
        final = {"week": w2, "home": None, "away": None, "winner": None, "note": "awaiting semifinals"}
    champ = final.get("winner")
    runner = None
    if champ:
        runner = final["home"]["team_key"] if final["away"]["team_key"] == champ else final["away"]["team_key"]
    return {"semifinals": semi, "final": final, "champion": champ, "runner_up": runner}

def select_wildcards(all_teams, pct):
    """Top-pct pool by total reg-season points (all teams, all divisions). Pool members without a
    division qualification (qual_type None) become wild cards. Mutates teams; returns summary dict."""
    total = len(all_teams)
    size = math.floor(pct * total + 1e-9)
    ranked = sorted(all_teams, key=lambda t: -t["reg_pts"])      # stable: ties keep input order
    for i, t in enumerate(ranked, 1):
        t["points_rank"] = i; t["in_wc_pool"] = i <= size
    pool = ranked[:size]
    div_q = [t for t in pool if t.get("qual_type")]
    wcs = [t for t in pool if not t.get("qual_type")]
    # a points tie straddling the cutoff only matters if a tied team has no division qualification
    tie = False
    if 0 < size < total and ranked[size]["reg_pts"] == ranked[size - 1]["reg_pts"]:
        tied = [t for t in ranked if t["reg_pts"] == ranked[size - 1]["reg_pts"]]
        tie = any(not t.get("qual_type") for t in tied)
        if tie:
            for t in tied:
                t["notes"].append("tied on points at the top-15% wild-card cutoff - needs commissioner ruling")
    for t in wcs:
        t["qual_type"] = "wild_card"; t["qualified_via"] = "Wild card (top 15% in points)"
    return {"pct": pct, "pool_size": size, "count": len(wcs),
            "pool_division_qualifiers": len(div_q),
            "cutoff_points": pool[-1]["reg_pts"] if pool else None,
            "first_out_points": ranked[size]["reg_pts"] if size < total else None,
            "tie_at_cutoff": tie, "backfill": False,
            "pool": [t["key"] for t in pool], "wild_cards": [t["key"] for t in wcs]}

def _find_team(all_teams, ident):
    """Match a commissioner-typed team: exact team key, team name, or owner name (case-insensitive)."""
    s = str(ident).strip().lower()
    hits = [t for t in all_teams if t["key"].lower() == s] or \
           [t for t in all_teams if t["team_name"].strip().lower() == s] or \
           [t for t in all_teams if t["owner"].strip().lower() == s]
    if len(hits) != 1:
        raise SystemExit(f"wildcard_tie_ruling: '{ident}' matched {len(hits)} teams; use the exact team name "
                         f"(or the team key 'leagueid:rosterid' shown in leaderboard.json) so it matches exactly one team.")
    return hits[0]

def apply_wildcard_overrides(all_teams, ov, wc):
    """Commissioner ruling (e.g. a points tie at the wild-card cutoff): add/remove wild cards by team name."""
    ov = ov or {}
    added, removed = [], []
    for ident in ov.get("remove") or []:
        t = _find_team(all_teams, ident)
        if t.get("qual_type") != "wild_card":
            raise SystemExit(f"wildcard_tie_ruling.remove: '{ident}' is not currently a wild card (it is {t.get('qual_type') or 'not qualified'}).")
        t["qual_type"] = None; t["qualified_via"] = None
        t["notes"].append("removed from wild cards by commissioner ruling")
        removed.append(t["key"])
    for ident in ov.get("add") or []:
        t = _find_team(all_teams, ident)
        if t.get("qual_type"):
            raise SystemExit(f"wildcard_tie_ruling.add: '{ident}' already qualified ({t['qual_type']}).")
        t["qual_type"] = "wild_card"; t["qualified_via"] = "Wild card (top 15% in points)"
        t["notes"].append("added as a wild card by commissioner ruling")
        added.append(t["key"])
    if added or removed:
        wc["wild_cards"] = [k for k in wc["wild_cards"] if k not in removed] + added
        wc["count"] = len(wc["wild_cards"])
        for t in all_teams:
            t["notes"] = [("tied on points at the top-15% wild-card cutoff - settled by commissioner ruling"
                           if "needs commissioner ruling" in n else n) for n in t["notes"]]
    wc["overrides"] = {"added": added, "removed": removed}
    wc["tie_resolved"] = bool(added or removed)
    return wc

# ---------------------------------------------------------------- build
def build(cfg):
    champ_weeks = cfg["champ_weeks"]
    weeks = list(range(1, champ_weeks[-1] + 1))
    divs, all_teams = [], []
    for lid in cfg["leagues"]:
        lg, name, teams = fetch_division(str(lid), weeks, cfg)
        divs.append({"lg": lg, "name": name, "league_id": str(lid), "teams": teams})
        all_teams += teams
    by_key = {t["key"]: t for t in all_teams}

    # which weeks have been played
    if cfg.get("as_of_week") is not None:
        as_of = int(cfg["as_of_week"])
    else:
        as_of = max([w for w in weeks if any(t["weekly"].get(w, 0) for t in all_teams)] or [0])
    played = set(range(1, as_of + 1))
    for t in all_teams:          # blank out unplayed weeks
        for w in list(t["weekly"]):
            if w not in played: t["weekly"][w] = None
    reg_end_eff = min(cfg["reg_end"], as_of)
    tw = lambda t, w: (t["weekly"].get(w) or 0.0)

    div_out = []
    for d in divs:
        for t in d["teams"]:
            t["weekly_num"] = {w: tw(t, w) for w in weeks}
        tmp = [dict(t, weekly={w: tw(t, w) for w in weeks}) for t in d["teams"]]
        compute_records(tmp, reg_end_eff)
        order, seeds = seed_division(tmp)
        for x in tmp:            # copy results back onto real team dicts
            src = by_key[x["key"]]
            for k in ("w", "l", "t", "reg_pts", "win_pct", "div_rank", "seed", "qual_type", "qualified_via", "h2h"):
                if k in x: src[k] = x[k]
            src["notes"] = x["notes"]
        seeds_real = [by_key[x["key"]] for x in seeds]
        for t in seeds_real: t["weekly"] = {w: t["weekly"].get(w) for w in weeks}
        po = division_playoffs([dict(t, weekly={w: tw(t, w) for w in weeks}) for t in seeds_real], cfg, played, by_key)
        best_rec = order[0]["key"]
        most_pts = max(tmp, key=lambda t: t["reg_pts"])["key"]
        div_out.append({"league_id": d["league_id"], "name": d["name"], "season": d["lg"].get("season"),
                        "sleeper_status": d["lg"].get("status"), "num_teams": len(d["teams"]),
                        "standings": [x["key"] for x in order],
                        "awards": {"best_record": best_rec, "most_points": most_pts},
                        "playoffs": po})

    # wild cards: top-15% pool minus division qualifiers (no backfill)
    total = len(all_teams)
    wc = select_wildcards(all_teams, cfg["wildcard_pct"])
    apply_wildcard_overrides(all_teams, cfg.get("wildcard_overrides"), wc)
    final_after = cfg.get("wildcard_final_after_week") or cfg["reg_end"]
    wc_final = (as_of > final_after or (cfg.get("final_through_week") or 0) >= final_after
                or bool(cfg.get("lock_week_final")))
    wc["status"] = "final" if wc_final else "projected"
    wc["final_after_week"] = final_after
    wc["through_week"] = reg_end_eff
    for t in all_teams:
        if t.get("qual_type") == "wild_card":
            t["qualified_via"] = "Wild card (top 15% in points)" + ("" if wc_final else " - projected")
    for t in all_teams:
        if not t.get("qual_type"):
            t["bracket"] = "consolation" if t["win_pct"] >= 0.5 else "toilet_bowl"
        else:
            t["bracket"] = "championship"

    # championship standings + movement
    c_lo, c_hi = cfg["carry_weeks"]
    for t in all_teams:
        cw = [tw(t, w) for w in range(c_lo, c_hi + 1)]
        t["carry_avg"] = round(sum(cw) / len(cw), 2)
    q = [t for t in all_teams if t["bracket"] == "championship"]
    champ_played = [w for w in champ_weeks if w in played]
    def totals_through(k):  # k = None -> carry only
        return {t["key"]: round(t["carry_avg"] + sum(tw(t, w) for w in champ_weeks if k is not None and w <= k and w in played), 2) for t in q}
    def ranks(tot):
        order = sorted(q, key=lambda t: (-tot[t["key"]], -t["reg_pts"]))
        r, prev = {}, None
        for i, t in enumerate(order):
            r[t["key"]] = r[order[i-1]["key"]] if i and tot[t["key"]] == tot[order[i-1]["key"]] else i + 1
        return order, r
    cur_k = champ_played[-1] if champ_played else None
    prev_k = (champ_played[-2] if len(champ_played) >= 2 else None) if champ_played else None
    tot_now = totals_through(cur_k); order, r_now = ranks(tot_now)
    _, r_prev = ranks(totals_through(prev_k)) if cur_k is not None else (None, None)
    champ_rows = []
    for t in order:
        if r_now[t["key"]] > 1 and sum(1 for x in q if tot_now[x["key"]] == tot_now[t["key"]]) > 1:
            t["notes"].append("tied total (no published tiebreak; listed by reg-season points)")
        champ_rows.append({"rank": r_now[t["key"]], "prev_rank": r_prev[t["key"]] if r_prev else None,
                           "movement": (r_prev[t["key"]] - r_now[t["key"]]) if r_prev else None,
                           "team_key": t["key"], "qual_type": t["qual_type"], "qualified_via": t["qualified_via"],
                           "qual_status": wc["status"],
                           "carry_avg": t["carry_avg"],
                           "weeks": {str(w): t["weekly"].get(w) for w in champ_weeks},
                           "total": tot_now[t["key"]]})

    def bracket_rows(kind):
        lo, hi = cfg["consolation_weeks"]
        rows = [t for t in all_teams if t["bracket"] == kind]
        tot = {t["key"]: round(sum(tw(t, w) for w in range(lo, hi + 1)), 2) for t in rows}
        rows.sort(key=lambda t: (-tot[t["key"]], -t["reg_pts"]))
        out = []
        for i, t in enumerate(rows):
            rk = out[-1]["rank"] if i and tot[t["key"]] == tot[rows[i-1]["key"]] else i + 1
            out.append({"rank": rk, "team_key": t["key"], "weeks": {str(w): t["weekly"].get(w) for w in range(lo, hi + 1)},
                        "total": tot[t["key"]]})
        return {"weeks": list(range(lo, hi + 1)), "standings": out}

    weekly_high = []
    for w in range(1, cfg["reg_end"] + 1):
        if w not in played: weekly_high.append({"week": w, "team_key": None, "points": None, "ties": []}); continue
        mx = max(tw(t, w) for t in all_teams)
        tops = [t["key"] for t in all_teams if tw(t, w) == mx]
        weekly_high.append({"week": w, "team_key": tops[0], "points": mx, "ties": tops[1:]})
    most_overall = max(all_teams, key=lambda t: t["reg_pts"]) if all_teams else None

    teams_out = {}
    for t in all_teams:
        teams_out[t["key"]] = {
            "team_name": t["team_name"], "owner": t["owner"], "division": t["division"],
            "league_id": t["league_id"], "roster_id": t["roster_id"],
            "record": {"w": t["w"], "l": t["l"], "t": t["t"]},
            "record_str": f'{t["w"]}-{t["l"]}' + (f'-{t["t"]}' if t["t"] else ""),
            "reg_pts": t["reg_pts"], "div_rank": t.get("div_rank"), "seed": t.get("seed"),
            "qual_type": t.get("qual_type"), "bracket": t["bracket"], "carry_avg": t["carry_avg"],
            "points_rank": t.get("points_rank"), "in_wc_pool": bool(t.get("in_wc_pool")),
            "weekly": {str(w): t["weekly"].get(w) for w in weeks}, "notes": sorted(set(t["notes"]))}

    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return {
        "schema_version": SCHEMA_VERSION, "is_sample": bool(cfg.get("is_sample")),
        "title": cfg.get("title", "SBFFC Championship"), "season": cfg.get("season") or (divs[0]["lg"].get("season") if divs else None),
        "generated_at": now.isoformat(timespec="seconds"),
        "as_of_week": as_of, "final_through_week": cfg.get("final_through_week"),
        "status_note": cfg.get("status_note", "Scores are unofficial until NFL stat corrections are final (typically by Thursday)."),
        "tiebreak_notes": cfg.get("tiebreak_notes") or {},
        "rules": {"reg_end": cfg["reg_end"], "div_playoff_weeks": cfg["div_playoff_weeks"],
                  "carry_weeks": cfg["carry_weeks"], "champ_weeks": champ_weeks,
                  "consolation_weeks": cfg["consolation_weeks"], "wildcard_pct": cfg["wildcard_pct"],
                  "wildcard_lock_week": final_after, "lock_week_final": bool(cfg.get("lock_week_final"))},
        "wildcards": wc,
        "counts": {"teams": total, "divisions": len(div_out), "wildcards": wc["count"],
                   "wildcards_status": wc["status"], "wildcard_pool": wc["pool_size"],
                   "championship": len(champ_rows),
                   "consolation": sum(1 for t in all_teams if t["bracket"] == "consolation"),
                   "toilet_bowl": sum(1 for t in all_teams if t["bracket"] == "toilet_bowl")},
        "teams": teams_out, "divisions": div_out,
        "championship": {"weeks": champ_weeks, "standings": champ_rows},
        "consolation": bracket_rows("consolation"), "toilet_bowl": bracket_rows("toilet_bowl"),
        "weekly_high": weekly_high,
        "most_points_overall": {"team_key": most_overall["key"], "points": most_overall["reg_pts"]} if most_overall else None,
    }

def wc_text(res):
    w = res["wildcards"]
    s = (f"Wild-card pool: top {w['pool_size']} of {res['counts']['teams']} teams ({round(w['pct']*100)}%) by total points "
         f"through Week {w['through_week']}" + (f" (cutoff {w['cutoff_points']:.2f})" if w["cutoff_points"] is not None else "") +
         f". {w['pool_division_qualifiers']} already qualified through their division, so {w['count']} wild card"
         f"{'' if w['count'] == 1 else 's'}")
    s += " (final)." if w["status"] == "final" else f" projected; final count TBD after Week {w['final_after_week']}."
    if w.get("tie_resolved"):
        s += " Includes a commissioner ruling on a points tie at the cutoff."
    elif w.get("tie_at_cutoff"):
        s += " Points tie at the cutoff - awaiting commissioner ruling."
    return s

def basic_html(res):
    T = res["teams"]; wk = res["championship"]["weeks"]
    head = "".join(f"<th>{h}</th>" for h in ["#", "Team", "Owner", "Division", "Qualifier", "Carry"] + [f"Wk{w}" for w in wk] + ["Total"])
    rows = []
    for r in res["championship"]["standings"]:
        t = T[r["team_key"]]
        cells = [r["rank"], t["team_name"], t["owner"], t["division"], r["qual_type"], r["carry_avg"]] + \
                [("" if r["weeks"][str(w)] is None else r["weeks"][str(w)]) for w in wk] + [r["total"]]
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in cells) + "</tr>")
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(res['title'])}</title>"
            f"<p>{'SAMPLE DATA - ' if res['is_sample'] else ''}Updated {res['generated_at']}</p>"
            f"<p>{html.escape(wc_text(res))}</p>"
            + "".join(f"<p><small>{html.escape(str(v))}</small></p>" for v in (res.get("tiebreak_notes") or {}).values()) +
            f"<table border=1 cellpadding=4><tr>{head}</tr>{''.join(rows)}</table>")

DEFAULTS = {"reg_end": 12, "div_playoff_weeks": [13, 14], "carry_weeks": [1, 14], "champ_weeks": [15, 16, 17],
            "consolation_weeks": [13, 17], "wildcard_pct": 0.15, "wildcard_final_after_week": None, "lock_week_final": False,
            "wildcard_overrides": None, "tiebreak_notes": None, "cache_dir": "cache", "refresh_weeks": []}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config"); ap.add_argument("--leagues"); ap.add_argument("--out", default="out")
    ap.add_argument("--as-of-week", type=int); ap.add_argument("--refresh-weeks", default="")
    ap.add_argument("--offline", action="store_true", help="use cache only, no network")
    a = ap.parse_args()
    cfg = dict(DEFAULTS)
    if a.config: cfg.update(json.load(open(a.config)))
    if a.leagues: cfg["leagues"] = [x.strip() for x in a.leagues.split(",") if x.strip()]
    if a.as_of_week is not None: cfg["as_of_week"] = a.as_of_week
    if a.refresh_weeks: cfg["refresh_weeks"] = [int(x) for x in a.refresh_weeks.split(",")]
    if a.offline: cfg["offline"] = True
    if a.config and not os.path.isabs(cfg["cache_dir"]):
        cfg["cache_dir"] = os.path.join(os.path.dirname(os.path.abspath(a.config)), cfg["cache_dir"])
    res = build(cfg)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "leaderboard.json"), "w") as f: json.dump(res, f, indent=1)
    with open(os.path.join(a.out, "leaderboard_basic.html"), "w") as f: f.write(basic_html(res))
    c = res["counts"]
    print(f"{c['teams']} teams / {c['divisions']} divisions; as of week {res['as_of_week']}; "
          f"championship {c['championship']} ({c['wildcards']} WC {c['wildcards_status']} of top-{c['wildcard_pool']} pool), consolation {c['consolation']}, "
          f"toilet {c['toilet_bowl']} -> {a.out}/leaderboard.json")

if __name__ == "__main__":
    main()
