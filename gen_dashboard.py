#!/usr/bin/env python3
"""Generate GSPro Analytics dashboard from data/latest.json."""
import json, os, statistics
from collections import defaultdict, Counter
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data', 'latest.json')
OUT  = os.path.join(BASE, 'index.html')

with open(DATA) as f:
    rounds = json.load(f)

# Solo rounds (a roundId played by a single player) are filtered out upstream
# in update.py. Re-assert here so a stale latest.json or a direct invocation of
# gen_dashboard.py never lets solo rounds back into the dashboard.
_players_per_round = defaultdict(set)
for _r in rounds:
    _rid = _r.get('roundId')
    if _rid:
        _players_per_round[_rid].add(_r.get('playerId'))
_multi_round_ids = {rid for rid, ps in _players_per_round.items() if len(ps) >= 2}
_before = len(rounds)
rounds = [r for r in rounds if r.get('roundId') in _multi_round_ids]
_dropped = _before - len(rounds)
if _dropped:
    print(f'  (gen_dashboard) dropped {_dropped} solo round entries; '
          f'{len(rounds)} multiplayer entries across '
          f'{len(_multi_round_ids)} sessions retained')

PLAYERS = sorted(set(r['player'] for r in rounds))
COLORS = {
    'Dan':       '#60a5fa',
    'Tobby':     '#f87171',
    'Brad':      '#fbbf24',
    'Jack':      '#a78bfa',
    'Baumbach':  '#22d3ee',
    'Dapp':      '#f472b6',
    'Mad':       '#34d399',
    'Maddox':    '#34d399',
    'Dan/Thom':  '#fb923c',
    'Albert':    '#fb923c',
}

_avg = lambda lst: sum(lst)/len(lst) if lst else None
_std = lambda lst: statistics.stdev(lst) if len(lst) >= 2 else None

def _rating_slope(v):
    try:
        rating, slope = str(v).split('/', 1)
        return float(rating), float(slope)
    except (TypeError, ValueError):
        return None, None

def _diff(r):
    rating, slope = _rating_slope(r.get('ratingSlope'))
    score = r.get('score')
    if rating is None or slope in (None, 0) or score is None:
        return None
    return (int(score) - rating) * 113 / slope

def _index_from_diffs(diffs):
    if len(diffs) < 5:
        return None
    recent = diffs[-20:]
    n = len(recent)
    take = 8 if n >= 20 else max(1, round(n * 0.4))
    return round(_avg(sorted(recent)[:take]) * 0.96, 1)

# ── session sizing (for group/solo detection) ────────────────────────────────
session_sizes = Counter()
for r in rounds:
    if r['date'] and r['course']:
        session_sizes[(r['date'], r['course'], r['holeCount'])] += 1

# ── per-player stats ─────────────────────────────────────────────────────────
def compute_per_player():
    per = {}
    for p in PLAYERS:
        pr   = [r for r in rounds if r['player'] == p]
        r18  = sorted([r for r in pr if r['holeCount']==18 and r['score']], key=lambda x: x['date'])
        s18  = [int(r['score']) for r in r18]

        std18 = _std(s18)
        avg18 = _avg(s18)

        if std18 is None:   grade, glabel = '-', 'N/A'
        elif std18 <= 5:    grade, glabel = 'A', 'Machine'
        elif std18 <= 7:    grade, glabel = 'B', 'Steady'
        elif std18 <= 9:    grade, glabel = 'C', 'Variable'
        elif std18 <= 11:   grade, glabel = 'D', 'Wild'
        else:               grade, glabel = 'F', 'Chaos'

        form_diff = form_label = None
        if s18 and len(s18) >= 5:
            fd = round(avg18 - _avg(s18[-5:]), 1)
            form_diff = fd
            if   fd >  3: form_label = 'Scorching'
            elif fd >  1: form_label = 'Warming Up'
            elif fd > -1: form_label = 'Steady'
            elif fd > -3: form_label = 'Cooling'
            else:         form_label = 'Frozen'

        peak = None
        if len(s18) >= 5:
            best_avg, best_end = None, None
            for i in range(4, len(s18)):
                w = _avg(s18[i-4:i+1])
                if best_avg is None or w < best_avg:
                    best_avg, best_end = w, r18[i]['date']
            peak = {'avg': round(best_avg, 1), 'end': best_end}

        # rolling 5-round trend (18H)
        trend18 = []
        for i, r in enumerate(r18):
            window = s18[max(0, i-4):i+1]
            trend18.append({'d': r['date'], 's': int(r['score']), 'a': round(_avg(window), 1)})

        # monthly avg (18H) – keyed by YYYY-MM
        by_month = defaultdict(list)
        for r in r18:
            by_month[r['date'][:7]].append(int(r['score']))
        monthly_avg = {m: round(_avg(v), 1) for m, v in by_month.items()}

        # group vs solo (18H only)
        solo18  = [int(r['score']) for r in r18 if session_sizes.get((r['date'],r['course'],r['holeCount']),0)==1]
        group18 = [int(r['score']) for r in r18 if session_sizes.get((r['date'],r['course'],r['holeCount']),0)>1]

        # scoring velocity: slope of last-20 18H rounds (strokes/round; negative = improving)
        velocity = None
        if len(s18) >= 10:
            recent = s18[-20:]
            n = len(recent)
            xm = (n-1)/2
            ym = _avg(recent)
            num = sum((i-xm)*(recent[i]-ym) for i in range(n))
            den = sum((i-xm)**2 for i in range(n))
            velocity = round(num/den, 3) if den else 0

        baseline_vs = []
        for i, r in enumerate(r18):
            prev = s18[max(0, i-10):i]
            base = _avg(prev)
            baseline_vs.append({
                'd': r['date'],
                'score': int(r['score']),
                'baseline': round(base, 1) if base is not None else None,
                'vs': round(int(r['score']) - base, 1) if base is not None else None,
            })

        recent5 = s18[-5:]
        recent10 = s18[-10:]
        std5 = _std(recent5)
        std10 = _std(recent10)
        blowups = [(r.get('doubleBogeys') or 0) + (r.get('others') or 0) for r in r18]
        recent_blowups = blowups[-5:]
        birdies = [(r.get('birdies') or 0) + (r.get('eagles') or 0) for r in r18]
        recent_birdies = birdies[-5:]
        prior_birdies = birdies[:-5]
        diffs = [_diff(r) for r in r18]
        diffs = [d for d in diffs if d is not None]

        # shot stats
        fir18  = [r['fairwaysHit'] for r in r18 if r['fairwaysHit'] is not None]
        gir18  = [r['greensInReg'] for r in r18 if r['greensInReg'] is not None]

        # archetype (relative to group medians: FIR 4.4, GIR 3.9)
        af, ag = _avg(fir18) or 4.4, _avg(gir18) or 3.9
        hi_fir  = af > 4.7
        hi_gir  = ag > 4.4
        if hi_fir and hi_gir:             arch = ('PRECISION', 'Precision Machine')
        elif hi_fir:                      arch = ('FAIRWAY',   'Fairway Hunter')
        elif hi_gir:                      arch = ('IRON',      'Iron Player')
        else:                             arch = ('GRINDER',   'Grinder')

        # score distribution (18H)
        buckets = ['<80','80-84','85-89','90-94','95-99','100+']
        dist = {b: 0 for b in buckets}
        for s in s18:
            if s<80:    dist['<80']   += 1
            elif s<85:  dist['80-84'] += 1
            elif s<90:  dist['85-89'] += 1
            elif s<95:  dist['90-94'] += 1
            elif s<100: dist['95-99'] += 1
            else:       dist['100+']  += 1

        per[p] = {
            'count': len(pr), 'count18': len(r18),
            'avg18':  round(avg18, 1)  if avg18  else None,
            'best18': min(s18)          if s18    else None,
            'worst18':max(s18)          if s18    else None,
            'std18':  round(std18, 2)   if std18  else None,
            'grade': grade, 'glabel': glabel,
            'form_diff': form_diff, 'form_label': form_label,
            'peak': peak,
            'trend18': trend18,
            'monthly_avg': monthly_avg,
            'solo_avg18':   round(_avg(solo18),  1) if solo18  else None,
            'group_avg18':  round(_avg(group18), 1) if group18 else None,
            'solo_count18': len(solo18), 'group_count18': len(group18),
            'velocity': velocity,
            'baseline_vs': baseline_vs,
            'last_vs_baseline': baseline_vs[-1]['vs'] if baseline_vs else None,
            'std5': round(std5, 2) if std5 else None,
            'std10': round(std10, 2) if std10 else None,
            'blowup_avg18': round(_avg(blowups), 2) if blowups else None,
            'blowup_recent18': round(_avg(recent_blowups), 2) if recent_blowups else None,
            'birdies_recent18': round(_avg(recent_birdies), 2) if recent_birdies else None,
            'birdies_prior18': round(_avg(prior_birdies), 2) if prior_birdies else None,
            'sim_index': _index_from_diffs(diffs),
            'avg_fir18':   round(_avg(fir18),  1) if fir18  else None,
            'avg_gir18':   round(_avg(gir18),  1) if gir18  else None,
            'archetype': list(arch),
            'unique_courses': len(set(r['course'] for r in pr if r['course'])),
            'score_dist': dist,
            'color': COLORS.get(p, '#9ca3af'),
            'avg_eagles18':   round(_avg([r.get('eagles') or 0 for r in r18]), 2) if r18 else None,
            'avg_birdies18':  round(_avg([r.get('birdies') or 0 for r in r18]), 2) if r18 else None,
            'avg_pars18':     round(_avg([r.get('pars') or 0 for r in r18]), 2) if r18 else None,
            'avg_bogeys18':   round(_avg([r.get('bogeys') or 0 for r in r18]), 2) if r18 else None,
            'avg_dbl18':      round(_avg([r.get('doubleBogeys') or 0 for r in r18]), 2) if r18 else None,
            'avg_drive18':    round(_avg([r.get('drivingDistLongest') or 0 for r in r18 if r.get('drivingDistLongest')]), 1) if r18 else None,
            'avg_net18':      round(_avg([r.get('net') for r in r18 if r.get('net') is not None]), 1) if r18 else None,
        }
    return per

# ── H2H matrix ───────────────────────────────────────────────────────────────
def compute_h2h():
    sessions = defaultdict(list)
    for r in rounds:
        if r['date'] and r['course'] and r['score']:
            sessions[(r['date'], r['course'], r['holeCount'])].append(r)

    matrix = {p: {q: {'w':0,'l':0,'t':0} for q in PLAYERS if q!=p} for p in PLAYERS}
    for rs in sessions.values():
        if len(rs) < 2: continue
        for i in range(len(rs)):
            for j in range(i+1, len(rs)):
                a, b = rs[i], rs[j]
                if a['player'] == b['player']: continue
                ap, bp = a['player'], b['player']
                if ap not in matrix or bp not in matrix.get(ap,{}): continue
                sa, sb = int(a['score']), int(b['score'])
                if   sa < sb: matrix[ap][bp]['w']+=1; matrix[bp][ap]['l']+=1
                elif sb < sa: matrix[bp][ap]['w']+=1; matrix[ap][bp]['l']+=1
                else:         matrix[ap][bp]['t']+=1; matrix[bp][ap]['t']+=1
    return matrix

# ── top courses ──────────────────────────────────────────────────────────────
def compute_top_courses():
    c = Counter(r['course'] for r in rounds if r['course'])
    return [{'name': n, 'count': v} for n, v in c.most_common(12)]

# ── monthly volume ───────────────────────────────────────────────────────────
def compute_monthly():
    all_months = sorted(set(r['date'][:7] for r in rounds if r['date']))
    by_player  = {}
    for p in PLAYERS:
        mc = Counter(r['date'][:7] for r in rounds if r['player']==p and r['date'])
        by_player[p] = [mc.get(m, 0) for m in all_months]
    return {'months': all_months, 'by_player': by_player}

# ── run ──────────────────────────────────────────────────────────────────────
per_player  = compute_per_player()
h2h_matrix  = compute_h2h()
top_courses = compute_top_courses()
monthly     = compute_monthly()

