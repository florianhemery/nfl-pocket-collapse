"""Generate a self-contained interactive Plotly HTML dashboard for the DSS results."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def build_dashboard(dss_csv: str, output_path: str) -> str:
    df = pd.read_csv(dss_csv)

    # ── Team ranking ──────────────────────────────────────────────────────
    team_agg = (
        df.groupby("defensiveTeam")["dss"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "dss_mean", "std": "dss_std", "count": "n"})
    )
    team_agg = team_agg[team_agg["n"] >= 5].sort_values("dss_mean", ascending=True)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "🏈 Team Defensive Sync Score Ranking",
            "📊 DSS vs Pass Completion Rate (Man vs Zone)",
            "🔥 DSS by Coverage Type × Down",
            "📈 DSS Distribution by Coverage Type",
        ),
        specs=[
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "heatmap"}, {"type": "box"}],
        ],
        vertical_spacing=0.14,
        horizontal_spacing=0.10,
    )

    # ── 1. Team ranking bar ───────────────────────────────────────────────
    colorscale = px.colors.diverging.RdYlGn
    norm = (team_agg["dss_mean"] - team_agg["dss_mean"].min()) / (
        team_agg["dss_mean"].max() - team_agg["dss_mean"].min()
    )
    bar_colors = px.colors.sample_colorscale(colorscale, norm.tolist())

    fig.add_trace(
        go.Bar(
            x=team_agg["dss_mean"],
            y=team_agg["defensiveTeam"],
            orientation="h",
            marker_color=bar_colors,
            error_x=dict(type="data", array=team_agg["dss_std"].tolist()),
            customdata=team_agg[["n", "dss_std"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "DSS: %{x:.1f} ± %{customdata[1]:.1f}<br>"
                "Plays: %{customdata[0]}<extra></extra>"
            ),
            name="Team DSS",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # ── 2. DSS vs completion rate scatter ─────────────────────────────────
    for ct, color in [("Man", "#FF5722"), ("Zone", "#2196F3")]:
        sub = df[df["coverageType"] == ct].copy()
        if sub.empty:
            continue
        bins = pd.cut(sub["dss"], bins=12)
        binned = sub.groupby(bins, observed=True).agg(
            dss=("dss", "mean"),
            comp_rate=("completed", "mean"),
            count=("completed", "count"),
        ).reset_index(drop=True).dropna()
        binned = binned[binned["count"] >= 5]

        fig.add_trace(
            go.Scatter(
                x=binned["dss"],
                y=binned["comp_rate"],
                mode="markers+lines",
                marker=dict(size=binned["count"] / binned["count"].max() * 20 + 5,
                            color=color, opacity=0.7),
                line=dict(color=color, width=2, dash="dash"),
                name=f"{ct} coverage",
                hovertemplate=(
                    f"<b>{ct}</b><br>DSS: %{{x:.1f}}<br>"
                    "Comp Rate: %{y:.1%}<extra></extra>"
                ),
            ),
            row=1, col=2,
        )

    # ── 3. Heatmap coverage × down ────────────────────────────────────────
    pivot = df.pivot_table(values="dss", index="coverage", columns="down", aggfunc="mean")
    pivot = pivot.fillna(np.nan)

    fig.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=[f"Down {int(d)}" for d in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="RdYlGn",
            text=np.where(np.isnan(pivot.values), "", np.round(pivot.values, 1).astype(str)),
            texttemplate="%{text}",
            hovertemplate="Coverage: %{y}<br>%{x}<br>DSS: %{z:.1f}<extra></extra>",
            showscale=True,
            colorbar=dict(x=1.01, len=0.45, y=0.12),
        ),
        row=2, col=1,
    )

    # ── 4. Box plot by coverage type ──────────────────────────────────────
    for ct, color in [("Man", "#FF5722"), ("Zone", "#2196F3"), ("Other", "#9C27B0")]:
        sub = df[df["coverageType"] == ct]
        if len(sub) < 5:
            continue
        fig.add_trace(
            go.Box(
                y=sub["dss"],
                name=ct,
                marker_color=color,
                boxpoints="outliers",
                hovertemplate=f"<b>{ct}</b><br>DSS: %{{y:.1f}}<extra></extra>",
            ),
            row=2, col=2,
        )

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="<b>Defensive Sync Score (DSS) Dashboard</b><br>"
                 "<sup>NFL 2021 Season · 122 games · 7,510 plays · "
                 "How synchronized is a defensive secondary?</sup>",
            x=0.5,
            font=dict(size=20),
        ),
        height=900,
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="white", family="Arial"),
        legend=dict(bgcolor="rgba(0,0,0,0.3)", bordercolor="#333"),
        margin=dict(t=100, b=60, l=60, r=80),
    )

    # Axis labels
    fig.update_xaxes(title_text="DSS (0–100)", row=1, col=1,
                     gridcolor="#21262d", zerolinecolor="#21262d")
    fig.update_yaxes(title_text="", row=1, col=1, tickfont=dict(size=9))
    fig.update_xaxes(title_text="Defensive Sync Score", row=1, col=2,
                     gridcolor="#21262d")
    fig.update_yaxes(title_text="Completion Rate", row=1, col=2,
                     tickformat=".0%", gridcolor="#21262d")
    fig.update_xaxes(title_text="", row=2, col=1)
    fig.update_yaxes(title_text="", row=2, col=1)
    fig.update_yaxes(title_text="DSS", row=2, col=2, gridcolor="#21262d")

    # ── Export ────────────────────────────────────────────────────────────
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn", full_html=True)

    return str(output_path)


if __name__ == "__main__":
    dss_csv = str(OUTPUT_DIR / "dss_results.csv")
    out = build_dashboard(dss_csv, str(OUTPUT_DIR / "dss_dashboard.html"))
    print(f"Dashboard saved: {out}")
    print(f"Size: {Path(out).stat().st_size / 1024:.0f} KB")
