"""DSS Pro Dashboard — Modern Light Theme.

Run: .venv/bin/python3 src/app.py  →  http://127.0.0.1:8050
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, html, dcc, Input, Output

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

df = pd.read_csv(OUTPUT_DIR / "dss_results.csv")
players_df = pd.read_csv(DATA_DIR / "players.csv")

ALL_TEAMS  = sorted(df["defensiveTeam"].dropna().unique())
COV_TYPES  = sorted(df["coverageType"].dropna().unique())
COV_NAMES  = sorted(df["coverage"].dropna().unique())

# ── Design tokens (superdesign.dev "Modern Professional") ──────────────
BG       = "#F0F4F8"      # page background
SURFACE  = "#FFFFFF"      # card surface
BORDER   = "#E2E8F0"      # card border
NAV_BG   = "#1E3A5F"      # top nav — NFL navy
TEXT     = "#1A202C"      # primary text
MUTED    = "#718096"      # secondary text
ACCENT   = "#2563EB"      # brand blue
GREEN    = "#16A34A"      # success
AMBER    = "#D97706"      # warning
RED      = "#DC2626"      # danger
GOLD     = "#B45309"      # gold / rank
FONT     = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# coverage palette — distinct, accessible
COV_COLORS = {"Man": "#EF4444", "Zone": "#2563EB", "Other": "#7C3AED"}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family=FONT, size=12),
    margin=dict(t=8, b=44, l=54, r=20),
    xaxis=dict(gridcolor="#EDF2F7", zerolinecolor="#CBD5E0", linecolor=BORDER,
               tickfont=dict(color=MUTED, size=11)),
    yaxis=dict(gridcolor="#EDF2F7", zerolinecolor="#CBD5E0", linecolor=BORDER,
               tickfont=dict(color=MUTED, size=11)),
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER,
                    font_color=TEXT, font_family=FONT),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER,
                font=dict(size=12, color=TEXT)),
)

# ── App ────────────────────────────────────────────────────────────────
app = Dash(__name__, title="DSS · NFL Secondary Analytics")

app.index_string = f"""<!DOCTYPE html>
<html>
<head>
  {{%metas%}}
  <title>{{%title%}}</title>
  {{%favicon%}}
  {{%css%}}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {BG}; color: {TEXT}; font-family: {FONT}; }}
    ::-webkit-scrollbar {{ width: 6px; background: {BG}; }}
    ::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}

    /* Dash dropdown overrides */
    .Select-control {{
      background: {SURFACE} !important;
      border: 1px solid {BORDER} !important;
      border-radius: 8px !important;
      min-height: 36px !important;
    }}
    .Select-control:hover {{ border-color: {ACCENT} !important; }}
    .Select-menu-outer {{ background: {SURFACE} !important; border: 1px solid {BORDER} !important;
                          border-radius: 8px !important; box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important; }}
    .Select-option {{ color: {TEXT} !important; padding: 8px 12px !important; font-size: 13px; }}
    .Select-option:hover, .Select-option.is-focused {{ background: #EBF2FF !important; color: {ACCENT} !important; }}
    .Select-option.is-selected {{ background: #DBEAFE !important; color: {ACCENT} !important; font-weight: 600; }}
    .Select-value-label {{ color: {TEXT} !important; font-size: 13px !important; }}
    .Select-placeholder {{ color: {MUTED} !important; font-size: 13px !important; }}
    .Select-arrow-zone {{ padding-right: 8px !important; }}

    /* Slider */
    .rc-slider-track {{ background: {ACCENT} !important; }}
    .rc-slider-handle {{ border-color: {ACCENT} !important; background: white !important;
                         box-shadow: 0 1px 4px rgba(37,99,235,0.3) !important; width: 16px; height: 16px; margin-top: -6px; }}
    .rc-slider-rail {{ background: {BORDER} !important; height: 4px; }}
    .rc-slider-dot-active {{ border-color: {ACCENT} !important; }}
    .rc-slider-mark-text {{ color: {MUTED} !important; font-size: 11px !important; }}

    /* Checklist */
    input[type="checkbox"] {{ accent-color: {ACCENT}; }}
  </style>
</head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer></body>
</html>"""

def card(children, style=None, padding="24px"):
    base = dict(
        background=SURFACE,
        border=f"1px solid {BORDER}",
        borderRadius="16px",
        padding=padding,
        boxShadow="0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04)",
    )
    if style:
        base.update(style)
    return html.Div(style=base, children=children)

def badge(text, color=ACCENT):
    return html.Span(text, style=dict(
        background=color + "18", color=color,
        fontSize="11px", fontWeight="600",
        padding="2px 8px", borderRadius="20px",
        letterSpacing="0.03em",
    ))

def section_title(title, subtitle=""):
    return html.Div(style=dict(marginBottom="16px"), children=[
        html.H3(title, style=dict(fontSize="15px", fontWeight="700",
                                   color=TEXT, margin="0 0 2px 0")),
        html.P(subtitle, style=dict(fontSize="12px", color=MUTED, margin="0"))
        if subtitle else None,
    ])

def kpi(title, value, delta=None, sub="", color=ACCENT, border_color=None):
    return html.Div(style=dict(
        background=SURFACE, border=f"1px solid {BORDER}",
        borderRadius="16px", padding="20px 24px",
        boxShadow="0 1px 3px rgba(0,0,0,0.06)",
        borderLeft=f"4px solid {border_color or color}",
        flex="1", minWidth="150px",
    ), children=[
        html.P(title.upper(), style=dict(
            fontSize="10px", fontWeight="700", letterSpacing="0.08em",
            color=MUTED, margin="0 0 10px 0",
        )),
        html.Div(style=dict(display="flex", alignItems="baseline", gap="8px"), children=[
            html.Span(value, style=dict(fontSize="28px", fontWeight="800", color=color, lineHeight="1")),
            html.Span(delta or "", style=dict(
                fontSize="12px", fontWeight="600",
                color=GREEN if delta and delta.startswith("−") else (RED if delta else MUTED),
            )),
        ]),
        html.P(sub, style=dict(fontSize="11px", color=MUTED, margin="6px 0 0 0"))
        if sub else None,
    ])

# ── Layout ─────────────────────────────────────────────────────────────
app.layout = html.Div(style=dict(background=BG, minHeight="100vh", fontFamily=FONT), children=[

    # ── Nav ────────────────────────────────────────────────────────────
    html.Div(style=dict(
        background=NAV_BG, height="60px",
        display="flex", alignItems="center",
        padding="0 40px", gap="16px",
        boxShadow="0 2px 8px rgba(0,0,0,0.15)",
    ), children=[
        html.Span("🏈", style=dict(fontSize="22px")),
        html.Div(children=[
            html.Span("Defensive Sync Score", style=dict(
                color="white", fontWeight="800", fontSize="16px", letterSpacing="-0.01em",
            )),
            html.Span("  ·  NFL 2021 Season", style=dict(color="#94A3B8", fontSize="13px")),
        ], style=dict(flex="1")),
        html.Div(style=dict(display="flex", gap="8px"), children=[
            badge("122 games", "#60A5FA"),
            badge("7,510 plays", "#34D399"),
            badge("32 teams", "#FBBF24"),
        ]),
    ]),

    html.Div(style=dict(maxWidth="1560px", margin="0 auto", padding="32px 32px 48px"), children=[

        # ── Page title ─────────────────────────────────────────────────
        html.Div(style=dict(marginBottom="28px"), children=[
            html.H1("Secondary Synchronization Dashboard",
                    style=dict(fontSize="26px", fontWeight="800",
                               color=TEXT, margin="0 0 6px 0", letterSpacing="-0.02em")),
            html.P(
                "How well does a defensive secondary move as a coordinated unit? "
                "DSS measures velocity alignment, spacing discipline and orientation divergence — "
                "frame by frame, snap to pass release.",
                style=dict(fontSize="14px", color=MUTED, maxWidth="720px", lineHeight="1.6"),
            ),
        ]),

        # ── Filters ────────────────────────────────────────────────────
        card(style=dict(marginBottom="24px"), padding="18px 24px", children=[
            html.Div(style=dict(display="flex", gap="28px", flexWrap="wrap", alignItems="flex-end"), children=[
                html.Div(children=[
                    html.P("Coverage Type", style=dict(fontSize="11px", fontWeight="600",
                                                        color=MUTED, letterSpacing="0.06em",
                                                        textTransform="uppercase", marginBottom="8px")),
                    dcc.Checklist(id="f-cov",
                        options=[{"label": f"  {c}", "value": c} for c in COV_TYPES],
                        value=COV_TYPES, inline=True,
                        inputStyle=dict(marginRight="5px", accentColor=ACCENT, width="14px", height="14px"),
                        labelStyle=dict(color=TEXT, fontSize="13px", marginRight="20px", cursor="pointer"),
                    ),
                ]),
                html.Div(style=dict(minWidth="230px"), children=[
                    html.P("Down", style=dict(fontSize="11px", fontWeight="600",
                                              color=MUTED, letterSpacing="0.06em",
                                              textTransform="uppercase", marginBottom="10px")),
                    dcc.RangeSlider(id="f-down", min=1, max=4, step=1, value=[1,4],
                        marks={i: {"label": f"{i}▪", "style": {"color": MUTED, "fontSize": "11px"}} for i in range(1,5)},
                        tooltip={"placement":"top", "always_visible": False},
                        updatemode="drag",
                    ),
                ]),
                html.Div(style=dict(minWidth="170px"), children=[
                    html.P("Focus Team", style=dict(fontSize="11px", fontWeight="600",
                                                     color=MUTED, letterSpacing="0.06em",
                                                     textTransform="uppercase", marginBottom="8px")),
                    dcc.Dropdown(id="f-team",
                        options=[{"label": t, "value": t} for t in ALL_TEAMS],
                        value=None, placeholder="All teams", clearable=True,
                        style=dict(fontSize="13px"),
                    ),
                ]),
                html.Div(style=dict(minWidth="190px"), children=[
                    html.P("Coverage Scheme", style=dict(fontSize="11px", fontWeight="600",
                                                          color=MUTED, letterSpacing="0.06em",
                                                          textTransform="uppercase", marginBottom="8px")),
                    dcc.Dropdown(id="f-scheme",
                        options=[{"label": c, "value": c} for c in COV_NAMES],
                        value=None, placeholder="All schemes", clearable=True,
                        style=dict(fontSize="13px"),
                    ),
                ]),
            ]),
        ]),

        # ── KPI strip ──────────────────────────────────────────────────
        html.Div(id="kpis", style=dict(
            display="flex", gap="14px", flexWrap="wrap", marginBottom="24px",
        )),

        # ── Row 1: Ranking + Scatter ────────────────────────────────────
        html.Div(style=dict(display="grid", gridTemplateColumns="1fr 1.5fr",
                            gap="20px", marginBottom="20px"), children=[
            card([
                section_title("Team Ranking", "Higher DSS = more synchronized secondary"),
                dcc.Graph(id="g-rank", style=dict(height="500px"),
                          config=dict(displayModeBar=False)),
            ]),
            card([
                section_title("DSS vs Completion Rate", "Does synchronization actually reduce completions?"),
                dcc.Graph(id="g-scatter", style=dict(height="500px"),
                          config=dict(displayModeBar=False)),
            ]),
        ]),

        # ── Row 2: Box + Heatmap ────────────────────────────────────────
        html.Div(style=dict(display="grid", gridTemplateColumns="1fr 1.7fr",
                            gap="20px", marginBottom="20px"), children=[
            card([
                section_title("DSS Distribution by Coverage", "Man coverage is the hardest to synchronize"),
                dcc.Graph(id="g-box", style=dict(height="360px"),
                          config=dict(displayModeBar=False)),
            ]),
            card([
                section_title("Coverage × Down Heatmap",
                              "Red = low sync → high completion risk · Green = well-coordinated"),
                dcc.Graph(id="g-heat", style=dict(height="360px"),
                          config=dict(displayModeBar=False)),
            ]),
        ]),

        # ── Row 3: Sub-scores + Legend card ────────────────────────────
        html.Div(style=dict(display="grid", gridTemplateColumns="1.8fr 1fr",
                            gap="20px", marginBottom="20px"), children=[
            card([
                section_title("Sub-score Breakdown — Top 5 Teams",
                              "VA · SD · OD breakdown per team (or focused team)"),
                dcc.Graph(id="g-sub", style=dict(height="320px"),
                          config=dict(displayModeBar=False)),
            ]),
            card([
                section_title("How to Read DSS"),
                html.Div(style=dict(display="flex", flexDirection="column", gap="16px"), children=[
                    html.Div(style=dict(
                        background="#EFF6FF", borderRadius="10px", padding="14px 16px",
                        borderLeft=f"3px solid {ACCENT}",
                    ), children=[
                        html.Span("VA — Velocity Alignment", style=dict(color=ACCENT, fontWeight="700", fontSize="13px")),
                        html.P("Do DBs move in the same direction post-snap?",
                               style=dict(color=MUTED, fontSize="12px", margin="4px 0 0 0", lineHeight="1.5")),
                    ]),
                    html.Div(style=dict(
                        background="#F5F3FF", borderRadius="10px", padding="14px 16px",
                        borderLeft="3px solid #7C3AED",
                    ), children=[
                        html.Span("SD — Spacing Discipline", style=dict(color="#7C3AED", fontWeight="700", fontSize="13px")),
                        html.P("Do they maintain their formation width?",
                               style=dict(color=MUTED, fontSize="12px", margin="4px 0 0 0", lineHeight="1.5")),
                    ]),
                    html.Div(style=dict(
                        background="#F0FDF4", borderRadius="10px", padding="14px 16px",
                        borderLeft=f"3px solid {GREEN}",
                    ), children=[
                        html.Span("OD — Orientation Divergence", style=dict(color=GREEN, fontWeight="700", fontSize="13px")),
                        html.P("Is each DB tracking his own receiver? (inverted — divergence is good)",
                               style=dict(color=MUTED, fontSize="12px", margin="4px 0 0 0", lineHeight="1.5")),
                    ]),
                    html.Div(style=dict(
                        background="#FFFBEB", borderRadius="10px", padding="14px 16px",
                        borderLeft=f"3px solid {AMBER}",
                    ), children=[
                        html.Span("⚡ Key insight", style=dict(color=AMBER, fontWeight="700", fontSize="13px")),
                        html.P("DBs staring at the QB (high orientation coherence) let more passes through. "
                               "True coverage means each DB watching his own man.",
                               style=dict(color=MUTED, fontSize="12px", margin="4px 0 0 0", lineHeight="1.5")),
                    ]),
                    html.Div(style=dict(
                        background=BG, borderRadius="8px", padding="10px 14px",
                        fontFamily="'JetBrains Mono', 'Fira Code', monospace",
                        fontSize="12px", color=TEXT, border=f"1px solid {BORDER}",
                    ), children=[
                        html.Span("DSS = 100 × (0.40·VA + 0.30·SD + 0.30·OD)"),
                    ]),
                ]),
            ]),
        ]),

        # ── Footer ─────────────────────────────────────────────────────
        html.P(
            "Data: NFL Big Data Bowl 2021 · ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data · "
            "github.com/florianhemery/nfl-pocket-collapse",
            style=dict(textAlign="center", color=MUTED, fontSize="11px", paddingTop="8px"),
        ),
    ]),
])


# ── Callbacks ─────────────────────────────────────────────────────────
@app.callback(
    Output("kpis",     "children"),
    Output("g-rank",   "figure"),
    Output("g-scatter","figure"),
    Output("g-box",    "figure"),
    Output("g-heat",   "figure"),
    Output("g-sub",    "figure"),
    Input("f-cov",    "value"),
    Input("f-down",   "value"),
    Input("f-team",   "value"),
    Input("f-scheme", "value"),
)
def update(cov_types, down_range, focus_team, scheme):
    if not cov_types:
        cov_types = COV_TYPES

    fdf = df[df["coverageType"].isin(cov_types) & df["down"].between(down_range[0], down_range[1])].copy()
    if scheme:
        fdf = fdf[fdf["coverage"] == scheme]
    focused = fdf[fdf["defensiveTeam"] == focus_team] if focus_team else fdf

    L = PLOT_LAYOUT.copy()

    # ── KPIs ──────────────────────────────────────────────────────────
    n_plays   = len(focused)
    dss_mean  = focused["dss"].mean() if n_plays else 0
    comp_rate = focused["completed"].mean() if n_plays else 0
    hi  = fdf[fdf["dss"] >= fdf["dss"].median()]
    lo  = fdf[fdf["dss"] <  fdf["dss"].median()]
    delta_pp  = (hi["completed"].mean() - lo["completed"].mean()) * 100
    best_team = fdf.groupby("defensiveTeam")["dss"].mean().idxmax() if len(fdf) else "—"
    best_val  = fdf.groupby("defensiveTeam")["dss"].mean().max()    if len(fdf) else 0

    kpis_out = [
        kpi("Plays Analyzed", f"{n_plays:,}", sub="in current filter", color=ACCENT, border_color=ACCENT),
        kpi("Avg DSS", f"{dss_mean:.1f}", sub="/ 100  ·  higher = better", color="#D97706", border_color=AMBER),
        kpi("Completion Rate", f"{comp_rate:.1%}", sub="allowed by defense", color="#7C3AED", border_color="#7C3AED"),
        kpi("Sync Effect",
            f"{abs(delta_pp):.1f} pp",
            delta=f"−{abs(delta_pp):.1f}pp" if delta_pp < 0 else f"+{abs(delta_pp):.1f}pp",
            sub="high vs low DSS delta",
            color=GREEN if delta_pp < 0 else RED,
            border_color=GREEN if delta_pp < 0 else RED),
        kpi("Best Secondary", best_team, sub=f"DSS {best_val:.1f} / 100", color=GREEN, border_color=GREEN),
    ]

    # ── Ranking ──────────────────────────────────────────────────────
    ta = (fdf.groupby("defensiveTeam")["dss"]
          .agg(["mean","std","count"]).reset_index()
          .query("count >= 3")
          .sort_values("mean", ascending=True))

    norm = ((ta["mean"] - ta["mean"].min()) /
            max(ta["mean"].max() - ta["mean"].min(), 0.01))

    bar_colors = [
        ACCENT if (focus_team and r["defensiveTeam"] == focus_team)
        else px.colors.sample_colorscale("RdYlGn", [float(norm.iloc[i])])[0]
        for i, (_, r) in enumerate(ta.iterrows())
    ]

    fig_rank = go.Figure(go.Bar(
        x=ta["mean"], y=ta["defensiveTeam"], orientation="h",
        marker=dict(color=bar_colors, line=dict(color="white", width=0.5),
                    cornerradius=4),
        error_x=dict(type="data", array=ta["std"].tolist(),
                     color="#CBD5E0", thickness=1.5),
        customdata=ta["count"].values,
        hovertemplate="<b>%{y}</b><br>DSS: <b>%{x:.1f}</b><br>n=%{customdata}<extra></extra>",
    ))
    fig_rank.update_layout(**L, showlegend=False, margin=dict(t=8, b=44, l=10, r=90))
    fig_rank.update_xaxes(title_text="Defensive Sync Score", range=[46, 64])
    fig_rank.update_yaxes(tickfont=dict(size=10))

    # ── Scatter ──────────────────────────────────────────────────────
    fig_sc = go.Figure()
    for ct in cov_types:
        sub = fdf[fdf["coverageType"] == ct]
        if len(sub) < 10:
            continue
        binned = (sub.groupby(pd.cut(sub["dss"], bins=10))
                  .agg(dss=("dss","mean"), comp=("completed","mean"), n=("completed","count"))
                  .reset_index(drop=True).dropna())
        binned = binned[binned["n"] >= 5]
        c = COV_COLORS.get(ct, "#888")
        fig_sc.add_trace(go.Scatter(
            x=binned["dss"], y=binned["comp"], mode="markers+lines", name=ct,
            marker=dict(size=binned["n"]/binned["n"].max()*18+8,
                        color=c, opacity=0.85,
                        line=dict(color="white", width=2)),
            line=dict(color=c, width=2.5, dash="dot"),
            hovertemplate=f"<b>{ct}</b><br>DSS: %{{x:.1f}}<br>Completion: %{{y:.1%}}<br>n=%{{text}}<extra></extra>",
            text=binned["n"].astype(str),
        ))

    # Regression annotation
    if len(fdf) > 20:
        b_all = fdf.groupby(pd.cut(fdf["dss"], bins=12)).agg(
            dss=("dss","mean"), comp=("completed","mean"), n=("completed","count")
        ).reset_index(drop=True).dropna()
        b_all = b_all[b_all["n"] >= 5]
        if len(b_all) > 2:
            z = np.polyfit(b_all["dss"], b_all["comp"], 1)
            x_fit = np.linspace(b_all["dss"].min(), b_all["dss"].max(), 80)
            fig_sc.add_trace(go.Scatter(
                x=x_fit, y=np.polyval(z, x_fit),
                mode="lines", name="Overall trend",
                line=dict(color="#94A3B8", width=2, dash="longdash"),
                hoverinfo="skip",
            ))

    fig_sc.update_layout(**L)
    fig_sc.update_xaxes(title_text="Defensive Sync Score (binned)")
    fig_sc.update_yaxes(title_text="Completion Rate", tickformat=".0%")
    fig_sc.add_annotation(
        text="← Higher sync, fewer completions", x=0.02, y=0.97,
        xref="paper", yref="paper", showarrow=False,
        font=dict(color=GREEN, size=11, family=FONT), align="left",
    )

    # ── Violin/Box ───────────────────────────────────────────────────
    fig_box = go.Figure()
    for ct in cov_types:
        sub = fdf[fdf["coverageType"] == ct]
        if len(sub) < 5:
            continue
        c = COV_COLORS.get(ct, "#888")
        fig_box.add_trace(go.Violin(
            y=sub["dss"], name=ct,
            box_visible=True, meanline_visible=True,
            fillcolor=c + "30", line_color=c,
            meanline_color=c, meanline_width=2,
            opacity=0.9,
            hovertemplate=f"<b>{ct}</b><br>DSS: %{{y:.1f}}<extra></extra>",
        ))
    fig_box.update_layout(**L, violingap=0.25)
    fig_box.update_yaxes(title_text="DSS", range=[20, 90])

    # ── Heatmap ──────────────────────────────────────────────────────
    pivot = fdf.pivot_table(values="dss", index="coverage", columns="down", aggfunc="mean")
    annots = []
    for i, row_label in enumerate(pivot.index):
        for j, col in enumerate(pivot.columns):
            val = pivot.loc[row_label, col]
            if not np.isnan(val):
                annots.append(dict(
                    x=f"Down {int(col)}", y=row_label,
                    text=f"<b>{val:.0f}</b>", showarrow=False,
                    font=dict(color="white" if val < 54 else "#1A202C", size=11, family=FONT),
                ))

    fig_hm = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"Down {int(d)}" for d in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[
            [0.0, "#FEE2E2"], [0.25, "#FCA5A5"], [0.4, "#FBBF24"],
            [0.6, "#86EFAC"], [0.8, "#4ADE80"], [1.0, "#16A34A"],
        ],
        zmin=42, zmax=68,
        showscale=True,
        colorbar=dict(
            len=0.85, thickness=14, tickfont=dict(color=MUTED, size=10),
            title=dict(text="DSS", font=dict(color=MUTED, size=11)),
            outlinewidth=0,
        ),
        hovertemplate="<b>%{y}</b> · %{x}<br>DSS: <b>%{z:.1f}</b><extra></extra>",
    ))
    fig_hm.update_layout(**L, margin=dict(t=8, b=44, l=150, r=60), annotations=annots)

    # ── Sub-scores ───────────────────────────────────────────────────
    if focus_team and len(fdf[fdf["defensiveTeam"] == focus_team]) > 0:
        teams_show = [focus_team]
    else:
        teams_show = fdf.groupby("defensiveTeam")["dss"].mean().nlargest(5).index.tolist()

    sub_agg = (fdf[fdf["defensiveTeam"].isin(teams_show)]
               .groupby("defensiveTeam")[["va","sd","od","dss"]]
               .mean().reset_index())

    sub_palette = [ACCENT, "#7C3AED", GREEN, AMBER, "#EF4444"]
    cat_labels  = ["Velocity Alignment (VA)", "Spacing Discipline (SD)",
                   "Orientation Divergence (OD)", "DSS (composite)"]
    fig_sub = go.Figure()
    for i, (_, row) in enumerate(sub_agg.iterrows()):
        c = sub_palette[i % len(sub_palette)]
        fig_sub.add_trace(go.Bar(
            name=row["defensiveTeam"],
            x=cat_labels,
            y=[row["va"], row["sd"], row["od"], row["dss"]],
            marker=dict(color=c, opacity=0.88, line=dict(width=0),
                        cornerradius=4),
            hovertemplate=f"<b>{row['defensiveTeam']}</b><br>%{{x}}: <b>%{{y:.1f}}</b><extra></extra>",
        ))
    fig_sub.update_layout(
        **L, barmode="group",
        yaxis=dict(range=[0, 100], title_text="Score (0–100)",
                   gridcolor="#EDF2F7", zerolinecolor="#CBD5E0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=12)),
    )

    return kpis_out, fig_rank, fig_sc, fig_box, fig_hm, fig_sub


if __name__ == "__main__":
    print(f"\n🏈  DSS Dashboard  →  http://127.0.0.1:8050\n")
    app.run(debug=True, host="127.0.0.1", port=8050)
