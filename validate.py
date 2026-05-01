import json, os, sys

DIR    = os.path.dirname(os.path.abspath(__file__))
LATEST = os.path.join(DIR, "data", "latest.json")
REQUIRED = {"roundId", "playerId", "player", "date", "course", "score", "holeCount", "fairwaysHit", "greensInReg"}
MIN_ROUNDS = 5
EXCLUDED_TEE_TYPES = {"par3"}

def run():
    if not os.path.exists(LATEST):
        print("FAIL: data/latest.json not found"); sys.exit(1)

    size_kb = os.path.getsize(LATEST) / 1024
    with open(LATEST) as f:
        rounds = json.load(f)

    errors = []

    if not isinstance(rounds, list):
        errors.append("Root is not a list")
    if not rounds:
        errors.append("Empty list")

    ids = []
    for i, r in enumerate(rounds):
        if not isinstance(r, dict):
            errors.append(f"[{i}] not a dict"); continue

        for k, v in r.items():
            if isinstance(v, (dict, list)):
                errors.append(f"[{i}] nested value at key '{k}'")

        missing = REQUIRED - set(r.keys())
        if missing:
            errors.append(f"[{i}] missing fields: {missing}")

        hc = r.get("holeCount")
        if hc != 18:
            errors.append(f"[{i}] invalid holeCount={hc}")
        tee = str(r.get("tee") or "").strip().lower()
        course = str(r.get("course") or "").lower()
        if tee in EXCLUDED_TEE_TYPES or "par 3" in course:
            errors.append(f"[{i}] excluded par-3 round present: {r.get('player')} {r.get('date')} {r.get('course')} {r.get('tee')}")

        ids.append((r.get("playerId"), r.get("roundId")))

    dup_ids = {x for x in ids if all(x) and ids.count(x) > 1}
    if dup_ids:
        errors.append(f"Duplicate player/round pairs: {dup_ids}")

    counts = {}
    for r in rounds:
        counts[r.get("player")] = counts.get(r.get("player"), 0) + 1
    under_min = {p: c for p, c in counts.items() if p and c < MIN_ROUNDS}
    if under_min:
        errors.append(f"Players below {MIN_ROUNDS} rounds: {under_min}")

    print(f"Rounds: {len(rounds)}")
    print(f"File size: {size_kb:.1f} KB {'[WARN: >200KB]' if size_kb > 200 else '[OK]'}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    else:
        print("PASS: all checks OK")

if __name__ == "__main__":
    run()
