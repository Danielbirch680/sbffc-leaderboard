#!/usr/bin/env python3
"""Generate SAMPLE (made-up) Sleeper-shaped data: 23 divisions x 12 teams = 276 teams.

Writes the same JSON files the Sleeper API returns into a cache folder, so the real engine
(sbffc_leaderboard.py, offline mode) is exercised end to end. All names are invented.
Used automatically by build.py when sample_mode is on (or no league IDs are filled in).
Deterministic: the same seed always produces the same season.

CLI:  python3 src/make_sample_data.py OUT_DIR     -> OUT_DIR/cache/*.json + OUT_DIR/config_sample.json
"""
import json, os, random, sys

FIRST = "Brian Jeff Jon Matt Luke Dave Steve Kelly Mike Jeremy Jim Roc Nathan Danny Bradley Ricky Kris Chris Jason Craig Larry Tony Reid Willie Curtis Todd Derrick Kyle Josh Ryan Cody Travis Dustin Brandon Wes Shane Casey Logan Tyler Drew Blake Grant Heath Jared Corey Brent Chad Trey Marcus Andre Darius Terrell Amanda Ashlee Kiera Stephanie Jenna Holly".split()
LAST = "Harwood Richardson Patterson Krantz Keith Barkes Kurowsky Thompson Dauzat Ramos Collis Frost Klein Young White Desselle Lachney Irwin Vincent Wiggins Campbell Nelson Rhoades Whittaker Vann McIntyre Barton Bridwell Gipson Hirst Aringer Holt Pruitt Mattingly Combs Duncan Hatfield Mayes Spurlock Gaines Pendleton Akers Tuttle Burchett Lawrence Quinn Ashford Studle Daugherty Napier Goins Riggs".split()
A = "Bowling Green|Barren River|Hilltopper|Cumberland|Bluegrass|Corvette City|Lost River|Big Red|Mammoth Cave|Warren County|Smiths Grove|Scottsville|Glasgow|Franklin|Russellville|Nashville|Louisville|Lexington|Owensboro|Paducah|Philpot|Mayberry|Dixie|Cajun|Southern|Overtime|Tickle|Swiperz|Temple".split("|")
B = "Mafia|Smackdown|Kryptonite|Stash|Gravediggers|Monsters|Feelers|TD Party|Krew|Chickens|Blasters|Nation|Thunder|Outlaws|Moonshiners|Bourbon Boys|Hitmen|Ballers|Wrecking Crew|Sharks|Hogs|Mules|Coyotes|Gamblers|Bandits|Pickers|Rednecks|Rebels|Express|Dynasty|Dawgs|Sluggers|Goats|Legends".split("|")

AS_OF = 16          # sample season snapshot: weeks 1-16 scored, week 17 not yet played


def rr_schedule(n=12):
    """circle method: n-1 rounds, each a list of (i, j) pairs (0-based)"""
    ids = list(range(n)); rounds = []
    for r in range(n - 1):
        rounds.append([(ids[i], ids[n - 1 - i]) for i in range(n // 2)])
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return rounds


def generate(out_dir, divisions=23, teams_per_div=12, weeks=17, as_of=AS_OF, seed=2026):
    """Write a sample season under out_dir/cache. Returns the list of fake league IDs."""
    rng = random.Random(seed)
    cache = os.path.join(out_dir, "cache"); os.makedirs(cache, exist_ok=True)
    used = set()

    def team_name():
        while True:
            n = f"{rng.choice(A)} {rng.choice(B)}"
            if n not in used: used.add(n); return n

    def owner():
        return f"{rng.choice(FIRST)} {rng.choice(LAST)}"

    def dump(obj, name):
        with open(os.path.join(cache, name), "w") as f: json.dump(obj, f)

    leagues = []
    for d in range(1, divisions + 1):
        lid = f"sample{d:02d}"
        leagues.append(lid)
        users, rosters = [], []
        skill = [rng.gauss(118, 9) for _ in range(teams_per_div)]
        for r in range(1, teams_per_div + 1):
            uid = f"{lid}u{r}"
            users.append({"user_id": uid, "display_name": owner(), "avatar": None, "metadata": {"team_name": team_name()}})
            rosters.append({"roster_id": r, "owner_id": uid, "league_id": lid, "settings": {}})
        dump({"league_id": lid, "name": f"Division {d}", "season": "2026", "status": "in_season",
              "total_rosters": teams_per_div, "settings": {}}, f"league__{lid}.json")
        dump(users, f"league__{lid}__users.json")
        dump(rosters, f"league__{lid}__rosters.json")
        sched = rr_schedule(teams_per_div)
        for w in range(1, weeks + 1):
            pairs = sched[(w - 2) % (teams_per_div - 1)] if w >= 2 else [(i, teams_per_div - 1 - i) for i in range(teams_per_div // 2)]
            ms = []
            for mid, (i, j) in enumerate(pairs, 1):
                for k in (i, j):
                    pts = 0.0 if w > as_of else round(max(55.0, rng.gauss(skill[k], 24)), 2)
                    ms.append({"roster_id": k + 1, "matchup_id": mid, "points": pts, "custom_points": None,
                               "starters": [], "players": []})
            dump(ms, f"league__{lid}__matchups__{w}.json")
    return leagues


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample"
    leagues = generate(out)
    cfg = {"_comment": "SAMPLE DATA ONLY - invented teams/owners, not real SBFFC results.",
           "is_sample": True, "title": "SBFFC Championship", "season": "2026",
           "leagues": leagues, "cache_dir": "cache", "offline": True}
    with open(os.path.join(out, "config_sample.json"), "w") as f: json.dump(cfg, f, indent=1)
    print(f"wrote {len(leagues)} sample divisions to {os.path.join(out, 'cache')}")