# nemesis / prey / win-rate
for p in PLAYERS:
    best_nem = best_prey = None
    bnem_rate = bprey_rate = -1
    total_w = total_g = 0
    for q in PLAYERS:
        if q==p or q not in h2h_matrix.get(p,{}): continue
        rec = h2h_matrix[p][q]
        tot = rec['w']+rec['l']+rec['t']
        total_w += rec['w']; total_g += tot
        if tot < 2: continue
        lr = rec['l']/tot; wr = rec['w']/tot
        if lr > bnem_rate:  bnem_rate  = lr;  best_nem  = {'p':q,**rec,'tot':tot}
        if wr > bprey_rate: bprey_rate = wr;  best_prey = {'p':q,**rec,'tot':tot}
    per_player[p]['nemesis']     = best_nem
    per_player[p]['prey']        = best_prey
    per_player[p]['win_rate']    = round(total_w/total_g*100,1) if total_g else 0
    per_player[p]['total_games'] = total_g

# ── embed ────────────────────────────────────────────────────────────────────
jd = lambda x: json.dumps(x, separators=(',',':'))
ROUNDS_J   = jd(rounds)
PLAYERS_J  = jd(PLAYERS)
COLORS_J   = jd(COLORS)
PERP_J     = jd(per_player)
H2H_J      = jd(h2h_matrix)
COURSES_J  = jd(top_courses)
MONTHLY_J  = jd(monthly)
GENERATED  = datetime.now().strftime('%Y-%m-%d %H:%M')

# ── HTML template ─────────────────────────────────────────────────────────────
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GSPro Analytics</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ──────────────────────────────────────────────────────────────
   GSPro · Broadcast / Control Room theme
   ───────────────────────────────────────────────────────────── */
:root {
  --bg-0:        #05080f;          /* canvas */
  --bg-1:        #0a1020;          /* shell */
  --bg-2:        #0f172a;          /* panel */
  --bg-3:        #131c33;          /* panel inner */
  --bg-hi:       #1a2547;          /* hover/selected */
  --line:        rgba(99,140,210,0.12);
  --line-hi:     rgba(99,140,210,0.30);
  --text:        #e6ecf7;
  --text-dim:    rgba(230,236,247,0.72);
  --muted:       rgba(180,196,224,0.55);
  --muted-2:     rgba(180,196,224,0.38);
  --accent:      #4f8bff;          /* primary blue */
  --accent-2:    #38bdf8;          /* cyan */
  --accent-glow: rgba(79,139,255,0.55);
  --green:       #22c55e;          /* semantic only */
  --gold:        #fbbf24;          /* semantic only */
  --red:         #ef4444;
  --radius-lg:   18px;
  --radius:      14px;
  --radius-sm:   10px;
  --shadow-glow: 0 10px 40px -10px rgba(79,139,255,0.25), 0 0 0 1px var(--line);
  --num: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
}
*, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }
html { scroll-behavior: smooth; }
body {
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg-0);
  color: var(--text);
  min-height: 100vh;
  font-feature-settings: "ss01","cv11";
  background-image:
    radial-gradient(ellipse 60% 40% at 15% 0%,  rgba(79,139,255,0.18) 0%, transparent 60%),
    radial-gradient(ellipse 70% 50% at 90% 10%, rgba(56,189,248,0.10) 0%, transparent 65%),
    radial-gradient(ellipse 60% 60% at 50% 110%, rgba(79,139,255,0.10) 0%, transparent 70%);
}
.num, .stat-value, .kpi-value, .lb-num, .matrix-cell, .dp-record, .dm-score, .ic-main {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum","ss01";
}
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:6px; }

/* ── Shell layout ────────────────────────────────────────── */
.app {
  display:grid;
  grid-template-columns: 248px 1fr;
  gap:18px;
  padding:18px;
  max-width: 1700px;
  margin:0 auto;
  min-height:100vh;
}
@media(max-width:1100px){
  .app { grid-template-columns: 1fr; padding:12px; }
}

