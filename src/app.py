"""DSS Live Demo App — Dash interactive dashboard.

Run with:
    .venv/bin/python3 src/app.py
Then open http://127.0.0.1:8050 in your browser.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from dash import Dash, html, dcc, Input, Output, callback

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ── Load data ─────────────────────────────────────────────────────────────
df = pd.read_csv(OUTPUT_DIR / "dss_results.csv")
players_df = pd.read_csv(DATA_DIR / "players.csv")

ALL_TEAMS = sorted(df["defensiveTeam"].dropna().unique())
ALL_COVERAGES = sorted(df["coverageType"].dropna().unique())
ALL_COVERAGE_NAMES = sorted(df["coverage"].dropna().unique())

# ── App ───────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    title="Defensive Sync Score — NFL 2021",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
    ],
)

DARK_BG = "#0d1117"
CARD_BG = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
RED = "#f85149"


def kpi_card(title: str, value: str, subtitle: str = "", color: str = ACCENT):
    return html.Div(
        style={
            "background": CARD_BG,
            "border": f"1px solid {BORDER}",
            "borderRadius": "8px",
            "padding": "16px 20px",
            "flex": "1",
            "minWidth": "160px",
        },
        children=[
            html.P(title, style={"color": "#8b949e", "fontSize": "12px", "margin": "0 0 4px 0"}),
            html.H2(value, style={"color": color, "margin": "0 0 4px 0", "fontSize": "26px"}),
            html.P(subtitle, style={"color": "#8b949e", "fontSize": "11px", "margin": "0"}),
        ],
    )


app.layout = html.Div(
    style={"background": DARK_BG, "color": TEXT, "fontFamily": "Inter, sans-serif",
           "minHeight": "100vh", "padding": "24px 32px"},
    children=[
        # ── Header ──────────────────────────────────────────────────────
        html.Div([
            html.H1("🏈 Defensive Sync Score", style={"margin": "0", "fontSize": "28px"}),
            html.P(
                "NFL 2021 · 122 games · 7,510 plays · How synchronized is a defensive secondary?",
                style={"color": "#8b949e", "margin": "4px 0 0 0", "fontSize": "14px"},
            ),
        ], style={"marginBottom": "24px"}),

        # ── KPI row ─────────────────────────────────────────────────────
        html.Div(id="kpi-row", style={"display": "flex", "gap": "12px",
                                       "flexWrap": "wrap", "marginBottom": "24px"}),

        # ── Filters ─────────────────────────────────────────────────────
        html.Div([
            html.Div([
                html.Label("Coverage Type", style={"fontSize": "12px", "color": "#8b949e"}),
                dcc.Checklist(
                    id="filter-coverage-type",
                    options=[{"label": f"  {c}", "value": c} for c in ALL_COVERAGES],
                    value=ALL_COVERAGES,
                    inline=True,
                    style={"color": TEXT, "fontSize": "14px"},
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"marginRight": "16px"},
                ),
            ], style={"flex": "1"}),
            html.Div([
                html.Label("Down", style={"fontSize": "12px", "color": "#8b949e"}),
                dcc.RangeSlider(
                    id="filter-down",
                    min=1, max=4, step=1, value=[1, 4],
                    marks={i: str(i) for i in range(1, 5)},
                    tooltip={"placement": "bottom"},
                ),
            ], style={"flex": "1", "minWidth": "200px"}),
            html.Div([
                html.Label("Team (focus)", style={"fontSize": "12px", "color": "#8b949e"}),
                dcc.Dropdown(
                    id="filter-team",
                    options=[{"label": t, "value": t} for t in ALL_TEAMS],
                    value=None,
                    placeholder="All teams",
                    clearable=True,
                    style={"background": CARD_BG, "color": TEXT, "fontSize": "13px"},
                ),
            ], style={"flex": "1", "minWidth": "150px"}),
        ], style={
            "background": CARD_BG, "border": f"1px solid {BORDER}",
            "borderRadius": "8px", "padding": "16px 20px",
            "display": "flex", "gap": "24px", "flexWrap": "wrap", "marginBottom": "20px",
        }),

        # ── Charts row 1 ────────────────────────────────────────────────
        html.Div([
            html.Div([
                html.H3("Team Ranking", style={"color": TEXT, "fontSize": "15px", "margin": "0 0 12px 0"}),
                dcc.Graph(id="chart-ranking", style={"height": "500px"}),
            ], style={"flex": "1", "minWidth": "300px", "background": CARD_BG,
                      "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),

            html.Div([
                html.H3("DSS vs Completion Rate", style={"color": TEXT, "fontSize": "15px", "margin": "0 0 12px 0"}),
                dcc.Graph(id="chart-scatter", style={"height": "500px"}),
            ], style={"flex": "1.2", "minWidth": "300px", "background": CARD_BG,
                      "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # ── Charts row 2 ────────────────────────────────────────────────
        html.Div([
            html.Div([
                html.H3("DSS by Coverage Type", style={"color": TEXT, "fontSize": "15px", "margin": "0 0 12px 0"}),
                dcc.Graph(id="chart-box", style={"height": "380px"}),
            ], style={"flex": "1", "minWidth": "300px", "background": CARD_BG,
                      "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),

            html.Div([
                html.H3("Coverage Heatmap (DSS by scheme × down)", style={"color": TEXT, "fontSize": "15px", "margin": "0 0 12px 0"}),
                dcc.Graph(id="chart-heatmap", style={"height": "380px"}),
            ], style={"flex": "1.5", "minWidth": "300px", "background": CARD_BG,
                      "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # ── Sub-scores breakdown ─────────────────────────────────────────
        html.Div([
            html.H3("Sub-score Breakdown (VA · SD · OD)", style={"color": TEXT, "fontSize": "15px", "margin": "0 0 12px 0"}),
            dcc.Graph(id="chart-subscores", style={"height": "300px"}),
        ], style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                  "borderRadius": "8px", "padding": "16px", "marginBottom": "16px"}),

        # ── Footer ──────────────────────────────────────────────────────
        html.P(
            "DSS = 100 × (0.40·VA + 0.30·SD + 0.30·OD)  ·  "
            "VA: velocity alignment  ·  SD: spacing discipline  ·  OD: orientation divergence  ·  "
            "Data: NFL Big Data Bowl 2021",
            style={"color": "#8b949e", "fontSize": "11px", "textAlign": "center", "marginTop": "8px"},
        ),
    ],
)


def filter_df(coverage_types, down_range):
    filtered = df[
        df["coverageType"].isin(coverage_types) &
        df["down"].between(down_range[0], down_range[1])
    ]
    return filtered


@app.callback(
    Output("kpi-row", "children"),
    Output("chart-ranking", "figure"),
    Output("chart-scatter", "figure"),
    Output("chart-box", "figure"),
    Output("chart-heatmap", "figure"),
    Output("chart-subscores", "figure"),
    Input("filter-coverage-type", "value"),
    Input("filter-down", "value"),
    Input("filter-team", "value"),
)
def update_all(coverage_types, down_range, focus_team):
    if not coverage_types:
        coverage_types = ALL_COVERAGES

    fdf = filter_df(coverage_types, down_range)
    if focus_team:
        fdf_team = fdf[fdf["defensiveTeam"] == focus_team]
    else:
        fdf_team = fdf

    LAYOUT = dict(
        paper_bgcolor=DARK_BG, plot_bgcolor=CARD_BG,
        font=dict(color=TEXT, family="Inter, sans-serif"),
        margin=dict(t=20, b=40, l=40, r=20),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    )

    # ── KPIs ────────────────────────────────────────────────────────────
    n_plays = len(fdf_team) if focus_team else len(fdf)
    dss_mean = fdf_team["dss"].mean() if focus_team else fdf["dss"].mean()
    comp_rate = fdf_team["completed"].mean() if focus_team else fdf["completed"].mean()
    hi = fdf[fdf["dss"] >= fdf["dss"].median()]
    lo = fdf[fdf["dss"] < fdf["dss"].median()]
    delta = (hi["completed"].mean() - lo["completed"].mean()) * 100

    kpis = [
        kpi_card("Plays analyzed", f"{n_plays:,}"),
        kpi_card("Avg DSS", f"{dss_mean:.1f}", "/ 100", ACCENT),
        kpi_card("Completion rate", f"{comp_rate:.1%}", "in selection"),
        kpi_card("High vs Low DSS delta", f"{delta:+.1f}pp", "completion rate", GREEN if delta < 0 else RED),
        kpi_card("Best team", fdf.groupby("defensiveTeam")["dss"].mean().idxmax(),
                 f"DSS {fdf.groupby('defensiveTeam')['dss'].mean().max():.1f}", GREEN),
    ]

    # ── Ranking bar ──────────────────────────────────────────────────────
    team_agg = fdf.groupby("defensiveTeam")["dss"].agg(["mean", "count"]).reset_index()
    team_agg = team_agg[team_agg["count"] >= 3].sort_values("mean", ascending=True)

    bar_colors = [ACCENT if focus_team and row["defensiveTeam"] == focus_team else
                  px.colors.sample_colorscale("RdYlGn",
                    [(row["mean"] - team_agg["mean"].min()) /
                     max(team_agg["mean"].max() - team_agg["mean"].min(), 0.01)])[0]
                  for _, row in team_agg.iterrows()]

    fig_rank = go.Figure(go.Bar(
        x=team_agg["mean"], y=team_agg["defensiveTeam"], orientation="h",
        marker_color=bar_colors,
        customdata=team_agg["count"].values,
        hovertemplate="<b>%{y}</b><br>DSS: %{x:.1f}<br>Plays: %{customdata}<extra></extra>",
    ))
    fig_rank.update_layout(**LAYOUT, showlegend=False)
    fig_rank.update_xaxes(title_text="DSS", range=[48, 62])
    fig_rank.update_yaxes(tickfont=dict(size=9))

    # ── Scatter DSS vs completion ─────────────────────────────────────────
    fig_scatter = go.Figure()
    for ct, color in [("Man", "#FF5722"), ("Zone", "#2196F3")]:
        if ct not in coverage_types:
            continue
        sub = fdf[fdf["coverageType"] == ct].copy()
        if len(sub) < 10:
            continue
        binned = sub.groupby(pd.cut(sub["dss"], bins=10)).agg(
            dss=("dss", "mean"), comp=("completed", "mean"), n=("completed", "count")
        ).reset_index(drop=True).dropna()
        binned = binned[binned["n"] >= 5]
        fig_scatter.add_trace(go.Scatter(
            x=binned["dss"], y=binned["comp"],
            mode="markers+lines",
            marker=dict(size=binned["n"] / binned["n"].max() * 18 + 6, color=color, opacity=0.8),
            line=dict(color=color, dash="dot"),
            name=ct,
            hovertemplate=f"<b>{ct}</b><br>DSS: %{{x:.1f}}<br>Comp: %{{y:.1%}}<extra></extra>",
        ))
    fig_scatter.update_layout(**LAYOUT)
    fig_scatter.update_xaxes(title_text="DSS (binned)")
    fig_scatter.update_yaxes(title_text="Completion Rate", tickformat=".0%")

    # ── Box plot ─────────────────────────────────────────────────────────
    fig_box = go.Figure()
    palette = {"Man": "#FF5722", "Zone": "#2196F3", "Other": "#9C27B0"}
    for ct in coverage_types:
        sub = fdf[fdf["coverageType"] == ct]
        if len(sub) < 5:
            continue
        fig_box.add_trace(go.Box(
            y=sub["dss"], name=ct, marker_color=palette.get(ct, "#888"),
            boxpoints="outliers", hovertemplate=f"<b>{ct}</b><br>DSS: %{{y:.1f}}<extra></extra>",
        ))
    fig_box.update_layout(**LAYOUT)
    fig_box.update_yaxes(title_text="DSS")

    # ── Heatmap ───────────────────────────────────────────────────────────
    pivot = fdf.pivot_table(values="dss", index="coverage", columns="down", aggfunc="mean")
    fig_hm = go.Figure(go.Heatmap(
        z=pivot.values, x=[f"Down {int(d)}" for d in pivot.columns],
        y=pivot.index.tolist(), colorscale="RdYlGn",
        text=np.where(np.isnan(pivot.values), "", np.round(pivot.values, 1).astype(str)),
        texttemplate="%{text}",
        hovertemplate="Coverage: %{y}<br>%{x}<br>DSS: %{z:.1f}<extra></extra>",
        colorbar=dict(len=0.9),
    ))
    fig_hm.update_layout(**LAYOUT, margin=dict(t=20, b=40, l=140, r=20))

    # ── Sub-scores team radar / bar ────────────────────────────────────────
    if focus_team:
        sub_data = fdf[fdf["defensiveTeam"] == focus_team]
    else:
        top5 = fdf.groupby("defensiveTeam")["dss"].mean().nlargest(5).index
        sub_data = fdf[fdf["defensiveTeam"].isin(top5)]

    sub_agg = sub_data.groupby("defensiveTeam")[["va", "sd", "od", "dss"]].mean().reset_index()
    fig_sub = go.Figure()
    palette2 = px.colors.qualitative.Set2
    for i, (_, row) in enumerate(sub_agg.iterrows()):
        fig_sub.add_trace(go.Bar(
            name=row["defensiveTeam"],
            x=["Velocity Align (VA)", "Spacing Discipline (SD)", "Orient. Divergence (OD)", "DSS (composite)"],
            y=[row["va"], row["sd"], row["od"], row["dss"]],
            marker_color=palette2[i % len(palette2)],
        ))
    fig_sub.update_layout(**LAYOUT, barmode="group", legend=dict(bgcolor="rgba(0,0,0,0.3)"))
    fig_sub.update_yaxes(title_text="Score (0–100)", range=[0, 100])

    return kpis, fig_rank, fig_scatter, fig_box, fig_hm, fig_sub


if __name__ == "__main__":
    print("\n🏈 DSS Live Demo starting...")
    print("   Open http://127.0.0.1:8050 in your browser\n")
    app.run(debug=True, host="127.0.0.1", port=8050)
