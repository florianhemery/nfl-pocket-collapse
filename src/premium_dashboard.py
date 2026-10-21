"""Generate the 2026 premium static HTML dashboard."""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

DATA_DIR   = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

def build_premium_dashboard(dss_csv: str, output_path: str) -> str:
    df = pd.read_csv(dss_csv)

    # ── Precompute data blobs ─────────────────────────────────────────
    # Team ranking
    team_agg = (df.groupby("defensiveTeam")["dss"]
                .agg(["mean","std","count"]).reset_index()
                .query("count >= 5")
                .sort_values("mean", ascending=False))
    team_agg.columns = ["team","mean","std","count"]

    # Man vs Zone scatter
    scatter = {}
    for ct in ["Man","Zone"]:
        sub = df[df["coverageType"]==ct]
        if len(sub) < 10: continue
        binned = (sub.groupby(pd.cut(sub["dss"], bins=12))
                  .agg(dss=("dss","mean"), comp=("completed","mean"), n=("completed","count"))
                  .reset_index(drop=True).dropna())
        binned = binned[binned["n"] >= 5]
        scatter[ct] = {"dss": binned["dss"].tolist(),
                       "comp": (binned["comp"]*100).tolist(),
                       "n": binned["n"].tolist()}

    # DSS distribution by coverage
    box = {}
    for ct in df["coverageType"].dropna().unique():
        vals = df[df["coverageType"]==ct]["dss"].dropna().tolist()
        if len(vals) > 5:
            box[ct] = {"median": float(np.median(vals)),
                       "q1": float(np.percentile(vals,25)),
                       "q3": float(np.percentile(vals,75)),
                       "min": float(np.percentile(vals,5)),
                       "max": float(np.percentile(vals,95)),
                       "mean": float(np.mean(vals))}

    # Heatmap
    pivot = df.pivot_table(values="dss", index="coverage", columns="down", aggfunc="mean")
    heatmap_rows = pivot.index.tolist()
    heatmap_cols = [int(c) for c in pivot.columns]
    heatmap_vals = [[round(pivot.loc[r,c],1) if not np.isnan(pivot.loc[r,c]) else None
                     for c in pivot.columns] for r in pivot.index]

    # Sub-scores top 5
    top5 = team_agg.head(5)["team"].tolist()
    sub_data = (df[df["defensiveTeam"].isin(top5)]
                .groupby("defensiveTeam")[["va","sd","od","dss"]]
                .mean().round(1).reset_index())
    sub_json = sub_data.to_dict(orient="records")

    # KPIs
    hi = df[df["dss"] >= df["dss"].median()]
    lo = df[df["dss"] <  df["dss"].median()]
    delta_man = None
    man = df[df["coverageType"]=="Man"]
    if len(man) > 10:
        hi_m = man[man["dss"] >= man["dss"].median()]
        lo_m = man[man["dss"] <  man["dss"].median()]
        delta_man = round((lo_m["completed"].mean() - hi_m["completed"].mean())*100, 1)
    best_team = team_agg.iloc[0]["team"]
    best_dss  = round(team_agg.iloc[0]["mean"], 1)
    worst_team = team_agg.iloc[-1]["team"]
    worst_dss  = round(team_agg.iloc[-1]["mean"], 1)
    overall_delta = round((lo["completed"].mean() - hi["completed"].mean())*100, 1)

    DATA = {
        "teams":      team_agg[["team","mean","std","count"]].round(2).to_dict(orient="records"),
        "scatter":    scatter,
        "box":        box,
        "heatmap":    {"rows": heatmap_rows, "cols": heatmap_cols, "vals": heatmap_vals},
        "subscores":  sub_json,
        "kpis": {
            "plays": len(df),
            "mean_dss": round(df["dss"].mean(),1),
            "best_team": best_team, "best_dss": best_dss,
            "worst_team": worst_team, "worst_dss": worst_dss,
            "delta_pp": overall_delta,
            "delta_man": delta_man,
        },
    }

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(DATA))
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DSS · NFL Secondary Analytics</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg:       #F4F7FE;
  --surface:  #FFFFFF;
  --border:   #E8EDF8;
  --nav:      #0F172A;
  --text:     #0F172A;
  --muted:    #64748B;
  --accent:   #3B82F6;
  --accent2:  #6366F1;
  --green:    #10B981;
  --amber:    #F59E0B;
  --red:      #EF4444;
  --gold:     #F59E0B;
  --man-c:    #EF4444;
  --zone-c:   #3B82F6;
  --radius:   16px;
  --shadow:   0 1px 3px rgba(15,23,42,.06), 0 8px 24px rgba(15,23,42,.05);
  --font:     'Inter', system-ui, sans-serif;
  --mono:     'JetBrains Mono', 'Fira Code', monospace;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body { background: var(--bg); color: var(--text); font-family: var(--font);
       font-size: 14px; line-height: 1.6; min-height: 100vh; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }

/* ── Nav ── */
nav {
  background: var(--nav);
  height: 60px; display: flex; align-items: center;
  padding: 0 36px; gap: 14px;
  position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 16px rgba(0,0,0,.25);
}
nav .logo { font-size: 22px; }
nav .title { color: white; font-weight: 800; font-size: 15px; letter-spacing: -.01em; flex:1; }
nav .title span { color: #94A3B8; font-weight: 400; font-size: 13px; }
.nav-badge {
  background: rgba(255,255,255,.08); color: #CBD5E1;
  font-size: 11px; font-weight: 600; padding: 4px 10px;
  border-radius: 99px; border: 1px solid rgba(255,255,255,.12);
  letter-spacing: .03em;
}

/* ── Layout ── */
.wrapper { max-width: 1520px; margin: 0 auto; padding: 36px 32px 56px; }

/* ── Page header ── */
.page-header { margin-bottom: 32px; }
.page-header h1 {
  font-size: 30px; font-weight: 900; letter-spacing: -.03em;
  background: linear-gradient(135deg, #0F172A 0%, #3B82F6 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text; margin-bottom: 8px;
}
.page-header p { color: var(--muted); font-size: 14px; max-width: 680px; line-height: 1.7; }

/* ── Card ── */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px;
  box-shadow: var(--shadow);
}
.card-title { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 2px; }
.card-sub   { font-size: 12px; color: var(--muted); margin-bottom: 18px; }

/* ── KPI row ── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px; margin-bottom: 24px;
}
.kpi-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px 22px;
  box-shadow: var(--shadow);
  position: relative; overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: var(--kpi-color, var(--accent));
  border-radius: var(--radius) var(--radius) 0 0;
}
.kpi-card .kpi-label {
  font-size: 10px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 10px;
}
.kpi-card .kpi-value {
  font-size: 32px; font-weight: 900; letter-spacing: -.02em;
  color: var(--kpi-color, var(--accent)); line-height: 1;
}
.kpi-card .kpi-delta {
  font-size: 12px; font-weight: 700; margin-left: 6px; vertical-align: middle;
}
.kpi-card .kpi-sub { font-size: 11px; color: var(--muted); margin-top: 6px; }

/* ── Grid layouts ── */
.grid-2-3  { display: grid; grid-template-columns: 2fr 3fr; gap: 20px; margin-bottom: 20px; }
.grid-1-2  { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-bottom: 20px; }
.grid-2    { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.grid-3-2  { display: grid; grid-template-columns: 3fr 2fr; gap: 20px; margin-bottom: 20px; }

/* ── Chart wrapper ── */
.chart-wrap { position: relative; width: 100%; }

/* ── Heatmap table ── */
.heatmap-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.heatmap-table th {
  background: var(--bg); color: var(--muted); font-weight: 600;
  font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  padding: 8px 12px; text-align: center; border: 1px solid var(--border);
}
.heatmap-table td {
  padding: 9px 12px; text-align: center; font-weight: 700; font-size: 13px;
  border: 1px solid var(--border);
  transition: opacity .15s;
}
.heatmap-table tr:hover td { opacity: .8; }

/* ── Legend pill ── */
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--pill-bg, #EFF6FF); color: var(--pill-color, var(--accent));
  font-size: 11px; font-weight: 600; padding: 4px 10px;
  border-radius: 99px;
}
.pill-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

/* ── Insight cards ── */
.insight { border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
.insight .ins-label { font-size: 12px; font-weight: 700; margin-bottom: 4px; }
.insight .ins-text  { font-size: 12px; color: var(--muted); line-height: 1.55; }

/* ── Ranking bars ── */
.rank-bar-row {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 8px; font-size: 12px;
}
.rank-team  { width: 36px; font-weight: 700; color: var(--text); text-align: right; flex-shrink: 0; }
.rank-track { flex: 1; height: 22px; background: var(--bg);
              border-radius: 99px; overflow: hidden; position: relative; }
.rank-fill  { height: 100%; border-radius: 99px;
              display: flex; align-items: center; justify-content: flex-end;
              padding-right: 8px; font-size: 11px; font-weight: 700;
              color: white; transition: width .6s cubic-bezier(.4,0,.2,1); }
.rank-val   { width: 34px; text-align: right; color: var(--muted); font-weight: 600; flex-shrink: 0; }

/* ── Code block ── */
.code-block {
  font-family: var(--mono); font-size: 12px;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 14px; color: var(--accent2);
  margin-top: 8px;
}

/* ── Footer ── */
footer { text-align: center; color: var(--muted); font-size: 11px; padding: 12px 0 4px; }

/* ── Responsive ── */
@media (max-width: 1100px) {
  .kpi-grid   { grid-template-columns: repeat(3, 1fr); }
  .grid-2-3, .grid-1-2, .grid-3-2 { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .grid-2   { grid-template-columns: 1fr; }
  .wrapper  { padding: 20px 16px; }
}
</style>
</head>
<body>

<nav>
  <span class="logo">🏈</span>
  <div class="title">
    Defensive Sync Score
    <span>&nbsp;·&nbsp; NFL 2021 Season</span>
  </div>
  <span class="nav-badge">122 games</span>
  <span class="nav-badge">7,510 plays</span>
  <span class="nav-badge">32 teams</span>
</nav>

<div class="wrapper">

  <!-- Page header -->
  <div class="page-header">
    <h1>Secondary Synchronization Dashboard</h1>
    <p>How well does a defensive secondary move as a coordinated unit? DSS quantifies velocity alignment, spacing discipline and orientation divergence — frame by frame, from snap to pass release.</p>
  </div>

  <!-- KPIs -->
  <div class="kpi-grid" id="kpi-grid"></div>

  <!-- Row 1: Ranking + Scatter -->
  <div class="grid-2-3">
    <div class="card">
      <div class="card-title">Team Ranking</div>
      <div class="card-sub">Higher DSS = more synchronized secondary</div>
      <div id="ranking-bars"></div>
    </div>
    <div class="card">
      <div class="card-title">DSS vs Pass Completion Rate</div>
      <div class="card-sub">More sync → fewer completions. Bubble size = play count.</div>
      <div class="chart-wrap" style="height:490px">
        <canvas id="chart-scatter"></canvas>
      </div>
    </div>
  </div>

  <!-- Row 2: Box + Heatmap -->
  <div class="grid-2">
    <div class="card">
      <div class="card-title">DSS Distribution by Coverage Type</div>
      <div class="card-sub">Man coverage is the hardest to synchronize</div>
      <div class="chart-wrap" style="height:300px">
        <canvas id="chart-box"></canvas>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Coverage Scheme × Down Heatmap</div>
      <div class="card-sub">Red = low sync · Green = well-coordinated secondary</div>
      <div style="overflow-x:auto">
        <table class="heatmap-table" id="heatmap-table"></table>
      </div>
    </div>
  </div>

  <!-- Row 3: Sub-scores + Explanation -->
  <div class="grid-3-2">
    <div class="card">
      <div class="card-title">Sub-score Breakdown — Top 5 Teams</div>
      <div class="card-sub">VA · SD · OD individually for the best-ranked defenses</div>
      <div class="chart-wrap" style="height:300px">
        <canvas id="chart-sub"></canvas>
      </div>
    </div>
    <div class="card">
      <div class="card-title">How to Read DSS</div>
      <div style="margin-top:12px">
        <div class="insight" style="background:#EFF6FF;border-left:3px solid #3B82F6">
          <div class="ins-label" style="color:#3B82F6">VA — Velocity Alignment (40%)</div>
          <div class="ins-text">Do DBs move in the same direction post-snap? Measured as cosine similarity of velocity vectors vs. the group mean.</div>
        </div>
        <div class="insight" style="background:#F5F3FF;border-left:3px solid #6366F1">
          <div class="ins-label" style="color:#6366F1">SD — Spacing Discipline (30%)</div>
          <div class="ins-text">Do they hold their formation width? Low coefficient of variation in pairwise distances = disciplined secondary.</div>
        </div>
        <div class="insight" style="background:#F0FDF4;border-left:3px solid #10B981">
          <div class="ins-label" style="color:#10B981">OD — Orientation Divergence (30%)</div>
          <div class="ins-text">Is each DB tracking his own receiver? Counter-intuitive: divergent gaze scores higher — each DB on his man, not staring at the QB.</div>
        </div>
        <div class="insight" style="background:#FFFBEB;border-left:3px solid #F59E0B">
          <div class="ins-label" style="color:#F59E0B">⚡ Key finding</div>
          <div class="ins-text">In man coverage, high-DSS defenses allow <strong>6.1 pp fewer completions</strong>. The effect persists in zone (3.7 pp). Cover-0 has the lowest DSS (~44) — full man with no safety help is inherently hard to synchronize.</div>
        </div>
        <div class="code-block">DSS = 100 × (0.40·VA + 0.30·SD + 0.30·OD)</div>
      </div>
    </div>
  </div>

  <footer>
    Data: NFL Big Data Bowl 2021 · ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data
    &nbsp;·&nbsp; github.com/florianhemery/nfl-pocket-collapse
  </footer>

</div>

<script>
const DATA = __DATA_JSON__;

// ── Helpers ────────────────────────────────────────────────────────────
function lerp(a,b,t){ return a+(b-a)*t; }
function heatColor(val, lo=42, hi=68){
  if(val===null) return '#F8FAFC';
  const t = Math.max(0, Math.min(1, (val-lo)/(hi-lo)));
  // Red → Amber → Green
  if(t < 0.5){
    const s = t/0.5;
    const r = Math.round(lerp(239,251,s));
    const g = Math.round(lerp( 68,191,s));
    const b = Math.round(lerp( 68, 36,s));
    return `rgb(${r},${g},${b})`;
  } else {
    const s = (t-0.5)/0.5;
    const r = Math.round(lerp(251,22,s));
    const g = Math.round(lerp(191,163,s));
    const b = Math.round(lerp( 36,74,s));
    return `rgb(${r},${g},${b})`;
  }
}
function textOnHeat(val, lo=42,hi=68){
  if(val===null) return '#94A3B8';
  const t = Math.max(0,Math.min(1,(val-lo)/(hi-lo)));
  return t < 0.45 ? '#FFFFFF' : '#0F172A';
}

const CHART_DEFAULTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { labels: { font: { family: 'Inter', size: 12 }, color: '#64748B' } } },
};

// ── KPIs ───────────────────────────────────────────────────────────────
const kpis = [
  { label:'Plays Analyzed',  value: DATA.kpis.plays.toLocaleString(),
    sub:'in the dataset', color:'#3B82F6' },
  { label:'Avg League DSS',  value: DATA.kpis.mean_dss,
    sub:'/ 100 · higher = better sync', color:'#F59E0B' },
  { label:'Best Secondary',  value: DATA.kpis.best_team,
    sub:`DSS ${DATA.kpis.best_dss} / 100`, color:'#10B981' },
  { label:'Sync Effect',     value: DATA.kpis.delta_pp+'pp',
    delta: '−'+DATA.kpis.delta_pp+'pp',
    sub:'completion delta high vs low DSS', color:'#10B981' },
  { label:'Man Coverage Δ', value: (DATA.kpis.delta_man||'N/A')+(DATA.kpis.delta_man?'pp':''),
    sub:'fewer completions with high DSS', color:'#EF4444' },
];
const grid = document.getElementById('kpi-grid');
kpis.forEach(k => {
  grid.innerHTML += `<div class="kpi-card" style="--kpi-color:${k.color}">
    <div class="kpi-label">${k.label}</div>
    <div>
      <span class="kpi-value">${k.value}</span>
    </div>
    <div class="kpi-sub">${k.sub}</div>
  </div>`;
});

// ── Ranking bars ────────────────────────────────────────────────────────
const rankEl = document.getElementById('ranking-bars');
const maxDSS = Math.max(...DATA.teams.map(t=>t.mean));
const minDSS = Math.min(...DATA.teams.map(t=>t.mean));
DATA.teams.forEach((t,i) => {
  const pct = ((t.mean - minDSS) / (maxDSS - minDSS)) * 78 + 20;
  const norm = (t.mean - minDSS) / (maxDSS - minDSS);
  // gradient from red to green
  const r = Math.round(lerp(239,16,norm));
  const g = Math.round(lerp(68,163,norm));
  const b = Math.round(lerp(68,74,norm));
  const color = `rgb(${r},${g},${b})`;
  rankEl.innerHTML += `<div class="rank-bar-row">
    <span class="rank-team">${t.team}</span>
    <div class="rank-track">
      <div class="rank-fill" style="width:${pct}%;background:${color}">${i<5?'▲':''}</div>
    </div>
    <span class="rank-val">${t.mean.toFixed(1)}</span>
  </div>`;
});

// ── Scatter ────────────────────────────────────────────────────────────
new Chart(document.getElementById('chart-scatter'), {
  type: 'bubble',
  data: {
    datasets: [
      DATA.scatter['Man'] ? {
        label: 'Man Coverage',
        data: DATA.scatter['Man'].dss.map((x,i)=>({
          x, y: DATA.scatter['Man'].comp[i], r: Math.max(4, DATA.scatter['Man'].n[i]/20+4)
        })),
        backgroundColor: 'rgba(239,68,68,0.25)',
        borderColor: '#EF4444', borderWidth: 2,
      } : null,
      DATA.scatter['Zone'] ? {
        label: 'Zone Coverage',
        data: DATA.scatter['Zone'].dss.map((x,i)=>({
          x, y: DATA.scatter['Zone'].comp[i], r: Math.max(4, DATA.scatter['Zone'].n[i]/20+4)
        })),
        backgroundColor: 'rgba(59,130,246,0.2)',
        borderColor: '#3B82F6', borderWidth: 2,
      } : null,
    ].filter(Boolean),
  },
  options: {
    ...CHART_DEFAULTS,
    scales: {
      x: { title: { display:true, text:'Defensive Sync Score (binned)', color:'#64748B', font:{size:12} },
           grid: { color:'#F1F5F9' }, ticks: { color:'#94A3B8' } },
      y: { title: { display:true, text:'Completion Rate (%)', color:'#64748B', font:{size:12} },
           grid: { color:'#F1F5F9' }, ticks: { color:'#94A3B8',
             callback: v => v.toFixed(0)+'%' } },
    },
    plugins: {
      ...CHART_DEFAULTS.plugins,
      tooltip: { callbacks: {
        label: ctx => `${ctx.dataset.label}: DSS ${ctx.raw.x.toFixed(1)} · Comp ${ctx.raw.y.toFixed(1)}%`
      }},
    },
  },
});

// ── Box / bar chart ─────────────────────────────────────────────────────
const boxLabels = Object.keys(DATA.box);
const boxColors = { Man:'rgba(239,68,68,.7)', Zone:'rgba(59,130,246,.7)', Other:'rgba(99,102,241,.7)' };
new Chart(document.getElementById('chart-box'), {
  type: 'bar',
  data: {
    labels: ['Q1–Q3 range', 'Median', 'Mean'],
    datasets: boxLabels.map(ct => ({
      label: ct,
      data: [DATA.box[ct].q3-DATA.box[ct].q1, DATA.box[ct].median, DATA.box[ct].mean],
      backgroundColor: boxColors[ct] || 'rgba(148,163,184,.6)',
      borderRadius: 6, borderSkipped: false,
    })),
  },
  options: {
    ...CHART_DEFAULTS,
    scales: {
      x: { grid:{color:'#F1F5F9'}, ticks:{color:'#94A3B8'} },
      y: { title:{display:true,text:'DSS',color:'#64748B',font:{size:12}},
           grid:{color:'#F1F5F9'}, ticks:{color:'#94A3B8'} },
    },
  },
});

// ── Heatmap table ────────────────────────────────────────────────────────
const table = document.getElementById('heatmap-table');
let thead = '<thead><tr><th>Coverage</th>';
DATA.heatmap.cols.forEach(c => thead += `<th>Down ${c}</th>`);
thead += '</tr></thead>';
let tbody = '<tbody>';
DATA.heatmap.rows.forEach((row,i) => {
  tbody += `<tr><td style="text-align:left;font-weight:600;color:var(--text);background:var(--bg)">${row}</td>`;
  DATA.heatmap.cols.forEach((_,j) => {
    const v = DATA.heatmap.vals[i][j];
    const bg = heatColor(v);
    const fg = textOnHeat(v);
    tbody += `<td style="background:${bg};color:${fg}">${v !== null ? v : '—'}</td>`;
  });
  tbody += '</tr>';
});
tbody += '</tbody>';
table.innerHTML = thead + tbody;

// ── Sub-scores grouped bar ───────────────────────────────────────────────
const subLabels = ['Velocity Align (VA)', 'Spacing Discipline (SD)', 'Orient. Divergence (OD)', 'DSS'];
const subColors = ['#3B82F6','#6366F1','#10B981','#F59E0B','#EF4444'];
new Chart(document.getElementById('chart-sub'), {
  type: 'bar',
  data: {
    labels: subLabels,
    datasets: DATA.subscores.map((d,i)=>({
      label: d.defensiveTeam,
      data: [d.va, d.sd, d.od, d.dss],
      backgroundColor: subColors[i]+'CC',
      borderRadius: 5, borderSkipped: false,
    })),
  },
  options: {
    ...CHART_DEFAULTS,
    scales: {
      x: { grid:{color:'#F1F5F9'}, ticks:{color:'#94A3B8',font:{size:11}} },
      y: { min:0, max:100, title:{display:true,text:'Score (0–100)',color:'#64748B',font:{size:12}},
           grid:{color:'#F1F5F9'}, ticks:{color:'#94A3B8'} },
    },
    plugins: {
      ...CHART_DEFAULTS.plugins,
      legend: { position:'top', labels:{...CHART_DEFAULTS.plugins.legend.labels, boxWidth:12, padding:16} },
    },
  },
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    out = build_premium_dashboard(
        str(OUTPUT_DIR / "dss_results.csv"),
        str(OUTPUT_DIR / "dss_premium.html"),
    )
    print(f"Premium dashboard: {out}")
    import os; print(f"Size: {os.path.getsize(out)//1024} KB")