/* ── Sidebar / roster ────────────────────────────────────── */
.sidebar {
  background: linear-gradient(180deg, rgba(15,23,42,0.92), rgba(10,16,32,0.92));
  border:1px solid var(--line);
  border-radius: var(--radius-lg);
  padding:18px 14px;
  display:flex; flex-direction:column;
  position:sticky; top:18px;
  align-self: start;
  height: calc(100vh - 36px);
  overflow:hidden;
}
.brand {
  display:flex; align-items:center; gap:12px;
  padding: 4px 6px 14px;
  border-bottom: 1px solid var(--line);
  margin-bottom:14px;
}
.brand-mark {
  width:34px; height:34px; border-radius:10px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  display:grid; place-items:center;
  box-shadow: 0 0 24px -4px var(--accent-glow);
  flex-shrink:0;
}
.brand-mark svg { width:18px; height:18px; color:#fff; }
.brand-text h1 {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-size:0.95rem; font-weight:700; letter-spacing:0.02em;
}
.brand-text p { font-size:0.62rem; color:var(--muted); letter-spacing:0.14em; text-transform:uppercase; }

.roster-label {
  font-size:0.6rem; font-weight:700; color:var(--muted-2);
  letter-spacing:0.18em; text-transform:uppercase;
  padding: 4px 8px 8px;
}
.roster {
  display:flex; flex-direction:column; gap:3px;
  overflow-y:auto;
  flex:1;
  padding-right:2px;
  scrollbar-width: thin;
  scrollbar-color: rgba(99,140,210,0.25) transparent;
}
.roster::-webkit-scrollbar { width:6px; }
.roster::-webkit-scrollbar-thumb { background: rgba(99,140,210,0.25); border-radius:3px; }
.roster-item {
  display:flex; align-items:center; gap:10px;
  padding:9px 10px;
  border-radius: var(--radius-sm);
  border:1px solid transparent;
  background:transparent;
  color:var(--text-dim);
  cursor:pointer;
  font-family:inherit; font-size:0.83rem; font-weight:500;
  width:100%;
  text-align:left;
  transition: background .15s, border-color .15s, color .15s;
}
.roster-item:hover {
  background: rgba(99,140,210,0.07);
  color: var(--text);
}
.roster-item.active {
  background: linear-gradient(90deg, rgba(79,139,255,0.18), rgba(79,139,255,0.04));
  border-color: rgba(79,139,255,0.35);
  color: var(--text);
  box-shadow: inset 2px 0 0 var(--accent);
}
.avatar {
  width:28px; height:28px; border-radius:8px;
  display:grid; place-items:center;
  font-family:'Space Grotesk', sans-serif;
  font-weight:700; font-size:0.78rem;
  color:#0b1424;
  flex-shrink:0;
  letter-spacing:0;
}
.avatar.all {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color:#fff;
}
.avatar svg { width:14px; height:14px; }
.roster-meta { font-size:0.66rem; color:var(--muted); margin-left:auto; font-variant-numeric:tabular-nums; }

.sidebar-foot {
  border-top:1px solid var(--line);
  margin-top:10px;
  padding:12px 8px 4px;
  font-size:0.66rem; color:var(--muted);
  display:flex; justify-content:space-between; gap:8px;
}

/* ── Main area ────────────────────────────────────────────── */
main { display:flex; flex-direction:column; gap:18px; min-width:0; }

.topbar {
  display:flex; align-items:center; gap:14px;
  padding: 4px 4px 0;
  flex-wrap:wrap;
}
.crumbs { font-size:0.72rem; color:var(--muted); letter-spacing:0.04em; }
.crumbs strong { color:var(--text); font-weight:600; margin-left:4px; }
.topbar-spacer { flex:1; }
.topbar-tag {
  display:inline-flex; align-items:center; gap:6px;
  font-size:0.7rem; color:var(--muted);
  padding:6px 10px; border-radius:999px;
  border:1px solid var(--line);
  background:rgba(15,23,42,0.6);
}
.live-dot {
  width:6px; height:6px; border-radius:50%;
  background: var(--green);
  box-shadow: 0 0 0 0 rgba(34,197,94,0.6);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%   { box-shadow:0 0 0 0 rgba(34,197,94,0.5); }
  70%  { box-shadow:0 0 0 7px rgba(34,197,94,0); }
  100% { box-shadow:0 0 0 0 rgba(34,197,94,0); }
}

/* ── Section heading ─────────────────────────────────────── */
.section-title {
  font-family: 'Space Grotesk','Inter', sans-serif;
  font-size:0.78rem; font-weight:600;
  letter-spacing:0.18em; text-transform:uppercase;
  color: var(--muted);
  display:flex; align-items:center; gap:10px;
  margin: 6px 2px 4px;
}
.section-title::before {
  content:''; width:14px; height:1px;
  background: linear-gradient(90deg, var(--accent), transparent);
}
.section-title .st-accent { color:var(--text); }

/* ── Panel base ──────────────────────────────────────────── */
.panel {
  background: linear-gradient(180deg, rgba(15,23,42,0.92), rgba(10,16,32,0.92));
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  position:relative;
  overflow:hidden;
  transition: border-color .15s, transform .15s;
}
.panel.glow {
  box-shadow: var(--shadow-glow);
}
.panel-pad   { padding:20px; }
.panel-pad-l { padding:24px 26px; }
.panel-head  {
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  font-size:0.7rem; font-weight:600; color:var(--muted);
  letter-spacing:0.14em; text-transform:uppercase;
  padding: 16px 20px 12px;
}
.panel-head h3 { font-size:0.7rem; font-weight:600; }
.panel-sub { font-size:0.68rem; color:var(--muted-2); letter-spacing:0; text-transform:none; }

/* ── KPI strip ───────────────────────────────────────────── */
.kpi-strip {
  display:grid;
  grid-template-columns: repeat(4, 1fr);
  gap:14px;
}
@media(max-width:1100px){ .kpi-strip { grid-template-columns: repeat(2,1fr); } }
@media(max-width:560px){  .kpi-strip { grid-template-columns: 1fr; } }
.kpi {
  display:flex; align-items:center; gap:14px;
  padding:14px 16px;
  background: var(--bg-2);
  border:1px solid var(--line);
  border-radius: var(--radius);
  position:relative;
  overflow:hidden;
}
.kpi::after {
  content:''; position:absolute; top:0; right:0; width:90px; height:60px;
  background: radial-gradient(circle at 100% 0%, rgba(79,139,255,0.18), transparent 70%);
  pointer-events:none;
}
.kpi-icon {
  width:38px; height:38px; border-radius:10px;
  display:grid; place-items:center;
  background: rgba(79,139,255,0.12);
  color: var(--accent);
  flex-shrink:0;
}
.kpi-icon svg { width:18px; height:18px; }
.kpi-body { display:flex; flex-direction:column; gap:1px; min-width:0; }
.kpi-label { font-size:0.64rem; font-weight:600; color:var(--muted); letter-spacing:0.13em; text-transform:uppercase; }
.kpi-value { font-family:'Space Grotesk', sans-serif; font-size:1.45rem; font-weight:700; line-height:1.1; letter-spacing:-0.01em; }
.kpi-sub   { font-size:0.7rem; color:var(--muted-2); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* ── Hero (stage) row ────────────────────────────────────── */
.stage {
  display:grid;
  grid-template-columns: 1.7fr 1fr 1fr;
  gap:14px;
}
@media(max-width:1280px){ .stage { grid-template-columns: 1fr 1fr; } .stage .stage-feature { grid-column: 1/-1; } }
@media(max-width:760px){  .stage { grid-template-columns: 1fr; } }
.stage-feature {
  padding:24px 26px;
  position:relative;
  background:
    radial-gradient(ellipse 60% 100% at 100% 50%, rgba(79,139,255,0.18) 0%, transparent 60%),
    linear-gradient(180deg, rgba(15,23,42,0.95), rgba(10,16,32,0.95));
  display:flex; flex-direction:column; gap:14px;
  min-height:240px;
}
.stage-feature::before {
  content:''; position:absolute; right:-40px; top:-40px;
  width:240px; height:240px; border-radius:50%;
  background: radial-gradient(circle, rgba(79,139,255,0.45), transparent 70%);
  filter: blur(28px); pointer-events:none;
}
.feature-eyebrow {
  font-size:0.65rem; color:var(--accent-2); letter-spacing:0.18em; text-transform:uppercase; font-weight:600;
}
.feature-name {
  font-family:'Space Grotesk','Inter',sans-serif;
  font-size:2.4rem; font-weight:700; letter-spacing:-0.02em; line-height:1.05;
}
.feature-tag { font-size:0.78rem; color:var(--text-dim); max-width:300px; }
.feature-stats { display:flex; gap:24px; margin-top:auto; flex-wrap:wrap; }
.feature-stat .fs-label { font-size:0.62rem; color:var(--muted); letter-spacing:0.14em; text-transform:uppercase; }
.feature-stat .fs-value { font-family:'Space Grotesk',sans-serif; font-size:1.2rem; font-weight:700; }
.feature-cta {
  align-self:flex-start;
  padding:9px 16px; border-radius:10px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color:#fff; font-size:0.78rem; font-weight:600; letter-spacing:0.04em;
  border:none; cursor:pointer;
  box-shadow: 0 0 24px -6px var(--accent-glow);
  transition: transform .15s, box-shadow .15s;
}
.feature-cta:hover { transform:translateY(-1px); box-shadow:0 0 28px -4px var(--accent-glow); }

/* ── Gauge panel ─────────────────────────────────────────── */
.gauge-panel { padding:20px; display:flex; flex-direction:column; gap:8px; align-items:flex-start; }
.gauge-wrap { width:100%; display:flex; flex-direction:column; align-items:center; gap:6px; margin-top:auto; margin-bottom:8px; }
.gauge { position:relative; width:160px; height:90px; }
.gauge-readout { position:absolute; bottom:-4px; left:0; right:0; text-align:center; }
.gauge-readout .gr-num { font-family:'Space Grotesk',sans-serif; font-size:1.7rem; font-weight:700; }
.gauge-readout .gr-cap { font-size:0.6rem; color:var(--muted); letter-spacing:0.14em; text-transform:uppercase; }

/* ── Stat-pair panel ─────────────────────────────────────── */
.statpair { display:grid; grid-template-columns: 1fr 1fr; gap:0; padding:0; }
.statpair > div { padding:16px 18px; }
.statpair > div + div { border-left:1px solid var(--line); }
.sp-label { font-size:0.6rem; color:var(--muted); letter-spacing:0.14em; text-transform:uppercase; font-weight:600; }
.sp-value { font-family:'Space Grotesk',sans-serif; font-size:1.5rem; font-weight:700; line-height:1.1; margin-top:6px; }
.sp-sub { font-size:0.68rem; color:var(--muted-2); margin-top:2px; }

/* ── Cockpit grid (chart row + side card) ────────────────── */
.cockpit {
  display:grid;
  grid-template-columns: 2fr 1fr;
  gap:14px;
}
@media(max-width:1100px){ .cockpit { grid-template-columns: 1fr; } }

/* ── Leaderboard table ───────────────────────────────────── */
.lb-wrap { overflow-x:auto; }
.lb-table { width:100%; border-collapse:collapse; font-size:0.84rem; }
.lb-table th {
  padding:11px 14px; text-align:left;
  font-size:0.62rem; font-weight:600;
  text-transform:uppercase; letter-spacing:0.13em; color:var(--muted);
  border-bottom:1px solid var(--line);
  white-space:nowrap;
  background:transparent;
}
.lb-table th button.th-btn {
  background:none; border:none; padding:0; margin:0;
  color:inherit; font:inherit; letter-spacing:inherit; text-transform:inherit;
  cursor:pointer; display:inline-flex; align-items:center; gap:4px;
}
.lb-table th button.th-btn:hover { color: var(--text); }
.lb-table th .sort-ind { color: var(--accent); font-size:0.7rem; }
.lb-table td { padding:13px 14px; border-bottom:1px solid var(--line); vertical-align:middle; }
.lb-table tr:last-child td { border-bottom:none; }
.lb-table tbody tr { transition:background .12s; }
.lb-table tbody tr:hover { background: rgba(79,139,255,0.05); }
.lb-num { font-family:'Space Grotesk',sans-serif; font-size:1rem; font-weight:700; color:var(--muted); width:28px; }
.lb-num.r1 { color: var(--gold); }
.lb-num.r2 { color: #cbd5e1; }
.lb-num.r3 { color: #b45309; }
.lb-player { display:inline-flex; align-items:center; gap:10px; font-weight:600; }
.lb-player .player-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; box-shadow:0 0 8px currentColor; }
.lb-strong { font-family:'Space Grotesk',sans-serif; font-weight:700; }
.lb-muted { color: var(--muted); font-size:0.75rem; }
.grade-badge {
  display:inline-flex; align-items:center; justify-content:center;
  width:26px; height:26px; border-radius:7px;
  font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:0.85rem;
  border:1px solid currentColor;
  background: color-mix(in srgb, currentColor 12%, transparent);
}
.score-bar-wrap { display:flex; align-items:center; gap:10px; min-width:120px; }
.score-bar-bg { flex:1; height:4px; border-radius:3px; background:rgba(255,255,255,0.06); overflow:hidden; }
.score-bar-fill { height:100%; border-radius:3px; transition:width .5s; }
.arch-cell { font-size:0.74rem; white-space:nowrap; color:var(--text-dim); }
.arch-cell .arch-key { font-family:'Space Grotesk',sans-serif; color:var(--accent); font-size:0.65rem; letter-spacing:0.12em; margin-right:6px; }

/* ── Form pill ───────────────────────────────────────────── */
.form-pill {
  display:inline-block; padding:3px 10px; border-radius:999px;
  font-size:0.7rem; font-weight:600; white-space:nowrap;
  border:1px solid currentColor;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

/* ── Chart cards ─────────────────────────────────────────── */
.chart-card { padding:18px 20px 20px; }
.chart-card canvas { max-height:340px; }
.trend-chart-wrap { position:relative; width:100%; height:340px; }
.trend-chart-wrap > canvas { width:100% !important; height:100% !important; max-height:none; display:block; }
@media(max-width:760px){ .trend-chart-wrap { height:280px; } }

/* ── H2H ─────────────────────────────────────────────────── */
.h2h-layout { display:grid; grid-template-columns:1fr 380px; gap:14px; }
@media(max-width:1100px){ .h2h-layout{ grid-template-columns:1fr; } }
.matrix-wrap { padding:18px 20px; overflow-x:auto; }
.matrix-table { border-collapse:separate; border-spacing:4px; font-size:0.74rem; }
.matrix-table th {
  padding:6px 10px; font-size:0.6rem; font-weight:600; letter-spacing:0.12em;
  text-transform:uppercase; color:var(--muted); text-align:center; white-space:nowrap;
}
.matrix-table .row-head { text-align:right; padding-right:12px; white-space:nowrap; font-weight:600; font-size:0.78rem; }
.matrix-cell {
  padding:7px 10px; border-radius:8px; text-align:center;
  cursor:pointer; transition:transform .12s, box-shadow .12s;
  font-weight:600; white-space:nowrap;
  border:1px solid transparent;
  min-width:64px;
  background: rgba(99,140,210,0.06);
  color: var(--text-dim);
  font-family: inherit;
  font-size: 0.74rem;
  font-variant-numeric: tabular-nums;
}
button.matrix-cell { display:inline-block; width:100%; }
.matrix-cell:hover { transform:scale(1.06); box-shadow:0 0 0 1px var(--line-hi); position:relative; z-index:5; }
.matrix-cell.self { background:transparent; cursor:default; color:var(--muted-2); }
.matrix-cell.win  { background:rgba(34,197,94,0.18);  color:#86efac; }
.matrix-cell.edge { background:rgba(34,197,94,0.10);  color:#bef0d2; }
.matrix-cell.even { background:rgba(148,163,184,0.12); color:#cbd5e1; }
.matrix-cell.trail{ background:rgba(239,68,68,0.10);  color:#fca5a5; }
.matrix-cell.loss { background:rgba(239,68,68,0.20);  color:#f87171; }
.matrix-cell.active { box-shadow:0 0 0 2px var(--accent); }

/* ── Duel panel ──────────────────────────────────────────── */
.duel-panel { padding:20px 22px; min-height:340px; display:flex; flex-direction:column; gap:14px; }
.duel-empty { display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:100%; gap:10px; color:var(--muted); font-size:0.85rem; padding:40px 0; text-align:center; }
.duel-empty .de-ico { width:36px; height:36px; opacity:0.5; }
.duel-header { display:flex; align-items:flex-start; gap:0; justify-content:center; }
.duel-player { text-align:center; flex:1; }
.duel-player .dp-name { font-family:'Space Grotesk',sans-serif; font-size:1.15rem; font-weight:700; }
.duel-player .dp-record { font-family:'Space Grotesk',sans-serif; font-size:2rem; font-weight:700; line-height:1; margin-top:4px; }
.duel-player .dp-sub { font-size:0.7rem; color:var(--muted); margin-top:4px; }
.duel-vs { font-size:0.7rem; font-weight:700; color:var(--muted-2); padding:14px 14px 0; letter-spacing:0.18em; }
.duel-bar-wrap { background:rgba(255,255,255,0.05); border-radius:999px; height:8px; overflow:hidden; }
.duel-bar-fill { height:100%; border-radius:999px; }
.duel-stat-row { display:flex; justify-content:space-between; font-size:0.74rem; color:var(--text-dim); }
.duel-recent h4 { font-size:0.62rem; font-weight:600; text-transform:uppercase; letter-spacing:0.16em;
  color:var(--muted); margin-bottom:10px; }
.duel-match-row { display:flex; align-items:center; gap:8px; font-size:0.75rem;
  padding:6px 0; border-bottom:1px solid var(--line); }
.duel-match-row:last-child { border:none; }
.dm-date  { color:var(--muted); width:60px; flex-shrink:0; font-variant-numeric:tabular-nums; }
.dm-course{ flex:1; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.dm-score { font-family:'Space Grotesk',sans-serif; font-weight:700; width:28px; text-align:right; flex-shrink:0; font-variant-numeric:tabular-nums; }
.dm-sep   { color:var(--muted-2); flex-shrink:0; }
.dm-w     { color:#86efac; }
.dm-l     { color:#f87171; }
.dm-t     { color:#cbd5e1; }

/* ── Two-column / analytics-grid ─────────────────────────── */
.analytics-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media(max-width:1000px){ .analytics-grid{ grid-template-columns:1fr; } }
.shot-bar-section { padding:20px 22px; display:flex; flex-direction:column; gap:14px; }
.shot-bar-section h3 { font-size:0.7rem; font-weight:600; text-transform:uppercase;
  letter-spacing:0.14em; color:var(--muted); margin-bottom:4px; }
.shot-stat-row { display:flex; flex-direction:column; gap:4px; }
.shot-stat-label { display:flex; justify-content:space-between; font-size:0.78rem; }
.shot-stat-label .ssl-name { font-weight:500; display:inline-flex; align-items:center; gap:6px; }
.shot-stat-label .ssl-val  { color:var(--muted); font-variant-numeric:tabular-nums; }
.shot-stat-bar { height:5px; border-radius:3px; background:rgba(255,255,255,0.06); overflow:hidden; }
.shot-stat-fill { height:100%; border-radius:3px; }
.player-dot { display:inline-block; width:8px; height:8px; border-radius:50%; flex-shrink:0; box-shadow:0 0 6px currentColor; }

/* ── Insights ────────────────────────────────────────────── */
.insights-grid {
  display:grid;
  grid-template-columns: repeat(auto-fill, minmax(260px,1fr));
  gap:14px;
}
.insight-card {
  padding:18px 20px;
  display:flex; flex-direction:column; gap:6px;
  position:relative; overflow:hidden;
  transition:transform .15s, border-color .15s;
}
.insight-card:hover { transform:translateY(-2px); border-color:var(--line-hi); }
.insight-card .ic-tag {
  display:inline-flex; align-items:center; gap:6px;
  font-size:0.6rem; font-weight:600; color:var(--muted);
  letter-spacing:0.16em; text-transform:uppercase;
}
.insight-card .ic-tag .ic-mark {
  width:18px; height:18px; border-radius:5px;
  display:grid; place-items:center;
  background: rgba(79,139,255,0.12); color:var(--accent);
  font-size:0.6rem; font-weight:700; letter-spacing:0;
}
.insight-card .ic-tag .ic-mark svg { width:11px; height:11px; }
.ic-main  { font-family:'Space Grotesk',sans-serif; font-size:1.4rem; font-weight:700; line-height:1.15; letter-spacing:-0.01em; margin-top:2px; }
.ic-sub   { font-size:0.78rem; color:var(--text-dim); }
.ic-extra { font-size:0.7rem; color:var(--muted); margin-top:auto; padding-top:6px; }

/* grade colors */
.grade-A { color: var(--green); } .grade-B { color: #84cc16; }
.grade-C { color: var(--gold); }  .grade-D { color: #f97316; } .grade-F { color: var(--red); }

/* ── Footer ──────────────────────────────────────────────── */
footer {
  padding:18px 22px; color:var(--muted); font-size:0.7rem;
  border-top:1px solid var(--line);
  display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;
}
footer .fl { display:flex; align-items:center; gap:8px; }

/* ── Utility ─────────────────────────────────────────────── */
.no-data { color:var(--muted); font-size:0.8rem; font-style:italic; text-align:center; padding:24px; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media(max-width:760px){ .two-col{ grid-template-columns:1fr; } }
.hidden { display:none !important; }

/* Mobile sidebar collapse */
@media(max-width:1100px){
  .sidebar { position:relative; top:auto; height:auto; max-height:none; }
  .roster {
    flex-direction:row; flex-wrap:wrap; gap:6px;
    max-height: 220px;
  }
  .roster-item { width:auto; flex: 1 1 160px; }
  .sidebar-foot { display:none; }
}
@media(max-width:560px){
  .feature-name { font-size:1.8rem; }
  .stage-feature { padding:18px; min-height:180px; }
  .panel-pad, .panel-pad-l, .matrix-wrap, .duel-panel, .shot-bar-section { padding:16px; }
}
</style>
</head>
<body>

<div class="app">

  <!-- ── Sidebar / roster ─────────────────────────────── -->
  <aside class="sidebar" aria-label="Player roster">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v18"/><path d="M12 4l8 4-8 4"/><circle cx="12" cy="20" r="2"/></svg>
      </div>
      <div class="brand-text">
        <h1>GSPro Analytics</h1>
        <p>Control Room</p>
      </div>
    </div>
    <div class="roster-label">Roster</div>
    <nav class="roster" id="playerFilter" role="tablist" aria-label="Filter by player"></nav>
    <div class="sidebar-foot">
      <span>__ROUND_COUNT__ rounds</span>
      <span>__PLAYER_COUNT__ players</span>
    </div>
  </aside>

  <!-- ── Main ─────────────────────────────────────────── -->
  <main>

    <div class="topbar">
      <div class="crumbs">Dashboard · <strong id="crumbCtx">All Players</strong></div>
      <div class="topbar-spacer"></div>
      <div class="topbar-tag"><span class="live-dot" aria-hidden="true"></span><span>Synced __GENERATED__</span></div>
    </div>

    <!-- KPI strip -->
    <section aria-label="Key metrics">
      <div class="kpi-strip" id="kpiStrip"></div>
    </section>

    <!-- Hero stage -->
    <section aria-label="Featured player and performance">
      <div class="stage" id="stage"></div>
    </section>

    <!-- Leaderboard -->
    <section aria-labelledby="lb-title">
      <div class="section-title" id="lb-title"><span class="st-accent">Leaderboard</span><span class="panel-sub" style="margin-left:auto;text-transform:none;letter-spacing:0">click headers to sort</span></div>
      <div class="panel">
        <div class="lb-wrap"><table class="lb-table" id="leaderboard"></table></div>
      </div>
    </section>

    <!-- Score Journey -->
    <section aria-labelledby="sj-title">
      <div class="section-title" id="sj-title"><span class="st-accent">Score Journey</span><span class="panel-sub" style="margin-left:auto;text-transform:none;letter-spacing:0">18-hole rounds · dashed line = overall trend</span></div>
      <div class="panel chart-card glow"><div class="trend-chart-wrap"><canvas id="trendChart"></canvas></div></div>
    </section>

    <!-- Deep Dive -->
    <section aria-labelledby="dd-title">
      <div class="section-title" id="dd-title"><span class="st-accent">Deep Dive</span></div>
      <div class="analytics-grid">
        <div class="panel chart-card">
          <div class="panel-head"><h3>Strokes vs Personal Baseline</h3></div>
          <div style="padding:0 18px 18px"><canvas id="baselineChart" style="max-height:300px"></canvas></div>
        </div>
        <div class="panel shot-bar-section" id="deepDiveStats"></div>
      </div>
    </section>

    <!-- H2H -->
    <section aria-labelledby="h2h-title">
      <div class="section-title" id="h2h-title"><span class="st-accent">Head-to-Head Arena</span></div>
      <div class="h2h-layout">
        <div class="panel matrix-wrap" id="h2hMatrix"></div>
        <div class="panel duel-panel" id="duelPanel" aria-live="polite">
          <div class="duel-empty">
            <svg class="de-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 17.5L4 7V4h3l10.5 10.5"/><path d="M9.5 17.5L20 7V4h-3L6.5 14.5"/></svg>
            <div>Select any cell to load a rivalry</div>
            <div style="color:var(--muted-2);font-size:0.72rem">Biggest rivalry pre-loads on launch</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Shot Analytics -->
    <section aria-labelledby="sh-title">
      <div class="section-title" id="sh-title"><span class="st-accent">Shot Analytics</span></div>
      <div class="analytics-grid">
        <div class="panel chart-card">
          <div class="panel-head"><h3>Player Radar — Normalized to Group</h3></div>
          <div style="padding:0 18px 18px"><canvas id="radarChart" style="max-height:300px"></canvas></div>
        </div>
        <div class="panel shot-bar-section" id="shotBars"></div>
      </div>
    </section>

    <!-- Intelligence Report -->
    <section aria-labelledby="int-title">
      <div class="section-title" id="int-title"><span class="st-accent">Intelligence Report</span></div>
      <div class="insights-grid" id="insightsGrid"></div>
    </section>

    <!-- Performance Distribution -->
    <section aria-labelledby="pd-title">
      <div class="section-title" id="pd-title"><span class="st-accent">Performance Distribution</span></div>
      <div class="two-col">
        <div class="panel chart-card">
          <div class="panel-head"><h3>Score Distribution (18H)</h3></div>
          <div style="padding:0 18px 18px"><canvas id="distChart" style="max-height:300px"></canvas></div>
        </div>
        <div class="panel chart-card">
          <div class="panel-head"><h3>Top Courses Played</h3></div>
          <div style="padding:0 18px 18px"><canvas id="courseChart" style="max-height:320px"></canvas></div>
        </div>
      </div>
    </section>

    <!-- Activity Timeline -->
    <section aria-labelledby="act-title">
      <div class="section-title" id="act-title"><span class="st-accent">Activity Timeline</span></div>
      <div class="panel chart-card">
        <div class="panel-head"><h3>Rounds per Month</h3></div>
        <div style="padding:0 18px 18px"><canvas id="volumeChart" style="max-height:240px"></canvas></div>
      </div>
    </section>

    <footer>
      <div class="fl"><span class="live-dot" aria-hidden="true"></span><span>GSPro Analytics</span></div>
      <div>Generated __GENERATED__ · __ROUND_COUNT__ rounds · __PLAYER_COUNT__ players</div>
    </footer>

  </main>
</div>

<script>
// ── Embedded data ─────────────────────────────────────────────────────────────
const ROUNDS      = __ROUNDS__;
const PLAYERS     = __PLAYERS__;
const MIN_ROUNDS  = 5;
const COLORS      = __COLORS__;
const PER_PLAYER  = __PERP__;
const H2H         = __H2H__;
const TOP_COURSES = __COURSES__;
const MONTHLY     = __MONTHLY__;

// ── State ─────────────────────────────────────────────────────────────────────
let activePlayer = 'all';
let trendChart, radarChart, courseChart, volumeChart, distChart, baselineChart;
let activeDuel = null;

// ── Chart palette / defaults ─────────────────────────────────────────────────
const CHART_AXIS  = 'rgba(180,196,224,0.45)';
const CHART_GRID  = 'rgba(99,140,210,0.10)';
const CHART_LABEL = 'rgba(180,196,224,0.7)';
if (window.Chart) {
  Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  Chart.defaults.color = CHART_LABEL;
  Chart.defaults.borderColor = CHART_GRID;
}

// ── SVG icons (no emoji) ─────────────────────────────────────────────────────
const ICONS = {
  trophy:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 01-10 0V4z"/><path d="M17 5h3v3a3 3 0 01-3 3M7 5H4v3a3 3 0 003 3"/></svg>',
  flag:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>',
  bolt:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/></svg>',
  target:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/></svg>',
  rounds:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  trend:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></svg>',
  spark:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/></svg>',
  shield:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6l8-3z"/></svg>',
  swords:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 17.5L4 7V4h3l10.5 10.5"/><path d="M9.5 17.5L20 7V4h-3L6.5 14.5"/></svg>',
  map:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>',
  fire:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c1 4 5 5 5 10a5 5 0 11-10 0c0-2 1-3 2-4 0 2 1 3 2 3-1-3 1-6 1-9z"/></svg>',
  crown:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7l4 4 5-7 5 7 4-4v11H3z"/></svg>',
  ruler:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M11 9l2 2M15 5l2 2"/></svg>',
  alert:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 17H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg>',
  dove:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13c4 0 6-3 6-6 2 1 4 0 6-1-1 4 0 7 4 8-3 4-9 6-13 4l-3 3v-4z"/></svg>',
  group:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="9" r="2.5"/><path d="M14 17c0-2 2-4 4-4s3 1 3 4"/></svg>',
  rocket:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14l-4-4M14 4c5 0 6 1 6 6L8 22l-3-3L18 6c0-1-1-2-4-2z"/><circle cx="15" cy="9" r="1.5"/></svg>',
  rotate:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5"/></svg>',
  ext:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4H5v15h15v-7"/><path d="M14 4h6v6M20 4l-9 9"/></svg>',
};

function svgIcon(name) { return ICONS[name] || ''; }
function initials(name){
  if (!name) return '?';
  const parts = String(name).replace(/[^A-Za-z\s]/g,'').trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0]+parts[1][0]).toUpperCase();
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderPills();
  renderKpiStrip();
  renderStage();
  renderLeaderboard();
  initTrendChart();
  initBaselineChart();
  renderH2H();
  initRadarChart();
  renderShotBars();
  renderDeepDiveStats();
  renderInsights();
  initCourseChart();
  initDistChart();
  initVolumeChart();
  // Auto-show biggest rivalry
  const biggestPair = getBiggestRivalry();
  if (biggestPair) showDuel(...biggestPair);
});

// ── Helpers ───────────────────────────────────────────────────────────────────
const avg   = a => a.length ? a.reduce((s,v)=>s+v,0)/a.length : null;
const minOf = a => a.length ? Math.min(...a) : null;
const maxOf = a => a.length ? Math.max(...a) : null;
const fmt1  = n => n != null ? n.toFixed(1) : '—';
const fmtInt= n => n != null ? Math.round(n).toString() : '—';
const isEligible = p => (PER_PLAYER[p]?.count || 0) >= MIN_ROUNDS;
const eligiblePlayers = () => PLAYERS.filter(isEligible);
const rankedPlayers = () => activePlayer === 'all' ? eligiblePlayers() : [activePlayer];

function hexAlpha(hex, a) {
  const r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

function normalize(val, min, max, invert=false) {
  if (max===min) return 50;
  const pct = (val-min)/(max-min)*100;
  return invert ? 100-pct : pct;
}

function getFilteredRounds(player=activePlayer, holes=null) {
  let rs = player==='all' ? ROUNDS : ROUNDS.filter(r=>r.player===player);
  if (holes) rs = rs.filter(r=>r.holeCount===holes);
  return rs;
}

function getBiggestRivalry() {
  let best=0, pair=null;
  for (const p of PLAYERS) for (const q of PLAYERS) {
    if (p>=q) continue;
    const rec = H2H[p]?.[q];
    if (!rec) continue;
    const tot = rec.w+rec.l+rec.t;
    if (tot>best) { best=tot; pair=[p,q]; }
  }
  return pair;
}

// ── Roster (sidebar) ──────────────────────────────────────────────────────────
function renderPills() {
  const el = document.getElementById('playerFilter');
  const all = ['all',...PLAYERS];
  el.innerHTML = all.map(p => {
    const col = p==='all' ? 'var(--accent)' : (COLORS[p]||'#9ca3af');
    const active = p===activePlayer;
    const rounds = p==='all' ? null : (PER_PLAYER[p]?.count ?? null);
    const avatar = p==='all'
      ? `<span class="avatar all" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><path d="M14 17c0-2 2-4 4-4s3 1 3 4"/></svg></span>`
      : `<span class="avatar" style="background:${col}" aria-hidden="true">${initials(p)}</span>`;
    const meta = p==='all' ? '<span class="roster-meta">All</span>' : (rounds!=null ? `<span class="roster-meta">${rounds}</span>` : '');
    const label = p==='all' ? 'All Players' : p;
    return `<button class="roster-item${active?' active':''}" role="tab" aria-selected="${active}" data-player="${p}" onclick="setPlayer('${p}')">${avatar}<span>${label}</span>${meta}</button>`;
  }).join('');
}

function setPlayer(p) {
  activePlayer = p;
  const crumb = document.getElementById('crumbCtx');
  if (crumb) crumb.textContent = p==='all' ? 'All Players' : p;
  renderPills();
  renderKpiStrip();
  renderStage();
  renderLeaderboard();
  updateTrendChart();
  updateBaselineChart();
  renderH2H();
  updateRadarChart();
  renderShotBars();
  renderDeepDiveStats();
  renderInsights();
  updateCourseChart();
  updateDistChart();
  updateVolumeChart();
  if (activeDuel) showDuel(...activeDuel);
}

// ── KPI strip (top of dashboard) ──────────────────────────────────────────────
function kpiCard(icon, label, value, sub) {
  return `<div class="kpi">
    <div class="kpi-icon" aria-hidden="true">${svgIcon(icon)}</div>
    <div class="kpi-body">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-sub">${sub||''}</div>
    </div>
  </div>`;
}

function renderKpiStrip() {
  const el = document.getElementById('kpiStrip');
  const players = rankedPlayers();

  if (activePlayer !== 'all') {
    const p = activePlayer;
    const pp = PER_PLAYER[p];
    el.innerHTML = [
      kpiCard('rounds', 'Rounds Played',  pp.count,                    `${pp.count18} × 18-hole`),
      kpiCard('flag',   'Avg Score (18H)', pp.avg18!=null?fmt1(pp.avg18):'—', `Best ${pp.best18??'—'} · Worst ${pp.worst18??'—'}`),
      kpiCard('shield', 'Consistency',     pp.grade,                   pp.std18!=null?`σ = ${pp.std18} · ${pp.glabel}`:pp.glabel),
      kpiCard('map',    'Courses',         pp.unique_courses,          `#${courseRank(p)} in group`),
    ].join('');
    return;
  }

  const eligible = eligiblePlayers();
  const totalRounds = ROUNDS.length;
  const total18 = ROUNDS.filter(r=>r.holeCount===18).length;
  const sorted18 = players.filter(p=>PER_PLAYER[p].avg18!=null).sort((a,b)=>PER_PLAYER[a].avg18-PER_PLAYER[b].avg18);
  const leader = sorted18[0];
  const groupAvg = sorted18.length ? avg(sorted18.map(p=>PER_PLAYER[p].avg18)) : null;
  const courses = new Set(ROUNDS.map(r=>r.course).filter(Boolean));

  el.innerHTML = [
    kpiCard('rounds', 'Total Rounds',  totalRounds,                   `${total18} qualifying · ${eligible.length} eligible players`),
    kpiCard('flag',   'Group Avg (18H)', groupAvg!=null?fmt1(groupAvg):'—', leader?`Leader ${leader} · ${fmt1(PER_PLAYER[leader].avg18)}`:''),
    kpiCard('trophy', 'Top Score',     leader||'—',                   leader?`${PER_PLAYER[leader].best18} best · ${PER_PLAYER[leader].count18} rds`:''),
    kpiCard('map',    'Courses Played', courses.size,                 `Across ${PLAYERS.length} players`),
  ].join('');
}

// ── Stage (feature panel + gauge + stat-pair) ─────────────────────────────────
function renderStage() {
  const el = document.getElementById('stage');
  const players = rankedPlayers();

  let featured, eyebrow, tag, statBlocks, gaugeVal, gaugeLabel, gaugeColor;

  if (activePlayer !== 'all') {
    const p = activePlayer;
    const pp = PER_PLAYER[p];
    featured  = p;
    eyebrow   = 'Player Spotlight';
    tag       = `${pp.archetype[1]} · ${pp.glabel}`;
    statBlocks = [
      ['Avg 18H',    pp.avg18!=null?fmt1(pp.avg18):'—'],
      ['Best',       pp.best18??'—'],
      ['Rounds',     pp.count],
      ['H2H Win%',   `${pp.win_rate}%`],
    ];
    // Gauge: percentile (lower avg = higher percentile of group)
    const allAvgs = PLAYERS.map(x=>PER_PLAYER[x].avg18).filter(v=>v!=null);
    if (pp.avg18!=null && allAvgs.length){
      const better = allAvgs.filter(v=>v>=pp.avg18).length;
      gaugeVal   = Math.round(better/allAvgs.length*100);
      gaugeLabel = 'Group Percentile';
    } else {
      gaugeVal = 50; gaugeLabel = 'No data';
    }
    gaugeColor = COLORS[p] || 'var(--accent)';
  } else {
    const sorted18 = players.filter(p=>PER_PLAYER[p].avg18!=null).sort((a,b)=>PER_PLAYER[a].avg18-PER_PLAYER[b].avg18);
    const leader = sorted18[0];
    const pp = leader ? PER_PLAYER[leader] : null;
    featured  = leader || '—';
    eyebrow   = 'Scoring Leader';
    tag       = pp ? `${pp.archetype[1]} · grade ${pp.grade}` : '';
    statBlocks = pp ? [
      ['Avg 18H',    fmt1(pp.avg18)],
      ['Best',       pp.best18],
      ['Rounds',     pp.count],
      ['Form',       pp.form_label||'—'],
    ] : [];
    // Gauge: form_diff scaled
    if (pp && pp.form_diff!=null) {
      gaugeVal = Math.max(0, Math.min(100, Math.round(50 + pp.form_diff*8)));
      gaugeLabel = pp.form_label || 'Current Form';
    } else {
      gaugeVal = 60; gaugeLabel = 'Form trend';
    }
    gaugeColor = leader ? (COLORS[leader]||'var(--accent)') : 'var(--accent)';
  }

  const featCol = COLORS[featured] || 'var(--accent)';
  const featStatsHtml = statBlocks.map(([l,v])=>`<div class="feature-stat"><div class="fs-label">${l}</div><div class="fs-value">${v}</div></div>`).join('');

  // hottest form & most consistent for side stat-pair (always shown)
  const eligible = eligiblePlayers();
  const hottest = eligible.filter(p=>PER_PLAYER[p].form_diff!=null).sort((a,b)=>PER_PLAYER[b].form_diff-PER_PLAYER[a].form_diff)[0];
  const mostConsistent = eligible.filter(p=>PER_PLAYER[p].std18!=null).sort((a,b)=>PER_PLAYER[a].std18-PER_PLAYER[b].std18)[0];
  const mostActive = [...eligible].sort((a,b)=>PER_PLAYER[b].count-PER_PLAYER[a].count)[0];

  el.innerHTML = `
    <div class="panel stage-feature glow">
      <div class="feature-eyebrow">${eyebrow}</div>
      <div class="feature-name" style="color:${featCol}">${featured}</div>
      <div class="feature-tag">${tag}</div>
      <div class="feature-stats">${featStatsHtml}</div>
      ${activePlayer==='all' && featured!=='—' ? `<button class="feature-cta" type="button" onclick="setPlayer('${featured}')">View profile</button>` : ''}
    </div>
    <div class="panel gauge-panel">
      <div class="panel-head" style="padding:0">
        <h3>Performance</h3>
      </div>
      ${gaugeSvg(gaugeVal, gaugeColor, gaugeLabel)}
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Group Pulse</h3></div>
      <div class="statpair">
        <div>
          <div class="sp-label">Hottest Form</div>
          <div class="sp-value">${hottest?hottest:'—'}</div>
          <div class="sp-sub">${hottest?(PER_PLAYER[hottest].form_label||'')+(PER_PLAYER[hottest].form_diff!=null?` · ${PER_PLAYER[hottest].form_diff>0?'+':''}${fmt1(PER_PLAYER[hottest].form_diff)}`:''):''}</div>
        </div>
        <div>
          <div class="sp-label">Most Consistent</div>
          <div class="sp-value">${mostConsistent?mostConsistent:'—'}</div>
          <div class="sp-sub">${mostConsistent?`σ ${PER_PLAYER[mostConsistent].std18} · grade ${PER_PLAYER[mostConsistent].grade}`:''}</div>
        </div>
        <div>
          <div class="sp-label">Most Active</div>
          <div class="sp-value">${mostActive?mostActive:'—'}</div>
          <div class="sp-sub">${mostActive?`${PER_PLAYER[mostActive].count} rounds`:''}</div>
        </div>
        <div>
          <div class="sp-label">Eligible</div>
          <div class="sp-value">${eligible.length}/${PLAYERS.length}</div>
          <div class="sp-sub">${MIN_ROUNDS}+ rounds</div>
        </div>
      </div>
    </div>`;
}

function gaugeSvg(value, color, label) {
  const v = Math.max(0, Math.min(100, value));
  const r = 70, cx = 80, cy = 80;
  const start = Math.PI, end = 2*Math.PI;
  const ang = start + (end-start) * (v/100);
  const sx = cx + r*Math.cos(start), sy = cy + r*Math.sin(start);
  const ex = cx + r*Math.cos(ang),   ey = cy + r*Math.sin(ang);
  const ex2 = cx + r*Math.cos(end),  ey2 = cy + r*Math.sin(end);
  const large = (ang-start) > Math.PI ? 1 : 0;
  return `<div class="gauge-wrap">
    <div class="gauge">
      <svg viewBox="0 0 160 90" width="160" height="90" aria-label="Gauge">
        <defs>
          <linearGradient id="gg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="${color}"/>
          </linearGradient>
        </defs>
        <path d="M ${sx} ${sy} A ${r} ${r} 0 1 1 ${ex2} ${ey2}" fill="none" stroke="rgba(99,140,210,0.18)" stroke-width="10" stroke-linecap="round"/>
        <path d="M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}" fill="none" stroke="url(#gg)" stroke-width="10" stroke-linecap="round" style="filter:drop-shadow(0 0 6px ${color})"/>
      </svg>
      <div class="gauge-readout">
        <div class="gr-num" style="color:${color}">${v}<span style="font-size:0.9rem;color:var(--muted)">%</span></div>
        <div class="gr-cap">${label}</div>
      </div>
    </div>
  </div>`;
}

function courseRank(p) {
  return [...PLAYERS].sort((a,b)=>PER_PLAYER[b].unique_courses-PER_PLAYER[a].unique_courses).indexOf(p)+1;
}

// ── Leaderboard ───────────────────────────────────────────────────────────────
let lbSort = {col:'avg18', dir:1};
function renderLeaderboard() {
  const players = rankedPlayers();
  const ranked  = [...players].filter(p=>PER_PLAYER[p].avg18!=null).sort((a,b)=>{
    const va=PER_PLAYER[a][lbSort.col]??9999, vb=PER_PLAYER[b][lbSort.col]??9999;
    return lbSort.dir*(va-vb);
  });

  const cols = [
    {k:'rank',   label:'#',       sort:false},
    {k:'player', label:'Player',  sort:false},
    {k:'count',  label:'Rounds',  sort:true},
    {k:'avg18',  label:'Avg (18H)',sort:true},
    {k:'best18', label:'Best',    sort:true},
    {k:'std18',  label:'Consistency',sort:true},
    {k:'form',   label:'Form',    sort:false},
    {k:'win_rate',label:'H2H Win%',sort:true},
    {k:'arch',   label:'Archetype',sort:false},
  ];

  const allAvgs = ranked.map(p=>PER_PLAYER[p].avg18).filter(Boolean);
  const minA=minOf(allAvgs)||70, maxA=maxOf(allAvgs)||110;

  const thead = `<thead><tr>${cols.map(c=>{
    if (!c.sort) return `<th>${c.label}</th>`;
    const ind = lbSort.col===c.k ? `<span class="sort-ind" aria-hidden="true">${lbSort.dir>0?'↑':'↓'}</span>` : '';
    const aria = lbSort.col===c.k ? (lbSort.dir>0?'ascending':'descending') : 'none';
    return `<th aria-sort="${aria}"><button type="button" class="th-btn" onclick="sortLB('${c.k}')" aria-label="Sort by ${c.label}">${c.label}${ind}</button></th>`;
  }).join('')}</tr></thead>`;

  const tbody = `<tbody>${ranked.map((p,i)=>{
    const pp=PER_PLAYER[p], col=COLORS[p]||'#9ca3af';
    const rank = i+1;
    const rankClass = rank===1?'r1':rank===2?'r2':rank===3?'r3':'';
    const gradeCls = `grade-${pp.grade}`;
    const formCol = pp.form_diff==null?'var(--muted)':pp.form_diff>0?'#22c55e':'#ef4444';
    const fillPct = pp.avg18!=null ? (1-(pp.avg18-minA)/(maxA-minA))*100 : 0;
    return `<tr>
      <td><span class="lb-num ${rankClass}">${String(rank).padStart(2,'0')}</span></td>
      <td><button type="button" class="lb-player" style="background:none;border:none;color:inherit;cursor:pointer;padding:0;font:inherit" onclick="setPlayer('${p}')" aria-label="View ${p}"><span class="player-dot" style="background:${col};color:${col}"></span><span>${p}</span></button></td>
      <td><span class="lb-strong">${pp.count}</span> <span class="lb-muted">(${pp.count18}×18)</span></td>
      <td><div class="score-bar-wrap">
        <span class="lb-strong">${pp.avg18!=null?fmt1(pp.avg18):'—'}</span>
        <div class="score-bar-bg"><div class="score-bar-fill" style="width:${fillPct.toFixed(1)}%;background:linear-gradient(90deg,${col},${hexAlpha(col,0.5)})"></div></div>
      </div></td>
      <td><span class="lb-strong" style="color:${col}">${pp.best18??'—'}</span></td>
      <td><span class="grade-badge ${gradeCls}">${pp.grade}</span> <span class="lb-muted">${pp.glabel}</span></td>
      <td><span class="form-pill" style="color:${formCol}">${pp.form_label??'—'}</span></td>
      <td><span class="lb-strong">${pp.win_rate}%</span> <span class="lb-muted">${pp.total_games}g</span></td>
      <td class="arch-cell" title="${pp.archetype[1]}"><span class="arch-key">${pp.archetype[0]}</span>${pp.archetype[1]}</td>
    </tr>`;
  }).join('')}</tbody>`;

  document.getElementById('leaderboard').innerHTML = thead+tbody;
}

function sortLB(col) {
  if (lbSort.col===col) lbSort.dir*=-1;
  else { lbSort.col=col; lbSort.dir=1; }
  renderLeaderboard();
}

// ── Trend chart ───────────────────────────────────────────────────────────────
const dateToTs = d => new Date(d + 'T12:00:00Z').getTime();
const fmtTick  = ts => {
  const d = new Date(ts);
  return d.toLocaleDateString('en-US', {month:'short', year:'2-digit', timeZone:'UTC'});
};

function linReg(pts) {
  const n = pts.length;
  if (n < 2) return null;
  const xm = pts.reduce((s,p)=>s+p.x,0)/n;
  const ym = pts.reduce((s,p)=>s+p.y,0)/n;
  const num = pts.reduce((s,p)=>s+(p.x-xm)*(p.y-ym),0);
  const den = pts.reduce((s,p)=>s+(p.x-xm)**2,0);
  const slope = den ? num/den : 0;
  const intcpt = ym - slope*xm;
  return {
    start: { x: pts[0].x,   y: Math.round((slope*pts[0].x  +intcpt)*10)/10 },
    end:   { x: pts[n-1].x, y: Math.round((slope*pts[n-1].x+intcpt)*10)/10 },
    slope,
  };
}

function buildTrendDatasets() {
  const datasets = [];
  for (const p of PLAYERS) {
    const pp  = PER_PLAYER[p];
    const raw = pp.trend18 || [];
    if (!raw.length) continue;
    const col   = COLORS[p]||'#9ca3af';
    const isSel = activePlayer===p;
    const isAll = activePlayer==='all';
    const alpha = isAll ? 0.60 : (isSel ? 1.0 : 0.10);
    const dotSz = isAll ? 3   : (isSel ? 5   : 1);

    // Scatter: one dot per actual round (timestamp x, score y)
    const pts = raw.map(d=>({x: dateToTs(d.d), y: d.s, date: d.d}));
    datasets.push({
      label: p,
      data: pts,
      type: 'scatter',
      backgroundColor: hexAlpha(col, alpha),
      pointRadius: dotSz,
      pointHoverRadius: dotSz + 2,
      parsing: false,
      order: 2,
    });

    // Trend line: linear regression across timestamps
    const reg = linReg(pts);
    if (reg) {
      const improving = reg.slope < 0;
      const lineCol = isSel
        ? (improving ? '#22c55e' : '#f87171')
        : hexAlpha(col, isAll ? 0.7 : 0.08);
      datasets.push({
        label: `${p}_trend`,
        data: [reg.start, reg.end],
        type: 'line',
        borderColor: lineCol,
        backgroundColor: 'transparent',
        borderWidth: isSel ? 2.5 : 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        parsing: false,
        order: 1,
      });
    }
  }
  return datasets;
}

function initTrendChart() {
  const ctx = document.getElementById('trendChart').getContext('2d');
  trendChart = new Chart(ctx, {
    type: 'scatter',
    data: { datasets: buildTrendDatasets() },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 300 },
      parsing: false,
      scales: {
        x: {
          type: 'linear',
          ticks: {
            color:CHART_AXIS, maxTicksLimit:12, font:{size:10},
            callback: fmtTick,
          },
          grid: { color:CHART_GRID },
        },
        y: {
          ticks: { color:CHART_AXIS, font:{size:10} },
          grid:  { color:CHART_GRID },
          title: { display:true, text:'Score', color:CHART_AXIS, font:{size:10} },
        }
      },
      plugins: {
        legend: {
          display: true, position:'bottom',
          labels: {
            color:CHART_LABEL, boxWidth:12, font:{size:11},
            filter: item => !item.text.endsWith('_trend'),
          }
        },
        tooltip: {
          filter: item => !item.dataset.label?.endsWith('_trend'),
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.raw.y}  (${ctx.raw.date})`,
          }
        }
      }
    }
  });
}

function updateTrendChart() {
  if (!trendChart) return;
  trendChart.data.datasets = buildTrendDatasets();
  trendChart.update('none');
}

// ── Baseline chart ─────────────────────────────────────────────────────────────
function buildBaselineDatasets() {
  const players = activePlayer==='all' ? rankedPlayers() : [activePlayer];
  const datasets = [];
  for (const p of players) {
    const raw = PER_PLAYER[p].baseline_vs || [];
    const pts = raw.filter(d=>d.vs!=null).map(d=>({x:dateToTs(d.d), y:d.vs, date:d.d, score:d.score, baseline:d.baseline}));
    if (!pts.length) continue;
    const col = COLORS[p]||'#9ca3af';
    datasets.push({
      label: p,
      data: pts,
      type: 'line',
      borderColor: hexAlpha(col, activePlayer==='all' ? 0.75 : 1),
      backgroundColor: hexAlpha(col, 0.18),
      pointBackgroundColor: col,
      pointRadius: activePlayer==='all' ? 2.5 : 4,
      borderWidth: activePlayer==='all' ? 1.5 : 2.5,
      tension: 0.25,
      parsing: false,
    });
  }
  return datasets;
}

function initBaselineChart() {
  const ctx = document.getElementById('baselineChart').getContext('2d');
  baselineChart = new Chart(ctx, {
    type: 'line',
    data: { datasets: buildBaselineDatasets() },
    options: {
      responsive:true, maintainAspectRatio:true, parsing:false,
      plugins:{
        legend:{ display:activePlayer==='all', position:'bottom', labels:{color:CHART_LABEL,boxWidth:12,font:{size:10}} },
        tooltip:{ callbacks:{ label:c=>` ${c.dataset.label}: ${c.raw.y>0?'+':''}${fmt1(c.raw.y)} vs baseline (${c.raw.score} on ${c.raw.date})` } }
      },
      scales:{
        x:{ type:'linear', ticks:{color:CHART_AXIS,maxTicksLimit:12,font:{size:10},callback:fmtTick}, grid:{color:CHART_GRID} },
        y:{ ticks:{color:CHART_AXIS,font:{size:10},callback:v=>v>0?`+${v}`:v}, grid:{color:CHART_GRID}, title:{display:true,text:'Strokes vs prior 10-round average',color:CHART_AXIS,font:{size:10}} }
      }
    }
  });
}

function updateBaselineChart() {
  if (!baselineChart) return;
  baselineChart.data.datasets = buildBaselineDatasets();
  baselineChart.options.plugins.legend.display = activePlayer==='all';
  baselineChart.update('none');
}

// ── H2H Matrix ────────────────────────────────────────────────────────────────
function renderH2H() {
  const showPlayers = activePlayer==='all' ? eligiblePlayers() : PLAYERS;
  let html = `<div style="font-size:0.66rem;font-weight:600;text-transform:uppercase;letter-spacing:0.16em;color:var(--muted);margin-bottom:14px;">Row beats Column — select a cell to load duel</div>`;
  html += `<table class="matrix-table" role="grid" aria-label="Head-to-head record matrix"><thead><tr><th scope="col"></th>`;
  for (const q of showPlayers) {
    const col = COLORS[q]||'#9ca3af';
    html += `<th scope="col" style="color:${col}">${q}</th>`;
  }
  html += `</tr></thead><tbody>`;
  for (const p of showPlayers) {
    const pcol = COLORS[p]||'#9ca3af';
    const dim  = activePlayer!=='all' && activePlayer!==p;
    html += `<tr style="${dim?'opacity:0.35':''}">`;
    html += `<th scope="row" class="row-head" style="color:${pcol}">${p}</th>`;
    for (const q of showPlayers) {
      if (p===q) { html+=`<td class="matrix-cell self" aria-label="—">—</td>`; continue; }
      const rec = H2H[p]?.[q];
      if (!rec) { html+=`<td class="matrix-cell self" aria-label="No data">·</td>`; continue; }
      const tot = rec.w+rec.l+rec.t;
      const winPct = tot>0 ? rec.w/tot : 0.5;
      const cls = winPct>=0.65?'win':winPct>=0.55?'edge':winPct>=0.45?'even':winPct>=0.35?'trail':'loss';
      const isActive = activeDuel && ((activeDuel[0]===p&&activeDuel[1]===q)||(activeDuel[0]===q&&activeDuel[1]===p));
      const ariaLabel = `${p} versus ${q}: ${rec.w} wins, ${rec.l} losses${rec.t?', '+rec.t+' ties':''}. View duel.`;
      html += `<td><button type="button" class="matrix-cell ${cls}${isActive?' active':''}" onclick="showDuel('${p}','${q}')" aria-label="${ariaLabel}">${rec.w}-${rec.l}${rec.t>0?'-'+rec.t:''}</button></td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  document.getElementById('h2hMatrix').innerHTML = html;
}

function showDuel(p1, p2) {
  activeDuel = [p1, p2];
  renderH2H(); // refresh matrix to show active cell
  const rec1 = H2H[p1]?.[p2]||{w:0,l:0,t:0};
  const col1 = COLORS[p1]||'#9ca3af', col2 = COLORS[p2]||'#9ca3af';
  const tot  = rec1.w+rec1.l+rec1.t;
  const pct1 = tot>0 ? Math.round(rec1.w/tot*100) : 50;
  const winPct2 = tot>0 ? Math.round(rec1.l/tot*100) : 50;

  // Get shared rounds from raw data
  const sessions = {};
  for (const r of ROUNDS) {
    if (!r.date||!r.course||!r.score) continue;
    const k = r.date+'::'+r.course+'::'+r.holeCount;
    if (!sessions[k]) sessions[k]=[];
    sessions[k].push(r);
  }
  const shared = [];
  for (const rs of Object.values(sessions)) {
    const a = rs.find(r=>r.player===p1), b = rs.find(r=>r.player===p2);
    if (a&&b) shared.push({date:a.date, course:a.course, hc:a.holeCount, [p1]:+a.score, [p2]:+b.score});
  }
  shared.sort((a,b)=>b.date.localeCompare(a.date));

  // Avg margin when each wins
  let sum1=0,cnt1=0,sum2=0,cnt2=0;
  for (const s of shared) {
    const diff = s[p1]-s[p2];
    if (diff<0){ sum1+=Math.abs(diff); cnt1++; }
    else if(diff>0){ sum2+=diff; cnt2++; }
  }
  const margin1 = cnt1>0?fmt1(sum1/cnt1):'—';
  const margin2 = cnt2>0?fmt1(sum2/cnt2):'—';

  const recent = shared.slice(0,8);
  const last5 = shared.slice(0,5);
  const recentRec = last5.reduce((a,s)=>{
    if (s[p1] < s[p2]) a.p1++;
    else if (s[p2] < s[p1]) a.p2++;
    else a.t++;
    return a;
  }, {p1:0,p2:0,t:0});
  const recentLeader = recentRec.p1===recentRec.p2 ? 'Tied' : (recentRec.p1>recentRec.p2 ? p1 : p2);

  const panel = document.getElementById('duelPanel');
  panel.innerHTML = `
    <div class="duel-header">
      <div class="duel-player">
        <div class="dp-name" style="color:${col1}">${p1}</div>
        <div class="dp-record" style="color:${col1}">${rec1.w}</div>
        <div class="dp-sub">wins · margin ${margin1}</div>
      </div>
      <div class="duel-vs">VS</div>
      <div class="duel-player">
        <div class="dp-name" style="color:${col2}">${p2}</div>
        <div class="dp-record" style="color:${col2}">${rec1.l}</div>
        <div class="dp-sub">wins · margin ${margin2}</div>
      </div>
    </div>
    ${rec1.t>0?`<div style="text-align:center;font-size:0.72rem;color:var(--muted)">${rec1.t} tie${rec1.t>1?'s':''}</div>`:''}
    <div>
      <div class="duel-bar-wrap">
        <div class="duel-bar-fill" style="width:${pct1}%;background:linear-gradient(90deg,${col1},${hexAlpha(col1,0.6)})"></div>
      </div>
      <div class="duel-stat-row" style="margin-top:5px">
        <span style="color:${col1};font-weight:700">${pct1}%</span>
        <span style="color:var(--muted);font-size:0.72rem">${tot} shared rounds</span>
        <span style="color:${col2};font-weight:700">${winPct2}%</span>
      </div>
      <div style="text-align:center;font-size:0.74rem;color:var(--text-dim);margin-top:8px">
        Recent: ${recentLeader} ${recentRec.p1}-${recentRec.p2}${recentRec.t?'-'+recentRec.t:''} over last ${last5.length}
      </div>
    </div>
    <div class="duel-recent">
      <h4>Recent Matchups</h4>
      ${recent.map(s=>{
        const d1=s[p1], d2=s[p2];
        const w1=d1<d2, tied=d1===d2;
        return `<div class="duel-match-row">
          <span class="dm-date">${s.date.slice(5)}</span>
          <span class="dm-course">${s.course}</span>
          <span class="dm-score ${w1?'dm-w':(!tied?'dm-l':'dm-t')}">${d1}</span>
          <span class="dm-sep">–</span>
          <span class="dm-score ${!w1&&!tied?'dm-w':(tied?'dm-t':'dm-l')}">${d2}</span>
          <span style="font-size:0.65rem;color:var(--muted)">${s.hc}H</span>
        </div>`;
      }).join('')}
    </div>`;
}

// ── Radar chart ───────────────────────────────────────────────────────────────
const RADAR_AXES = ['Tee Accuracy','Iron Precision','Birdie+','Scoring','Consistency'];

function radarValues(p) {
  const pp = PER_PLAYER[p];
  // raw values
  const fir   = pp.avg_fir18;
  const gir   = pp.avg_gir18;
  const birdies = pp.avg_birdies18;
  const score = pp.avg18;
  const std   = pp.std18;
  // normalize within group ranges
  const baseline = activePlayer==='all' ? eligiblePlayers() : PLAYERS;
  const allFir   = baseline.map(x=>PER_PLAYER[x].avg_fir18).filter(Boolean);
  const allGir   = baseline.map(x=>PER_PLAYER[x].avg_gir18).filter(Boolean);
  const allBirdies = baseline.map(x=>PER_PLAYER[x].avg_birdies18).filter(Boolean);
  const allScore = baseline.map(x=>PER_PLAYER[x].avg18).filter(Boolean);
  const allStd   = baseline.map(x=>PER_PLAYER[x].std18).filter(Boolean);
  return [
    fir   != null ? normalize(fir,   Math.min(...allFir),   Math.max(...allFir))   : 0,
    gir   != null ? normalize(gir,   Math.min(...allGir),   Math.max(...allGir))   : 0,
    birdies != null ? normalize(birdies, Math.min(...allBirdies), Math.max(...allBirdies)) : 0,
    score != null ? normalize(score, Math.min(...allScore), Math.max(...allScore), true) : 0,
    std   != null ? normalize(std,   Math.min(...allStd),   Math.max(...allStd),   true) : 0,
  ].map(v=>Math.round(v));
}

function buildRadarDatasets() {
  const players = rankedPlayers();
  return players.map(p=>{
    const col = COLORS[p]||'#9ca3af';
    const alpha = activePlayer==='all' ? 0.35 : 0.5;
    return {
      label: p,
      data: radarValues(p),
      borderColor: hexAlpha(col, 0.85),
      backgroundColor: hexAlpha(col, alpha),
      borderWidth: 2,
      pointBackgroundColor: col,
      pointRadius: 3,
    };
  });
}

function initRadarChart() {
  const ctx = document.getElementById('radarChart').getContext('2d');
  radarChart = new Chart(ctx, {
    type: 'radar',
    data: { labels: RADAR_AXES, datasets: buildRadarDatasets() },
    options: {
      responsive:true, maintainAspectRatio:true,
      scales:{ r:{
        min:0, max:100,
        ticks:{ display:false },
        grid:{ color:CHART_GRID },
        angleLines:{ color:CHART_GRID },
        pointLabels:{ color:CHART_LABEL, font:{size:11} },
      }},
      plugins:{ legend:{ display:activePlayer==='all', position:'bottom', labels:{ color:CHART_LABEL, boxWidth:12, font:{size:10} } } },
      animation:{ duration:300 },
    }
  });
}

function updateRadarChart() {
  if (!radarChart) return;
  radarChart.data.datasets = buildRadarDatasets();
  radarChart.options.plugins.legend.display = activePlayer==='all';
  radarChart.update('none');
}

// ── Shot bars ─────────────────────────────────────────────────────────────────
function renderShotBars() {
  const el = document.getElementById('shotBars');
  const players = rankedPlayers();
  const stats = [
    { key:'avg_fir18', label:'Fairways Hit (avg)', max:8, better:'higher' },
    { key:'avg_gir18', label:'Greens in Regulation (avg)', max:10, better:'higher' },
    { key:'avg_birdies18', label:'Birdies per Round (avg)', max:6, better:'higher' },
  ];
  el.innerHTML = `<h3>Avg Stats per Round (18H)</h3>` + stats.map(st=>{
    const rows = players.filter(p=>PER_PLAYER[p][st.key]!=null).map(p=>{
      const val = PER_PLAYER[p][st.key];
      const col = COLORS[p]||'#9ca3af';
      const pct = Math.min(val/st.max*100, 100);
      return `<div class="shot-stat-row">
        <div class="shot-stat-label">
          <span class="ssl-name"><span class="player-dot" style="background:${col}"></span>${p}</span>
          <span class="ssl-val">${fmt1(val)}</span>
        </div>
        <div class="shot-stat-bar">
          <div class="shot-stat-fill" style="width:${pct.toFixed(1)}%;background:${col}"></div>
        </div>
      </div>`;
    }).join('');
    return `<div><div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--muted);margin-bottom:8px">${st.label}</div>${rows}</div>`;
  }).join('');
}

function renderDeepDiveStats() {
  const el = document.getElementById('deepDiveStats');
  const players = rankedPlayers();
  const stats = [
    { key:'last_vs_baseline', label:'Last Round vs Baseline', suffix:' strokes', lower:true, signed:true },
    { key:'std10', label:'Volatility Index (last 10)', suffix:' σ', lower:true },
    { key:'blowup_recent18', label:'Blow-up Holes (last 5 avg)', suffix:' / round', lower:true },
    { key:'birdies_recent18', label:'Birdie+ Rate (last 5 avg)', suffix:' / round', lower:false },
    { key:'sim_index', label:'Simulator Index Estimate', suffix:'', lower:true },
  ];
  el.innerHTML = `<h3>Deep Metrics — 18H Only</h3>` + stats.map(st=>{
    const rows = players
      .filter(p=>PER_PLAYER[p][st.key]!=null)
      .sort((a,b)=>st.lower ? PER_PLAYER[a][st.key]-PER_PLAYER[b][st.key] : PER_PLAYER[b][st.key]-PER_PLAYER[a][st.key])
      .map(p=>{
        const pp = PER_PLAYER[p], val = pp[st.key], col = COLORS[p]||'#9ca3af';
        const shown = st.signed && val>0 ? `+${fmt1(val)}` : fmt1(val);
        return `<div class="shot-stat-row">
          <div class="shot-stat-label">
            <span class="ssl-name"><span class="player-dot" style="background:${col}"></span>${p}</span>
            <span class="ssl-val">${shown}${st.suffix}</span>
          </div>
          <div class="shot-stat-bar">
            <div class="shot-stat-fill" style="width:${Math.max(8, Math.min(100, Math.abs(val)*12)).toFixed(1)}%;background:${col}"></div>
          </div>
        </div>`;
      }).join('');
    return `<div><div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--muted);margin-bottom:8px">${st.label}</div>${rows || '<div class="no-data">Not enough data</div>'}</div>`;
  }).join('');
}

// ── Insights ──────────────────────────────────────────────────────────────────
function renderInsights() {
  const el = document.getElementById('insightsGrid');
  const players = rankedPlayers();

  const cards = [];

  if (activePlayer==='all') {
    // Group-wide insights
    const eligible = eligiblePlayers();
    const byGrind = [...eligible].sort((a,b)=>PER_PLAYER[b].count-PER_PLAYER[a].count);
    const byExp   = [...eligible].sort((a,b)=>PER_PLAYER[b].unique_courses-PER_PLAYER[a].unique_courses);
    const byForm  = [...eligible].filter(p=>PER_PLAYER[p].form_diff!=null).sort((a,b)=>PER_PLAYER[b].form_diff-PER_PLAYER[a].form_diff);
    const byCons  = [...eligible].filter(p=>PER_PLAYER[p].std18!=null).sort((a,b)=>PER_PLAYER[a].std18-PER_PLAYER[b].std18);
    const groupAvgRounds = Math.round(eligible.reduce((s,p)=>s+PER_PLAYER[p].count,0)/eligible.length);

    cards.push(insightCard('bolt',  'The Grinder',byGrind[0],`${PER_PLAYER[byGrind[0]].count} rounds played`,`${Math.round(PER_PLAYER[byGrind[0]].count/groupAvgRounds*10)/10}× the group average · never quits`,'var(--accent)'));
    cards.push(insightCard('map',   'Course Explorer',byExp[0],`${PER_PLAYER[byExp[0]].unique_courses} unique courses`,`Most diverse catalog in the group`,'var(--accent-2)'));
    cards.push(insightCard('fire',  'Hottest Streak',byForm[0]||null,byForm[0]?PER_PLAYER[byForm[0]].form_label:'—',byForm[0]?`+${fmt1(PER_PLAYER[byForm[0]].form_diff)} strokes better than season avg`:'','var(--gold)'));
    cards.push(insightCard('target','Most Consistent',byCons[0],`Grade ${PER_PLAYER[byCons[0]].grade}`,`σ = ${PER_PLAYER[byCons[0]].std18} — most predictable in the group`,'var(--accent-2)'));

    // Best single round
    const allR18 = ROUNDS.filter(r=>r.holeCount===18&&r.score&&isEligible(r.player));
    const bestRound = allR18.reduce((b,r)=>!b||+r.score<+b.score?r:b, null);
    if (bestRound) cards.push(insightCard('trophy','Best Single Round',bestRound.player,bestRound.score,`${bestRound.course} · ${bestRound.date}`,'var(--gold)'));

    // Biggest rivalry
    const pair = getBiggestRivalry();
    if (pair) {
      const rec = H2H[pair[0]]?.[pair[1]]||{};
      const tot = (rec.w||0)+(rec.l||0)+(rec.t||0);
      cards.push(insightCard('swords','Fiercest Rivalry',`${pair[0]} vs ${pair[1]}`,`${tot} shared rounds`,`${pair[0]} leads ${rec.w||0}–${rec.l||0} (${rec.t||0} ties)`,'var(--accent)'));
    }

    // Most dominant player
    const dom = [...eligible].filter(p=>PER_PLAYER[p].total_games>=5).sort((a,b)=>PER_PLAYER[b].win_rate-PER_PLAYER[a].win_rate)[0];
    if (dom) cards.push(insightCard('crown','H2H Dominant',dom,`${PER_PLAYER[dom].win_rate}% win rate`,`${PER_PLAYER[dom].total_games} head-to-head games`,'var(--gold)'));

    // Most improved
    const byVel = [...eligible].filter(p=>PER_PLAYER[p].velocity!=null).sort((a,b)=>PER_PLAYER[a].velocity-PER_PLAYER[b].velocity);
    if (byVel[0]) {
      const v = PER_PLAYER[byVel[0]].velocity;
      cards.push(insightCard('trend','Fastest Improving',byVel[0],`${Math.abs(v).toFixed(2)} strokes/round`,`Last 20 rounds · trending ${v<0?'down':'up'}`,'var(--green)'));
    }
    const byBlow = [...eligible].filter(p=>PER_PLAYER[p].blowup_recent18!=null).sort((a,b)=>PER_PLAYER[a].blowup_recent18-PER_PLAYER[b].blowup_recent18);
    if (byBlow[0]) cards.push(insightCard('shield','Fewest Blow-ups',byBlow[0],`${fmt1(PER_PLAYER[byBlow[0]].blowup_recent18)} / rd`,`Double bogeys or worse, last 5 rounds`,'var(--green)'));
    const byBird = [...eligible].filter(p=>PER_PLAYER[p].birdies_recent18!=null).sort((a,b)=>PER_PLAYER[b].birdies_recent18-PER_PLAYER[a].birdies_recent18);
    if (byBird[0]) cards.push(insightCard('dove','Birdie Heat',byBird[0],`${fmt1(PER_PLAYER[byBird[0]].birdies_recent18)} / rd`,`Birdies plus eagles, last 5 rounds`,'var(--gold)'));
    const byIndex = [...eligible].filter(p=>PER_PLAYER[p].sim_index!=null).sort((a,b)=>PER_PLAYER[a].sim_index-PER_PLAYER[b].sim_index);
    if (byIndex[0]) cards.push(insightCard('ruler','Lowest Sim Index',byIndex[0],fmt1(PER_PLAYER[byIndex[0]].sim_index),`Best differentials, last 20 rounds`,'var(--accent)'));

  } else {
    const p  = activePlayer;
    const pp = PER_PLAYER[p];
    const col = COLORS[p]||'#9ca3af';

    if (pp.nemesis) {
      const n=pp.nemesis;
      cards.push(insightCard('alert','Your Nemesis',n.p,`${n.l}W–${n.w}L–${n.t}T`,`${n.p} beats you ${Math.round(n.l/n.tot*100)}% of the time`,'var(--red)'));
    }
    if (pp.prey) {
      const n=pp.prey;
      cards.push(insightCard('target','Hunting Ground',n.p,`${n.w}W–${n.l}L–${n.t}T`,`You beat ${n.p} ${Math.round(n.w/n.tot*100)}% of the time`,'var(--green)'));
    }
    const crank = courseRank(p);
    cards.push(insightCard('map','Course Explorer',`${pp.unique_courses} courses`,`#${crank} in the group`,`Played ${pp.unique_courses} unique courses on the simulator`,col));
    cards.push(insightCard('target','Consistency',`Grade ${pp.grade}`,pp.glabel,pp.std18!=null?`σ = ${pp.std18} strokes`:'Not enough data',col));
    if (pp.last_vs_baseline!=null) cards.push(insightCard('ruler','Vs Personal Baseline',`${pp.last_vs_baseline>0?'+':''}${fmt1(pp.last_vs_baseline)}`,`Last round vs prior 10-round avg`,pp.last_vs_baseline<0?'Better than baseline':'Above baseline',pp.last_vs_baseline<0?'var(--green)':'var(--gold)'));
    if (pp.blowup_recent18!=null) cards.push(insightCard('shield','Blow-up Rate',`${fmt1(pp.blowup_recent18)} / rd`,`Double bogeys or worse, last 5 rounds`,`Season avg ${fmt1(pp.blowup_avg18)} per round`,col));
    if (pp.birdies_recent18!=null) cards.push(insightCard('dove','Birdie+ Trend',`${fmt1(pp.birdies_recent18)} / rd`,`Birdies plus eagles, last 5 rounds`,pp.birdies_prior18!=null?`Prior avg ${fmt1(pp.birdies_prior18)} per round`:'',col));
    if (pp.sim_index!=null) cards.push(insightCard('ruler','Simulator Index',fmt1(pp.sim_index),`Handicap-style estimate`,`Uses rating/slope data; not official`,col));
    if (pp.peak) cards.push(insightCard('trophy','Peak Form Window',`${pp.peak.avg} avg`,`Best 5-round stretch`,`Ending ${pp.peak.end}`,col));
    if (pp.form_label) cards.push(insightCard('trend','Current Form',pp.form_label,`${pp.form_diff>0?'+':''}${fmt1(pp.form_diff)} strokes`,`vs season average (last 5 rounds, 18H)`,pp.form_diff>0?'var(--green)':'var(--red)'));
    if (pp.solo_avg18!=null&&pp.group_avg18!=null) {
      const diff = pp.group_avg18-pp.solo_avg18;
      cards.push(insightCard('group','Group Effect',`${diff>0?'+':''}${fmt1(diff)} strokes`,diff>0?'You play worse with others':'You play better with others',`Solo ${fmt1(pp.solo_avg18)} (${pp.solo_count18} rds) vs group ${fmt1(pp.group_avg18)} (${pp.group_count18} rds)`,diff<0?'var(--green)':'var(--gold)'));
    }
    if (pp.velocity!=null) {
      const v=pp.velocity, improving=v<-0.05;
      cards.push(insightCard(improving?'rocket':'trend','Scoring Velocity',`${Math.abs(v).toFixed(2)} strokes/rd`,improving?'Improving trend':'Trending higher',`Slope of last 20 18H rounds`,improving?'var(--green)':'var(--red)'));
    }
    cards.push(insightCard('swords','H2H Record',`${pp.win_rate}%`,`Win rate across matchups`,`${pp.total_games} competitive rounds`,'var(--accent)'));
    cards.push(insightCard('spark','Playing Archetype',pp.archetype[1],'Based on FIR, GIR & scoring','Relative to group median values',col));
  }

  el.innerHTML = cards.join('');
}

function insightCard(icon, label, main, sub, extra, color='var(--accent)') {
  if (!main) return '';
  const safeColor = color.startsWith('#') ? color : color;
  const isHex = color.startsWith('#');
  const borderTint = isHex ? hexAlpha(color, 0.30) : 'var(--line-hi)';
  return `<div class="panel insight-card" style="border-color:${borderTint}">
    <div class="ic-tag">
      <span class="ic-mark" style="color:${safeColor};background: color-mix(in srgb, ${safeColor} 14%, transparent);">${svgIcon(icon)}</span>
      <span>${label}</span>
    </div>
    <div class="ic-main" style="color:${safeColor}">${main}</div>
    <div class="ic-sub">${sub}</div>
    ${extra?`<div class="ic-extra">${extra}</div>`:''}
  </div>`;
}

// ── Course chart ──────────────────────────────────────────────────────────────
function getCourseData() {
  const filtered = activePlayer==='all' ? ROUNDS : ROUNDS.filter(r=>r.player===activePlayer);
  const counts = {};
  for (const r of filtered) {
    if (r.course) counts[r.course] = (counts[r.course]||0)+1;
  }
  const sorted = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,12);
  return { labels: sorted.map(x=>x[0]), data: sorted.map(x=>x[1]) };
}

function initCourseChart() {
  const {labels, data} = getCourseData();
  const ctx = document.getElementById('courseChart').getContext('2d');
  const col = activePlayer==='all'?'#22c55e':COLORS[activePlayer]||'#22c55e';
  courseChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets:[{ label:'Rounds', data, backgroundColor: labels.map((_,i)=>hexAlpha(col, 0.5+i/labels.length*0.5)), borderRadius:6, borderSkipped:false }]
    },
    options: {
      indexAxis:'y', responsive:true, maintainAspectRatio:true,
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{label:c=>` ${c.parsed.x} rounds`} } },
      scales:{
        x:{ ticks:{color:CHART_AXIS,font:{size:10}}, grid:{color:CHART_GRID} },
        y:{ ticks:{color:CHART_LABEL,font:{size:10}}, grid:{display:false} }
      }
    }
  });
}

function updateCourseChart() {
  if (!courseChart) return;
  const {labels, data} = getCourseData();
  const col = activePlayer==='all'?'#22c55e':COLORS[activePlayer]||'#22c55e';
  courseChart.data.labels = labels;
  courseChart.data.datasets[0].data = data;
  courseChart.data.datasets[0].backgroundColor = labels.map((_,i)=>hexAlpha(col, 0.4+i/labels.length*0.45));
  courseChart.update('none');
}

// ── Distribution chart ────────────────────────────────────────────────────────
const DIST_BUCKETS = ['<80','80-84','85-89','90-94','95-99','100+'];
const DIST_COLORS  = ['#22c55e','#84cc16','#f59e0b','#f97316','#ef4444','#991b1b'];

function getDistData() {
  const players = rankedPlayers();
  return players.map(p => ({
    label: p,
    data: DIST_BUCKETS.map(b=>PER_PLAYER[p].score_dist[b]||0),
    backgroundColor: hexAlpha(COLORS[p]||'#9ca3af', 0.7),
    borderRadius: 4,
  }));
}

function initDistChart() {
  const ctx = document.getElementById('distChart').getContext('2d');
  distChart = new Chart(ctx, {
    type: 'bar',
    data: { labels: DIST_BUCKETS, datasets: getDistData() },
    options: {
      responsive:true, maintainAspectRatio:true,
      plugins:{ legend:{ display: activePlayer==='all', position:'bottom', labels:{color:CHART_LABEL,boxWidth:12,font:{size:10}} } },
      scales:{
        x:{ ticks:{color:CHART_AXIS,font:{size:10}}, grid:{display:false} },
        y:{ ticks:{color:CHART_AXIS,font:{size:10}}, grid:{color:CHART_GRID}, title:{display:true,text:'Rounds',color:CHART_AXIS,font:{size:10}} }
      }
    }
  });
}

function updateDistChart() {
  if (!distChart) return;
  distChart.data.datasets = getDistData();
  distChart.options.plugins.legend.display = activePlayer==='all';
  distChart.update('none');
}

// ── Volume (activity timeline) ────────────────────────────────────────────────
function buildVolumeDatasets() {
  const players = rankedPlayers();
  return players.map(p=>({
    label: p,
    data: MONTHLY.by_player[p]||[],
    backgroundColor: hexAlpha(COLORS[p]||'#9ca3af', 0.75),
    borderRadius: 3,
    stack: 'rounds',
  }));
}

function initVolumeChart() {
  const ctx = document.getElementById('volumeChart').getContext('2d');
  volumeChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: MONTHLY.months,
      datasets: buildVolumeDatasets(),
    },
    options: {
      responsive:true, maintainAspectRatio:true,
      plugins:{ legend:{ display:activePlayer==='all', position:'bottom', labels:{color:CHART_LABEL,boxWidth:12,font:{size:10}} } },
      scales:{
        x:{ stacked:true, ticks:{color:CHART_AXIS,font:{size:10}}, grid:{display:false} },
        y:{ stacked:true, ticks:{color:CHART_AXIS,font:{size:10},stepSize:1}, grid:{color:CHART_GRID}, title:{display:true,text:'Rounds',color:CHART_AXIS,font:{size:10}} }
      }
    }
  });
}

function updateVolumeChart() {
  if (!volumeChart) return;
  volumeChart.data.datasets = buildVolumeDatasets();
  volumeChart.options.plugins.legend.display = activePlayer==='all';
  volumeChart.update('none');
}
</script>
</body>
</html>"""

TEMPLATE = TEMPLATE.replace('__ROUNDS__',      ROUNDS_J)
TEMPLATE = TEMPLATE.replace('__PLAYERS__',     PLAYERS_J)
TEMPLATE = TEMPLATE.replace('__COLORS__',      COLORS_J)
TEMPLATE = TEMPLATE.replace('__PERP__',        PERP_J)
TEMPLATE = TEMPLATE.replace('__H2H__',         H2H_J)
TEMPLATE = TEMPLATE.replace('__COURSES__',     COURSES_J)
TEMPLATE = TEMPLATE.replace('__MONTHLY__',     MONTHLY_J)
TEMPLATE = TEMPLATE.replace('__GENERATED__',   GENERATED)
TEMPLATE = TEMPLATE.replace('__ROUND_COUNT__', str(len(rounds)))
TEMPLATE = TEMPLATE.replace('__PLAYER_COUNT__',str(len(PLAYERS)))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(TEMPLATE)

size_kb = os.path.getsize(OUT) // 1024
print(f'✓ index.html → {size_kb} KB')
