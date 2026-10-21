"""
NFL Defensive Sync Score - Premium Interactive Dashboard V2
Professional-grade interface for coaches, scouts, and analysts
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import numpy as np

# Load data
print("Loading DSS results...")
df = pd.read_csv('output/dss_results.csv')

# Compute advanced metrics
df['dss_category'] = pd.cut(df['dss'], bins=[0, 50, 55, 60, 100], labels=['Weak', 'Average', 'Good', 'Elite'])
df['completion_rate'] = df['completed']  # Already 0/1 in the data

# Team aggregations
team_stats = df.groupby('defensiveTeam').agg({
    'dss': 'mean',
    'va': 'mean',
    'sd': 'mean',
    'od': 'mean',
    'completion_rate': 'mean',
    'gameId': 'count'
}).round(2)
team_stats.columns = ['DSS', 'VA', 'SD', 'OD', 'Completion_Rate', 'Plays']
team_stats = team_stats.sort_values('DSS', ascending=False).reset_index()

# Coverage type analysis
coverage_stats = df.groupby('coverage').agg({
    'dss': ['mean', 'std', 'count'],
    'completion_rate': 'mean'
}).round(2)
coverage_stats.columns = ['DSS_Mean', 'DSS_Std', 'Plays', 'Completion_Rate']
coverage_stats = coverage_stats.sort_values('DSS_Mean', ascending=False).reset_index()

# Initialize Dash app with premium theme
app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "NFL DSS Analytics Platform"

# Color scheme
COLORS = {
    'primary': '#00D9FF',
    'secondary': '#FF6B35',
    'success': '#4CAF50',
    'warning': '#FFC107',
    'danger': '#F44336',
    'dark': '#1a1a1a',
    'light': '#e0e0e0'
}

# ============ LAYOUT ============
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("🏈 NFL DEFENSIVE SYNC SCORE", 
                       className="text-center mb-2",
                       style={'color': COLORS['primary'], 'fontWeight': 'bold', 'fontSize': '3rem'}),
                html.H4("Professional Analytics Platform | Season 2021 | 7,510 Plays Analyzed",
                       className="text-center mb-4",
                       style={'color': COLORS['light'], 'fontWeight': '300'}),
                html.Hr(style={'borderColor': COLORS['primary'], 'borderWidth': '2px'})
            ])
        ], width=12)
    ]),
    
    # Key Metrics Cards
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{len(df):,}", className="text-center mb-0", style={'color': COLORS['primary']}),
                    html.P("Total Plays", className="text-center", style={'color': COLORS['light']})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{len(team_stats)}", className="text-center mb-0", style={'color': COLORS['success']}),
                    html.P("NFL Teams", className="text-center", style={'color': COLORS['light']})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["success"]}'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{df['dss'].mean():.1f}", className="text-center mb-0", style={'color': COLORS['warning']}),
                    html.P("Avg DSS", className="text-center", style={'color': COLORS['light']})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["warning"]}'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{df['completion_rate'].mean()*100:.1f}%", className="text-center mb-0", style={'color': COLORS['danger']}),
                    html.P("Completion Rate", className="text-center", style={'color': COLORS['light']})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["danger"]}'})
        ], width=3)
    ], className="mb-4"),
    
    # Control Panel
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("🎛️ CONTROL PANEL", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Coverage Type Filter:", style={'color': COLORS['light'], 'fontWeight': 'bold'}),
                            dcc.Dropdown(
                                id='coverage-filter',
                                options=[{'label': 'All Coverage Types', 'value': 'ALL'}] + 
                                        [{'label': cov, 'value': cov} for cov in sorted(df['coverage'].dropna().unique())],
                                value='ALL',
                                style={'backgroundColor': COLORS['dark'], 'color': 'black'},
                                clearable=False
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Team Focus:", style={'color': COLORS['light'], 'fontWeight': 'bold'}),
                            dcc.Dropdown(
                                id='team-filter',
                                options=[{'label': 'All Teams', 'value': 'ALL'}] + 
                                        [{'label': team, 'value': team} for team in sorted(df['defensiveTeam'].unique())],
                                value='ALL',
                                style={'backgroundColor': COLORS['dark'], 'color': 'black'},
                                clearable=False
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("DSS Range:", style={'color': COLORS['light'], 'fontWeight': 'bold'}),
                            dcc.RangeSlider(
                                id='dss-range',
                                min=df['dss'].min(),
                                max=df['dss'].max(),
                                value=[df['dss'].min(), df['dss'].max()],
                                marks={int(val): {'label': str(int(val)), 'style': {'color': COLORS['light']}} 
                                       for val in np.linspace(df['dss'].min(), df['dss'].max(), 6)},
                                tooltip={"placement": "bottom", "always_visible": True}
                            )
                        ], width=4)
                    ])
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=12)
    ], className="mb-4"),
    
    # Main Visualizations - Row 1
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("📊 TEAM RANKINGS", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dcc.Graph(id='team-ranking-chart', config={'displayModeBar': False})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("🎯 DSS vs COMPLETION RATE", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dcc.Graph(id='dss-completion-scatter', config={'displayModeBar': False})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=6)
    ], className="mb-4"),
    
    # Main Visualizations - Row 2
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("📈 COVERAGE TYPE ANALYSIS", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dcc.Graph(id='coverage-analysis', config={'displayModeBar': False})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("🔍 SUB-SCORES BREAKDOWN", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dcc.Graph(id='subscores-radar', config={'displayModeBar': False})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=6)
    ], className="mb-4"),
    
    # Advanced Analytics Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("🔥 HEATMAP: DSS by Team & Coverage", style={'color': COLORS['primary']})),
                dbc.CardBody([
                    dcc.Graph(id='heatmap-chart', config={'displayModeBar': False})
                ])
            ], style={'backgroundColor': COLORS['dark'], 'border': f'2px solid {COLORS["primary"]}'})
        ], width=12)
    ], className="mb-4"),
    
    # Footer
    dbc.Row([
        dbc.Col([
            html.Hr(style={'borderColor': COLORS['primary']}),
            html.P(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Built with ❤️ for NFL Analytics",
                   className="text-center",
                   style={'color': COLORS['light'], 'fontSize': '0.9rem'})
        ], width=12)
    ])
    
], fluid=True, style={'backgroundColor': '#0a0a0a', 'padding': '20px'})


# ============ CALLBACKS ============

@app.callback(
    [Output('team-ranking-chart', 'figure'),
     Output('dss-completion-scatter', 'figure'),
     Output('coverage-analysis', 'figure'),
     Output('subscores-radar', 'figure'),
     Output('heatmap-chart', 'figure')],
    [Input('coverage-filter', 'value'),
     Input('team-filter', 'value'),
     Input('dss-range', 'value')]
)
def update_charts(coverage, team, dss_range):
    # Filter data
    filtered_df = df.copy()
    
    if coverage != 'ALL':
        filtered_df = filtered_df[filtered_df['coverage'] == coverage]
    
    if team != 'ALL':
        filtered_df = filtered_df[filtered_df['defensiveTeam'] == team]
    
    filtered_df = filtered_df[(filtered_df['dss'] >= dss_range[0]) & (filtered_df['dss'] <= dss_range[1])]
    
    # Recompute team stats with filtered data
    team_stats_filtered = filtered_df.groupby('defensiveTeam').agg({
        'dss': 'mean',
        'va': 'mean',
        'sd': 'mean',
        'od': 'mean',
        'completion_rate': 'mean',
        'gameId': 'count'
    }).round(2).sort_values('dss', ascending=False).reset_index()
    
    # 1. Team Ranking Bar Chart
    fig1 = go.Figure()
    colors_bar = [COLORS['success'] if dss >= 57 else COLORS['warning'] if dss >= 54 else COLORS['danger'] 
                  for dss in team_stats_filtered['dss']]
    
    fig1.add_trace(go.Bar(
        x=team_stats_filtered['defensiveTeam'],
        y=team_stats_filtered['dss'],
        marker_color=colors_bar,
        text=team_stats_filtered['dss'].round(1),
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>DSS: %{y:.2f}<extra></extra>'
    ))
    
    fig1.update_layout(
        template='plotly_dark',
        paper_bgcolor=COLORS['dark'],
        plot_bgcolor=COLORS['dark'],
        font=dict(color=COLORS['light']),
        xaxis_title="Team",
        yaxis_title="Defensive Sync Score",
        showlegend=False,
        height=400,
        margin=dict(t=20, b=40, l=40, r=20)
    )
    
    # 2. DSS vs Completion Rate Scatter
    fig2 = px.scatter(
        filtered_df,
        x='dss',
        y='completion_rate',
        color='coverage',
        hover_data=['defensiveTeam'],
        color_discrete_sequence=px.colors.qualitative.Vivid,
        opacity=0.7
    )
    
    fig2.update_layout(
        template='plotly_dark',
        paper_bgcolor=COLORS['dark'],
        plot_bgcolor=COLORS['dark'],
        font=dict(color=COLORS['light']),
        xaxis_title="Defensive Sync Score",
        yaxis_title="Completion Rate",
        legend_title="Coverage Type",
        height=400,
        margin=dict(t=20, b=40, l=40, r=20)
    )
    
    # 3. Coverage Type Box Plot
    fig3 = go.Figure()
    
    for cov in filtered_df['coverage'].dropna().unique():
        cov_data = filtered_df[filtered_df['coverage'] == cov]
        fig3.add_trace(go.Box(
            y=cov_data['dss'],
            name=cov,
            boxmean='sd',
            marker_color=COLORS['primary']
        ))
    
    fig3.update_layout(
        template='plotly_dark',
        paper_bgcolor=COLORS['dark'],
        plot_bgcolor=COLORS['dark'],
        font=dict(color=COLORS['light']),
        yaxis_title="Defensive Sync Score",
        xaxis_title="Coverage Type",
        showlegend=False,
        height=400,
        margin=dict(t=20, b=40, l=40, r=20)
    )
    
    # 4. Sub-scores Radar Chart (Top 5 teams)
    top_teams = team_stats_filtered.head(5)
    
    fig4 = go.Figure()
    
    for idx, row in top_teams.iterrows():
        fig4.add_trace(go.Scatterpolar(
            r=[row['va']*100, row['sd']*100, row['od']*100],
            theta=['Velocity Alignment', 'Spacing Discipline', 'Orientation Divergence'],
            fill='toself',
            name=row['defensiveTeam']
        ))
    
    fig4.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], color=COLORS['light']),
            bgcolor=COLORS['dark']
        ),
        template='plotly_dark',
        paper_bgcolor=COLORS['dark'],
        font=dict(color=COLORS['light']),
        showlegend=True,
        height=400,
        margin=dict(t=20, b=40, l=40, r=40)
    )
    
    # 5. Heatmap
    heatmap_data = filtered_df.pivot_table(
        values='dss',
        index='defensiveTeam',
        columns='coverage',
        aggfunc='mean'
    ).fillna(0)
    
    fig5 = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale='Viridis',
        text=heatmap_data.values.round(1),
        texttemplate='%{text}',
        textfont={"size": 10},
        colorbar=dict(title="DSS")
    ))
    
    fig5.update_layout(
        template='plotly_dark',
        paper_bgcolor=COLORS['dark'],
        plot_bgcolor=COLORS['dark'],
        font=dict(color=COLORS['light']),
        xaxis_title="Coverage Type",
        yaxis_title="Team",
        height=500,
        margin=dict(t=20, b=60, l=60, r=20)
    )
    
    return fig1, fig2, fig3, fig4, fig5


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏈 NFL DSS ANALYTICS PLATFORM V2 - STARTING")
    print("="*60)
    print(f"📊 Loaded {len(df):,} plays")
    print(f"🏟️  {len(team_stats)} teams analyzed")
    print(f"📈 Average DSS: {df['dss'].mean():.2f}")
    print(f"🎯 Server running on: http://127.0.0.1:8050")
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=8050)
