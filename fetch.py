import urllib.request, urllib.parse, http.cookiejar, re, json, os

BASE = "https://portal.gsprogolf.com"
DIR  = os.path.dirname(os.path.abspath(__file__))
RAW_OUT     = os.path.join(DIR, "data", "raw.json")
COOKIE_FILE = os.path.join(DIR, ".cookies")

DAN_ID = "7d00b84c-9ede-4e63-a915-5e678b13e564"

def _env(key):
    v = os.environ.get(key)
    if not v:
        cfg = os.path.join(DIR, ".env")
        if os.path.exists(cfg):
            for line in open(cfg):
                line = line.strip()
                if line.startswith(key + "="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not v:
        raise RuntimeError(f"Missing env var {key}. Set it or add to .env")
    return v

def _build_opener(jar):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    return opener

def login():
    jar = http.cookiejar.LWPCookieJar(COOKIE_FILE)
    if os.path.exists(COOKIE_FILE):
        try:
            jar.load(ignore_discard=True)
        except Exception:
            pass
    opener = _build_opener(jar)
    r = opener.open(f"{BASE}/Identity/Account/Login")
    html = r.read().decode("utf-8")
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html).group(1)
    data = urllib.parse.urlencode({
        "Input.Email": _env("GSPRO_EMAIL"),
        "Input.Password": _env("GSPRO_PASSWORD"),
        "Input.RememberMe": "false",
        "__RequestVerificationToken": token,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/Identity/Account/Login", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    opener.open(req)
    jar.save(ignore_discard=True)
    return opener

def get_players(opener):
    r = opener.open(f"{BASE}/analytics/rounds")
    html = r.read().decode("utf-8")
    options = re.findall(r'<option value="([^"]+)">([^<]+)</option>', html)
    seen = {DAN_ID}
    players = [{"id": DAN_ID, "name": "Dan"}]
    for pid, name in options:
        if pid not in seen:
            seen.add(pid)
            players.append({"id": pid, "name": name.strip()})
    return players

def fetch_player(opener, player_id):
    params = urllib.parse.urlencode({
        "selectedPlayer": player_id, "analyticsType": "Rounds", "refreshCache": "false"
    })
    url = f"{BASE}/analytics/rounds/LoadData?{params}"
    req = urllib.request.Request(url, headers={
        "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"
    })
    r = opener.open(req)
    return json.loads(r.read().decode("utf-8"))

def run():
    os.makedirs(os.path.dirname(RAW_OUT), exist_ok=True)
    opener = login()
    players = get_players(opener)
    raw = []
    for p in players:
        d = fetch_player(opener, p["id"])
        raw.append({
            "player_id": p["id"],
            "player_name": p["name"],
            "rounds": d.get("Rounds_Rounds", []),
            "scores": d.get("RoundScores", []),
        })
    with open(RAW_OUT, "w") as f:
        json.dump(raw, f, separators=(",", ":"))

if __name__ == "__main__":
    run()
