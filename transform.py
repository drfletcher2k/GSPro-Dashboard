import json, os

DIR         = os.path.dirname(os.path.abspath(__file__))
FILTERED    = os.path.join(DIR, "data", "filtered.json")
TRANSFORMED = os.path.join(DIR, "data", "transformed.json")

def flatten_round(p_name, r, sc):
    return {
        "roundId":              r.get("roundKey"),
        "playerId":             r.get("playerKey"),
        "player":               p_name,
        "date":                 (r.get("roundBegin") or "")[:10],
        "course":               r.get("courseName"),
        "tee":                  r.get("teeType"),
        "par":                  _int(r.get("par")),
        "score":                _int(r.get("total")),
        "net":                  _int(r.get("net")),
        "courseHandicap":       _int(r.get("courseHandicap")),
        "holeCount":            r.get("holeCount"),
        "roundType":            r.get("roundType"),
        "ratingSlope":          r.get("ratingSlope"),
        "fairwaysHit":          sc.get("fairwaysValue"),
        "fairwaysTarget":       sc.get("fairwaysTarget"),
        "greensInReg":          sc.get("greensValue"),
        "greensTarget":         sc.get("greensTarget"),
        "putts":                sc.get("puttsValue"),
        "sandSaves":            sc.get("sandSavesValue"),
        "drivingDistLongest":   sc.get("drivingDistanceLongest"),
        "eagles":               sc.get("eagle"),
        "birdies":              sc.get("birdie"),
        "pars":                 sc.get("par"),
        "bogeys":               sc.get("bogey"),
        "doubleBogeys":         sc.get("doubleBogey"),
        "others":               sc.get("other"),
    }

def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def run():
    with open(FILTERED) as f:
        players = json.load(f)

    out = []
    for p in players:
        scores_by_round = {s["roundKey"]: s for s in p.get("scores", [])}
        for r in p["rounds"]:
            sc = scores_by_round.get(r.get("roundKey"), {})
            out.append(flatten_round(p["player_name"], r, sc))

    with open(TRANSFORMED, "w") as f:
        json.dump(out, f, separators=(",", ":"))

if __name__ == "__main__":
    run()
