#!/usr/bin/env python3
"""One-command build: config/season.json -> published site folder.

  python3 src/build.py                 # build into _site/ (what GitHub Actions publishes)
  python3 src/build.py --out other/    # somewhere else
  python3 src/build.py --sample        # force the made-up sample season
  python3 src/build.py --as-of-week 12 # pretend only weeks 1-12 have been played (testing)

Sample mode is used when config "sample_mode" is true OR no Sleeper league IDs are filled in,
so the site keeps working before the real leagues exist. Live mode needs every division filled in.
Live mode fetches from Sleeper's public API (no key needed): about 23 x 20 = 460 requests per run,
throttled to <= 750/minute (Sleeper asks for < 1000/minute).
"""
import argparse, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sbffc_leaderboard as engine   # noqa: E402
import make_sample_data              # noqa: E402
import build_site                    # noqa: E402


class ConfigError(SystemExit):
    pass


def _weeks_pair(v, name):
    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v) and v[0] <= v[1]):
        raise ConfigError(f"config: {name} must look like [first, last], e.g. [13, 17]; got {v!r}")
    return v


def load_config(path):
    try:
        with open(path) as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). "
                          "Usually a missing/extra comma or quote near that spot.")
    return raw


def engine_config(raw, force_sample=False):
    """Translate the friendly season.json into the engine's settings. Returns (cfg, mode, notes)."""
    divs = raw.get("divisions") or []
    if not isinstance(divs, list) or not divs:
        raise ConfigError("config: 'divisions' must be a list of {name, sleeper_league_id}")
    ids = [str(d.get("sleeper_league_id") or "").strip() for d in divs]
    filled = [i for i in ids if i]
    bad = [f"{d.get('name')}: {i!r}" for d, i in zip(divs, ids) if i and not re.fullmatch(r"\d{6,25}", i)]
    if bad:
        raise ConfigError("config: these Sleeper league IDs don't look right (they should be just digits): " + "; ".join(bad))
    if len(set(filled)) != len(filled):
        raise ConfigError("config: the same Sleeper league ID is listed for more than one division")
    sample = bool(force_sample or raw.get("sample_mode", True) or not filled)
    if not sample and len(filled) != len(divs):
        missing = [d.get("name") for d, i in zip(divs, ids) if not i]
        raise ConfigError("config: sample_mode is false but these divisions have no Sleeper league ID: " + ", ".join(missing))
    pct = raw.get("wildcard_percent", 15)
    if not (isinstance(pct, (int, float)) and 0 <= pct <= 100):
        raise ConfigError("config: wildcard_percent must be a number like 15")
    champ = raw.get("championship_weeks", [15, 16, 17])
    cfg = dict(engine.DEFAULTS)
    cfg.update({
        "title": raw.get("title", "SBFFC Championship"),
        "season": str(raw.get("season", "")),
        "is_sample": sample,
        "reg_end": int(raw.get("regular_season_last_week", 12)),
        "div_playoff_weeks": _weeks_pair(raw.get("division_playoff_weeks", [13, 14]), "division_playoff_weeks"),
        "carry_weeks": _weeks_pair(raw.get("carryover_average_weeks", [1, 14]), "carryover_average_weeks"),
        "champ_weeks": champ,
        "consolation_weeks": _weeks_pair(raw.get("consolation_weeks", [13, 17]), "consolation_weeks"),
        "wildcard_pct": pct / 100.0,
        "wildcard_final_after_week": int(raw.get("wildcard_lock_week", 12)),
        "lock_week_final": bool(raw.get("week12_final", False)),
        "final_through_week": raw.get("final_through_week"),
        "wildcard_overrides": raw.get("wildcard_tie_ruling") or {},
        "tiebreak_notes": raw.get("tiebreak_notes") or {},
    })
    if raw.get("status_note"):
        cfg["status_note"] = raw["status_note"]
    if not sample:
        cfg["leagues"] = ids
        cfg["division_names"] = {i: d.get("name") for d, i in zip(divs, ids) if d.get("name")}
    return cfg, ("sample" if sample else "live")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(REPO, "config", "season.json"))
    ap.add_argument("--out", default=os.path.join(REPO, "_site"))
    ap.add_argument("--sample", action="store_true", help="force sample data")
    ap.add_argument("--as-of-week", type=int)
    ap.add_argument("--cache", help="keep Sleeper responses in this folder and reuse them (default: fresh fetch)")
    a = ap.parse_args(argv)

    raw = load_config(a.config)
    cfg, mode = engine_config(raw, a.sample)
    work = tempfile.mkdtemp(prefix="sbffc-build-")
    try:
        if mode == "sample":
            cfg["leagues"] = make_sample_data.generate(work)
            cfg["cache_dir"] = os.path.join(work, "cache")
            cfg["offline"] = True
        else:
            cfg["cache_dir"] = os.path.abspath(a.cache) if a.cache else os.path.join(work, "cache")
            if a.cache:   # reuse league/users/rosters, but always re-fetch weekly scores
                cfg["refresh_weeks"] = list(range(1, cfg["champ_weeks"][-1] + 1))
        if a.as_of_week is not None:
            cfg["as_of_week"] = a.as_of_week
        res = engine.build(cfg)
        data = os.path.join(work, "out"); os.makedirs(data)
        with open(os.path.join(data, "leaderboard.json"), "w") as f: json.dump(res, f, indent=1)
        with open(os.path.join(data, "leaderboard_basic.html"), "w") as f: f.write(engine.basic_html(res))
        if os.path.isdir(a.out):
            shutil.rmtree(a.out)
        files = build_site.assemble(a.out, data, raw.get("display") or {}, raw.get("public_url"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    c, w = res["counts"], res["wildcards"]
    print(f"[{mode}] {c['teams']} teams / {c['divisions']} divisions, as of week {res['as_of_week']}: "
          f"championship {c['championship']} ({w['count']} wild cards, {w['status']}, pool {w['pool_size']}"
          f"{', TIE AT CUTOFF' if w['tie_at_cutoff'] and not w.get('tie_resolved') else ''}), "
          f"consolation {c['consolation']}, toilet bowl {c['toilet_bowl']}")
    print(f"site -> {a.out}: {', '.join(files)}")
    return res


if __name__ == "__main__":
    main()
