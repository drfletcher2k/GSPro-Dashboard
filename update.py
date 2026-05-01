import json, os, importlib
from collections import defaultdict
import fetch, filter as flt, transform

DIR    = os.path.dirname(os.path.abspath(__file__))
LATEST = os.path.join(DIR, "data", "latest.json")
TRANSFORMED = os.path.join(DIR, "data", "transformed.json")

def run():
    fetch.run()
    flt.run()
    transform.run()

    with open(TRANSFORMED) as f:
        rounds = json.load(f)

    seen, deduped = set(), []
    for r in rounds:
        key = (r.get("playerId"), r.get("roundId"))
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    # Exclude solo rounds: a round (identified by roundId, which is shared
    # across players who played together) must have at least 2 distinct
    # players to count toward dashboard data.
    players_per_round = defaultdict(set)
    for r in deduped:
        rid = r.get("roundId")
        if rid:
            players_per_round[rid].add(r.get("playerId"))

    multiplayer_ids = {rid for rid, players in players_per_round.items() if len(players) >= 2}
    before = len(deduped)
    multi = [r for r in deduped if r.get("roundId") in multiplayer_ids]
    excluded_solo = before - len(multi)
    print(f"Excluded {excluded_solo} solo round entries; "
          f"{len(multi)} multiplayer round entries across "
          f"{len(multiplayer_ids)} multiplayer sessions remain")

    with open(LATEST, "w") as f:
        json.dump(multi, f, separators=(",", ":"))

    size_kb = os.path.getsize(LATEST) / 1024
    print(f"{len(multi)} rounds → data/latest.json ({size_kb:.1f} KB)")

    import gen_dashboard
    importlib.reload(gen_dashboard)
    print("index.html regenerated")

if __name__ == "__main__":
    run()
