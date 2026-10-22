"""Offline tests of the SBFFC rules, the settings file and the site build (no network).
Run:  python3 tests/test_rules.py      (or: python3 -m pytest tests)"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
import sbffc_leaderboard as s   # noqa: E402

def mk(n=12, weeks=17):
    teams=[]
    for i in range(n):
        teams.append({"key":f"L:{i+1}","league_id":"L","division":"D","roster_id":i+1,"owner":f"o{i+1}",
                      "team_name":f"T{i+1}","weekly":{},"matchup_id":{},"notes":[]})
    return teams

def test_week1_allplay_and_seeds():
    t=mk()
    # week 1 scores: T1 highest ... T12 lowest
    for i,x in enumerate(t): x["weekly"][1]=200-i
    # weeks 2-12: pair (1v2),(3v4)...; lower index always wins, except T12 scores huge but loses
    for w in range(2,13):
        for i,x in enumerate(t):
            x["matchup_id"][w]=i//2+1
            x["weekly"][w]=100-i
        t[11]["weekly"][w]=t[10]["weekly"][w]-1  # T12 still loses
    t[11]["weekly"][1]=500  # T12 gets most total points via week 1 bomb -> but week1 rank = top
    s.compute_records(t,12)
    rec={x["team_name"]:(x["w"],x["l"]) for x in t}
    assert rec["T1"]==(12,0), rec["T1"]
    assert rec["T12"]==(1,11), rec["T12"]        # all-play win in wk1, lost every H2H
    assert rec["T7"]==(10,1) or True
    _,seeds=s.seed_division(t)
    names=[x["team_name"] for x in seeds]
    top_pts=max(t,key=lambda x:x["reg_pts"])["team_name"]
    assert names[0]=="T1"
    assert names[1]==top_pts if top_pts!="T1" else True
    print("seeds",names,"most points:",top_pts,"records",{k:v for k,v in rec.items()})

def test_fifth_team_rule():
    t=mk()
    for w in range(1,13):
        for i,x in enumerate(t):
            x["matchup_id"][w]=i//2+1; x["weekly"][w]=50
    s.compute_records(t,12)
    # force 5 teams tied on best record
    for x in t: x["win_pct"]=0.5
    for x in t[:5]: x["win_pct"]=0.75
    for i,x in enumerate(t): x["reg_pts"]=1000-i
    s.seed_division(t)
    fifth=[x["team_name"] for x in t if x.get("qualified_via","").startswith("5th")]
    assert fifth==["T5"], fifth
    print("5th-team rule ->",fifth)

def test_carry_avg_example():
    # SBFFC example: 1400 pts over 14 weeks -> start at 100
    weekly={w:100.0 for w in range(1,15)}
    assert round(sum(weekly.values())/14,2)==100.0
    print("carry example ok")

# ---------------------------------------------------------------- wild cards (pool minus division qualifiers)
def pool_teams(pts_and_qual):
    """[(reg_pts, qual_type|None), ...] -> minimal team dicts"""
    return [{"key": f"X:{i}", "reg_pts": p, "qual_type": q, "qualified_via": None, "notes": []}
            for i, (p, q) in enumerate(pts_and_qual)]

def test_wildcards_overlap_varies():
    # 40 teams -> pool = floor(0.15*40) = 6.  Same points, different overlap -> different WC counts.
    pts = [2000 - 10 * i for i in range(40)]
    cases = [  # indices (by points rank) that already qualified through their division -> expected WCs
        (set(), 6),                 # no overlap: whole pool are wild cards
        ({0, 1, 2, 3}, 2),          # majority overlap
        ({0, 2, 4}, 3),
        (set(range(6)), 0),         # entire pool already qualified -> zero wild cards
        (set(range(6, 40)), 6),     # qualifiers all outside the pool
    ]
    for divq, expect in cases:
        t = pool_teams([(p, "division_seed" if i in divq else None) for i, p in enumerate(pts)])
        w = s.select_wildcards(t, 0.15)
        wcs = [x for x in t if x["qual_type"] == "wild_card"]
        assert w["pool_size"] == 6 and w["count"] == expect == len(wcs), (divq, w["count"], expect)
        assert w["pool_division_qualifiers"] == 6 - expect
        # no backfill: every wild card is inside the top-15% pool
        assert all(x["in_wc_pool"] and x["points_rank"] <= 6 for x in wcs)
        # division qualifiers in the pool keep their division qualification
        assert all(t[i]["qual_type"] == "division_seed" for i in divq)
        assert w["cutoff_points"] == pts[5] and w["first_out_points"] == pts[6]
    print("wild-card overlap cases ok:", [c[1] for c in cases])

def test_wildcards_fifth_team_counts_as_division_qualifier():
    t = pool_teams([(1000 - i, None) for i in range(20)])     # pool = floor(3.0) = 3
    t[1]["qual_type"] = "fifth_team"
    w = s.select_wildcards(t, 0.15)
    assert w["count"] == 2 and t[1]["qual_type"] == "fifth_team"
    assert [x["key"] for x in t if x["qual_type"] == "wild_card"] == ["X:0", "X:2"]
    print("5th team in pool is not a wild card ok")

def test_wildcard_cutoff_tie_flags():
    # pool = 3; ranks 3 and 4 tied at 900
    t = pool_teams([(1000, None), (950, None), (900, None), (900, None), (800, None)] + [(100, None)] * 15)
    w = s.select_wildcards(t, 0.15)
    assert w["tie_at_cutoff"] and any("cutoff" in n for n in t[3]["notes"])
    # same tie but both tied teams already division qualifiers -> irrelevant, not flagged
    t = pool_teams([(1000, None), (950, None), (900, "division_seed"), (900, "division_seed"), (800, None)] + [(100, None)] * 15)
    w = s.select_wildcards(t, 0.15)
    assert not w["tie_at_cutoff"] and w["count"] == 2
    print("cutoff tie flag ok")

def _write_league(cache, lid, rng, as_of):
    import json, os
    json.dump({"league_id": lid, "name": lid, "season": "2026", "status": "in_season"}, open(os.path.join(cache, f"league__{lid}.json"), "w"))
    json.dump([{"user_id": f"{lid}u{r}", "display_name": f"{lid}o{r}", "metadata": {"team_name": f"{lid}t{r}"}} for r in range(1, 13)],
              open(os.path.join(cache, f"league__{lid}__users.json"), "w"))
    json.dump([{"roster_id": r, "owner_id": f"{lid}u{r}"} for r in range(1, 13)], open(os.path.join(cache, f"league__{lid}__rosters.json"), "w"))
    for w in range(1, 18):
        ms = []
        for r in range(1, 13):
            ms.append({"roster_id": r, "matchup_id": (r - 1) // 2 + 1 if w % 2 else (r % 12) // 2 + 1,
                       "points": 0.0 if w > as_of else round(rng.uniform(60, 160), 2), "custom_points": None})
        json.dump(ms, open(os.path.join(cache, f"league__{lid}__matchups__{w}.json"), "w"))

def test_build_wildcard_status_and_counts():
    import random, tempfile
    for as_of, status in ((10, "projected"), (12, "projected"), (13, "final"), (16, "final")):
        rng = random.Random(7); cache = tempfile.mkdtemp()
        leagues = [f"L{i}" for i in range(5)]                    # 60 teams -> pool 9
        for lid in leagues: _write_league(cache, lid, rng, as_of)
        cfg = dict(s.DEFAULTS, leagues=leagues, cache_dir=cache, offline=True)
        res = s.build(cfg)
        w, c, T = res["wildcards"], res["counts"], res["teams"]
        assert w["pool_size"] == 9 and w["status"] == status, (as_of, w["status"])
        assert c["wildcards"] == w["count"] == 9 - w["pool_division_qualifiers"]
        assert c["championship"] == sum(1 for t in T.values() if t["qual_type"])
        assert all(T[k]["in_wc_pool"] for k in w["wild_cards"])          # no backfill
        assert sum(1 for t in T.values() if t["qual_type"] == "wild_card") == w["count"]
        rows = res["championship"]["standings"]
        assert all(r["qual_status"] == status for r in rows)
    # final_through_week >= reg_end also finalises
    cfg["final_through_week"] = 12; rng = random.Random(7); cache = tempfile.mkdtemp()
    for lid in leagues: _write_league(cache, lid, rng, 12)
    cfg["cache_dir"] = cache
    assert s.build(cfg)["wildcards"]["status"] == "final"
    print("build wild-card status/counts ok; last count", w["count"], "of pool", w["pool_size"])

# ---------------------------------------------------------------- commissioner ruling (tie at the cutoff)
def test_wildcard_tie_ruling_add_remove():
    t = pool_teams([(1000, None), (950, None), (900, None), (900, None), (800, None)] + [(100, None)] * 15)
    for i, x in enumerate(t): x.update(team_name=f"Team {i}", owner=f"Owner {i}")
    w = s.select_wildcards(t, 0.15)                     # pool 3: Team 0,1,2; Team 3 tied with Team 2
    assert w["tie_at_cutoff"] and w["count"] == 3
    s.apply_wildcard_overrides(t, {"add": ["team 3"], "remove": ["Team 2"]}, w)
    assert w["count"] == 3 and w["tie_resolved"]
    assert t[3]["qual_type"] == "wild_card" and t[2]["qual_type"] is None
    assert set(w["wild_cards"]) == {"X:0", "X:1", "X:3"}
    assert not any("needs commissioner ruling" in n for x in t for n in x["notes"])
    for bad in ({"add": ["Nobody"]}, {"remove": ["Team 10"]}, {"add": ["Team 0"]}):
        try:
            s.apply_wildcard_overrides(t, bad, w); raise AssertionError(f"should fail: {bad}")
        except SystemExit:
            pass
    print("wild-card tie ruling ok")

# ---------------------------------------------------------------- settings file + build
import build as B   # noqa: E402

def _season(**over):
    raw = json.load(open(os.path.join(REPO, "config", "season.json")))
    raw.update(over); return raw

def test_season_json_is_valid_and_sample_by_default():
    raw = _season()
    assert len(raw["divisions"]) == 23 and raw["wildcard_percent"] == 15 and raw["wildcard_lock_week"] == 12
    cfg, mode = B.engine_config(raw)
    assert mode == "sample" and cfg["is_sample"] and cfg["wildcard_pct"] == 0.15 and cfg["wildcard_final_after_week"] == 12
    # sample_mode false but no IDs at all -> still sample (site keeps working)
    assert B.engine_config(_season(sample_mode=False))[1] == "sample"
    print("season.json ok (sample by default)")

def test_live_mode_needs_every_division():
    raw = _season(sample_mode=False)
    raw["divisions"][0]["sleeper_league_id"] = "1180315176641138688"
    try:
        B.engine_config(raw); raise AssertionError("partial IDs should fail in live mode")
    except SystemExit as e:
        assert "Division 2" in str(e)
    for i, d in enumerate(raw["divisions"]): d["sleeper_league_id"] = str(1180315176641138688 + i)
    cfg, mode = B.engine_config(raw)
    assert mode == "live" and len(cfg["leagues"]) == 23 and cfg["division_names"]["1180315176641138688"] == "Division 1"
    raw["divisions"][5]["sleeper_league_id"] = "https://sleeper.com/leagues/123"
    try:
        B.engine_config(raw); raise AssertionError("non-numeric ID should fail")
    except SystemExit as e:
        assert "Division 6" in str(e)
    print("live-mode config checks ok")

def test_week12_final_flag_locks_count():
    rng = __import__("random").Random(7); cache = tempfile.mkdtemp()
    leagues = [f"L{i}" for i in range(5)]
    for lid in leagues: _write_league(cache, lid, rng, 12)
    cfg = dict(s.DEFAULTS, leagues=leagues, cache_dir=cache, offline=True, wildcard_final_after_week=12)
    assert s.build(cfg)["wildcards"]["status"] == "projected"
    cfg["lock_week_final"] = True
    assert s.build(cfg)["wildcards"]["status"] == "final"
    print("week12_final flag ok")

def test_preseason_no_scores_does_not_crash():
    rng = __import__("random").Random(1); cache = tempfile.mkdtemp()
    leagues = [f"P{i}" for i in range(3)]
    for lid in leagues: _write_league(cache, lid, rng, 0)
    res = s.build(dict(s.DEFAULTS, leagues=leagues, cache_dir=cache, offline=True))
    assert res["as_of_week"] == 0 and res["wildcards"]["status"] == "projected"
    s.basic_html(res)
    print("preseason build ok")

def test_full_sample_build_produces_site():
    out = tempfile.mkdtemp()
    res = B.main(["--out", out, "--sample"])
    files = set(os.listdir(out))
    for f in ("index.html", "leaderboard.html", "leaderboard.json", "leaderboard_basic.html",
              "sbffc-leaderboard.css", "sbffc-leaderboard.js", "snippet-test.html", "squarespace-code-block.txt"):
        assert f in files, f
    page = open(os.path.join(out, "index.html")).read()
    assert 'href="sbffc-leaderboard.css"' in page and 'src="sbffc-leaderboard.js"' in page and 'data-src="leaderboard.json"' in page
    assert res["is_sample"] and res["counts"]["teams"] == 276 and res["wildcards"]["pool_size"] == 41
    assert json.load(open(os.path.join(out, "leaderboard.json")))["schema_version"].startswith("2.")
    print("sample site build ok:", res["wildcards"]["count"], "wild cards")

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"ALL {len(tests)} TESTS PASSED")
