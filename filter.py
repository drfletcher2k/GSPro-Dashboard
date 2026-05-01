import json, os

DIR      = os.path.dirname(os.path.abspath(__file__))
RAW      = os.path.join(DIR, "data", "raw.json")
FILTERED = os.path.join(DIR, "data", "filtered.json")

VALID_HOLES = {18}
MIN_ROUNDS = 5
EXCLUDED_TEE_TYPES = {"par3"}

def is_complete(r):
    tee = str(r.get("teeType") or "").strip().lower()
    course = str(r.get("courseName") or "").lower()
    return (
        r.get("holeCount") in VALID_HOLES
        and tee not in EXCLUDED_TEE_TYPES
        and "par 3" not in course
        and not r.get("hiddenFromStatsTF", False)
        and r.get("isRoundTypeRound", True)
    )

def run():
    with open(RAW) as f:
        players = json.load(f)

    out = []
    for p in players:
        qualifying = [r for r in p["rounds"] if is_complete(r)]
        if len(qualifying) >= MIN_ROUNDS:
            out.append({
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "rounds": qualifying,
                "scores": p["scores"],
            })

    with open(FILTERED, "w") as f:
        json.dump(out, f, separators=(",", ":"))

if __name__ == "__main__":
    run()
