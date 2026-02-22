# -*- coding: utf-8 -*-
"""
Football Analytics Dashboard
Author: Hardy Agarwal
Refactored: 2025 — removed VAEP/DB dependencies, simplified for Render deployment
Performance optimised: lazy loading of heavy dependencies to minimise cold-start time
"""

# ── Minimal imports at startup ──────────────────────────────────────────────
import functools
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# ── Lazy-loaded module-level globals ────────────────────────────────────────
_imports_loaded = False
_comp_data = None
_empty_pitch_src = None

# These are populated by _load_heavy_imports() on first use
sb = pd = io = base64 = plt = field = MPS = passingnetwork = plotaction = None


def _load_heavy_imports():
    """Import all heavy dependencies once, on first user interaction."""
    global _imports_loaded
    global sb, pd, io, base64, plt, field, MPS, passingnetwork, plotaction

    if _imports_loaded:
        return

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt

    from statsbombpy import sb as _sb
    import pandas as _pd
    import io as _io
    import base64 as _b64

    import field as _field
    import MPS as _MPS
    from graph import passingnetwork as _pn
    from actionplot import plotaction as _pa

    sb = _sb
    pd = _pd
    io = _io
    base64 = _b64
    plt = _plt
    field = _field
    MPS = _MPS
    passingnetwork = _pn
    plotaction = _pa

    _imports_loaded = True


def _get_comp():
    """Lazy-load games.csv on first access."""
    global _comp_data
    if _comp_data is None:
        _load_heavy_imports()
        _comp_data = pd.read_csv('games.csv')
    return _comp_data


def _get_empty_pitch():
    """Generate the empty pitch image once, on first use."""
    global _empty_pitch_src
    if _empty_pitch_src is None:
        _load_heavy_imports()
        fig = plt.figure()
        ax = fig.add_subplot(111)
        MPS.drawactionfield(ax=ax, color='white',
                            linecolor='lightgrey', show=False)
        ax.axis('off')
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        _empty_pitch_src = 'data:image/png;base64,{}'.format(
            base64.b64encode(buf.getbuffer()).decode('utf8')
        )
        plt.close(fig)
    return _empty_pitch_src


# ── Data helpers (cached for performance) ───────────────────────────────────

@functools.lru_cache(maxsize=20)
def get_event_data(match_id):
    """Fetch and lightly process StatsBomb event data for a match."""
    _load_heavy_imports()
    events = sb.events(match_id=match_id)
    events['timestamp'] = pd.to_datetime(events['timestamp']).dt.time
    return events


@functools.lru_cache(maxsize=20)
def get_lineup_data(match_id):
    """Fetch StatsBomb lineup data for a match."""
    _load_heavy_imports()
    return sb.lineups(match_id=match_id)


def _safe_get(row, col, default=None):
    """Safely get a value from a row, handling nested dicts."""
    if col in row.index:
        val = row[col]
        if pd.notna(val) if not isinstance(val, dict) else True:
            return val
    return default


@functools.lru_cache(maxsize=20)
def get_match_stats(match_id):
    """Compute match summary statistics for both teams."""
    events = get_event_data(match_id)
    teams = events['team'].dropna().unique().tolist()
    if len(teams) < 2:
        return None

    stats = {}
    for team in teams:
        te = events[events['team'] == team]

        possession_events = len(te)

        shots = te[te['type'] == 'Shot']
        goals = 0
        total_shots = len(shots)
        shots_on_target = 0
        for i in shots.index:
            shot_data = shots.loc[i, 'shot'] if 'shot' in shots.columns else None
            if isinstance(shot_data, dict):
                outcome = shot_data.get('outcome', {})
                outcome_name = outcome.get('name', '') if isinstance(outcome, dict) else str(outcome)
            else:
                outcome_name = str(_safe_get(shots.loc[i], 'shot_outcome', ''))
            if outcome_name == 'Goal':
                goals += 1
            if outcome_name in ('Goal', 'Saved', 'Saved to Post'):
                shots_on_target += 1

        passes = te[te['type'] == 'Pass']
        total_passes = len(passes)
        successful_passes = 0
        for i in passes.index:
            pass_data = passes.loc[i, 'pass'] if 'pass' in passes.columns else None
            if isinstance(pass_data, dict):
                outcome = pass_data.get('outcome')
                if outcome is None:
                    successful_passes += 1
            else:
                outcome = _safe_get(passes.loc[i], 'pass_outcome', None)
                if pd.isna(outcome) if not isinstance(outcome, str) else outcome == '':
                    successful_passes += 1

        fouls = len(te[te['type'] == 'Foul Committed'])
        yellow = 0
        red = 0
        foul_events = te[te['type'] == 'Foul Committed']
        for i in foul_events.index:
            fc_data = foul_events.loc[i, 'foul_committed'] if 'foul_committed' in foul_events.columns else None
            if isinstance(fc_data, dict):
                card = fc_data.get('card', {})
                card_name = card.get('name', '') if isinstance(card, dict) else str(card)
            else:
                card_name = str(_safe_get(foul_events.loc[i], 'foul_committed_card', ''))
            if 'Yellow' in card_name:
                yellow += 1
            if 'Red' in card_name or 'Second Yellow' in card_name:
                red += 1

        stats[team] = {
            'possession_events': possession_events,
            'goals': goals,
            'shots': total_shots,
            'shots_on_target': shots_on_target,
            'passes': total_passes,
            'pass_accuracy': round(100 * successful_passes / total_passes, 1) if total_passes > 0 else 0,
            'fouls': fouls,
            'yellow_cards': yellow,
            'red_cards': red,
        }

    total_events = sum(s['possession_events'] for s in stats.values())
    for team in stats:
        stats[team]['possession'] = round(
            100 * stats[team]['possession_events'] / total_events, 1
        ) if total_events > 0 else 0

    return teams, stats


@functools.lru_cache(maxsize=20)
def get_xg_data(match_id):
    """
    Compute cumulative xG flow and extract a flat list of all shots.
    Returns: (xg_flow_dict, shots_df, goals_markers)
    """
    events = get_event_data(match_id)
    teams = events['team'].dropna().unique().tolist()
    if len(teams) < 2:
        return None, None, None

    # 1. Filter and process shots (Exclude penalties - period 5)
    shots = events[(events['type'] == 'Shot') & (events['period'] <= 4)].copy()
    
    # Extract xG and Outcome from nested or flat columns
    def get_shot_metrics(row):
        xg, outcome = 0, ''
        if 'shot' in row and isinstance(row['shot'], dict):
            xg = row['shot'].get('statsbomb_xg', 0)
            outcome = row['shot'].get('outcome', {}).get('name', '')
        else:
            xg = row.get('shot_statsbomb_xg', 0)
            outcome = row.get('shot_outcome', '')
        return pd.Series([xg if pd.notna(xg) else 0, outcome])

    shots[['xg', 'outcome']] = shots.apply(get_shot_metrics, axis=1)
    shots['time_in_seconds'] = shots['minute'] * 60 + shots['second']
    shots = shots.sort_values('time_in_seconds')

    # 2. Build cumulative flow data
    xg_flow = {}
    goals_markers = []
    
    # Ensure lines start at zero
    for team in teams:
        team_shots = shots[shots['team'] == team]
        
        # Timeline: 0, then every shot time, then end of match (max time or 90/120)
        times = [0] + team_shots['time_in_seconds'].tolist()
        vals = [0] + team_shots['xg'].cumsum().tolist()
        
        # Add goal marker metadata
        for _, row in team_shots[team_shots['outcome'] == 'Goal'].iterrows():
            goals_markers.append({
                'team': team,
                'time': row['time_in_seconds'],
                'minute': row['minute'],
                'player': row.get('player', 'Unknown'),
                'xg': round(row['xg'], 2)
            })
            
        xg_flow[team] = {'times': times, 'vals': vals}

    return xg_flow, shots, goals_markers
    return xg_flow, shots, goals_markers


def create_xg_flow_fig(xg_flow, goals_markers):
    """Create a Plotly xG Flow Chart."""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    colors = ['#1f77b4', '#d62728'] # Blue, Red
    for i, (team, data) in enumerate(xg_flow.items()):
        # Step line for xG flow
        fig.add_trace(go.Scatter(
            x=[t/60 for t in data['times']], # Minutes
            y=data['vals'],
            mode='lines',
            name=team,
            line=dict(shape='hv', color=colors[i % len(colors)], width=3),
            hovertemplate='%{y:.2f} xG at %{x:.1f} min<extra></extra>'
        ))
        
        # Add Goal markers (Consolidated legend entry)
        team_goals = [g for g in goals_markers if g['team'] == team]
        if team_goals:
            fig.add_trace(go.Scatter(
                x=[g['time']/60 for g in team_goals],
                y=[xg_flow[team]['vals'][xg_flow[team]['times'].index(g['time'])] for g in team_goals],
                mode='markers',
                marker=dict(symbol='star', size=12, color='gold', 
                            line=dict(color='black', width=1)),
                name='Goal',
                text=[f"Goal: {g['player']} ({g['minute']}')<br>Value: {g['xg']} xG" for g in team_goals],
                hoverinfo='text',
                showlegend=(i == 0) # Only show in legend once
            ))

    fig.update_layout(
        title='Match xG Flow',
        xaxis_title='Minute',
        yaxis_title='Cumulative xG',
        template='plotly_white',
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
        height=350
    )
    return fig


def create_shot_map_fig(shots):
    """Create a vertical interactive Plotly Shot Map with team-separated halves."""
    import plotly.graph_objects as go
    import numpy as np

    fig = go.Figure()

    # Draw Pitch using shapes (Vertical 80x120)
    # Pitch Outline
    fig.add_shape(type="rect", x0=0, y0=0, x1=80, y1=120, line=dict(color="black"))
    # Centre Line
    fig.add_shape(type="line", x0=0, y0=60, x1=80, y1=60, line=dict(color="black"))
    # Centre Circle
    fig.add_shape(type="circle", x0=31, y0=51, x1=49, y1=69, line=dict(color="black"))
    
    # Penalty boxes (Vertical)
    # Bottom penn box
    fig.add_shape(type="rect", x0=18, y0=0, x1=62, y1=18, line=dict(color="black"))
    # Top penn box
    fig.add_shape(type="rect", x0=18, y0=102, x1=62, y1=120, line=dict(color="black"))

    # Add dummy traces for non-team-specific legend
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        name='Goal',
        marker=dict(symbol='circle', color='gray', size=14),
        showlegend=True
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        name='No Goal',
        marker=dict(symbol='x', color='gray', size=14),
        showlegend=True
    ))

    # Identify teams and colors
    teams = shots['team'].dropna().unique().tolist()
    team_colors = ['blue', '#d62728'] # Blue, Red
    
    # Plot Shots
    for i, team in enumerate(teams):
        ts = shots[shots['team'] == team]
        flip = (i == 1) # Flip the second team to the opposite half (top half)
        color = team_colors[i % len(team_colors)]
        
        ts_goals = ts[ts['outcome'] == 'Goal']
        ts_misses = ts[ts['outcome'] != 'Goal']

        for df, name, symbol in [(ts_goals, 'Goal', 'circle'), 
                                 (ts_misses, 'No Goal', 'x')]:
            if df.empty: continue
            
            # Vertical mapping:
            # StatsBomb (0-120, 0-80). 
            # Vert display (0-80, 0-120).
            if flip:
                # Top half (attacking down towards y=0)
                xv = [loc[1] for loc in df['location']]
                yv = [120 - loc[0] for loc in df['location']]
            else:
                # Bottom half (attacking up towards y=120)
                xv = [80 - loc[1] for loc in df['location']]
                yv = [loc[0] for loc in df['location']]
            
            fig.add_trace(go.Scatter(
                x=xv,
                y=yv,
                mode='markers',
                name=f"{team} ({name})",
                marker=dict(
                    size=np.sqrt(df['xg']) * 20 + 5,
                    color=color,
                    opacity=0.6,
                    symbol=symbol,
                    line=dict(width=1, color='DarkSlateGrey')
                ),
                text=[f"<b>{team}</b><br>{row['player']}<br>{row['minute']}' | {row['xg']:.2f} xG<br>Outcome: {row['outcome']}" 
                      for _, row in df.iterrows()],
                customdata=df.index.tolist(), 
                hovertemplate='%{text}<br><i>Hover to trace buildup</i><extra></extra>',
                showlegend=False # Legend handled by dummy traces
            ))

    fig.update_layout(
        title='Match Shot Map',
        xaxis=dict(range=[-5, 85], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-5, 125], showgrid=False, zeroline=False, visible=False),
        template='plotly_white',
        height=600,
        width=400,
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=14)),
        clickmode='event+select'
    )
    return fig
    _load_heavy_imports()
    fig = field.drawfield()
    events = get_event_data(match_id)
    playerdata = events[events['player'] == player_name].copy()

    playerdata['second'] = playerdata['second'].apply(lambda s: str(s).zfill(2))

    # ── PASSES ──
    playerpassdata = playerdata[playerdata['type'] == 'Pass']
    passannotation = []
    px1, py1, pcolors, ptime = [500], [50], ['black'], ['00:00']

    for i in playerpassdata.index:
        outcome = playerpassdata.loc[i, 'pass_outcome'] if 'pass_outcome' in playerpassdata.columns else None
        color = 'red' if pd.notna(outcome) else 'blue'
        end_loc = playerpassdata.loc[i, 'pass_end_location'] if 'pass_end_location' in playerpassdata.columns else None
        if end_loc is None or (isinstance(end_loc, float) and pd.isna(end_loc)):
            continue
        start_loc = playerpassdata.loc[i, 'location']
        passannotation.append(dict(
            x=end_loc[0], y=80 - end_loc[1],
            ax=start_loc[0], ay=80 - start_loc[1],
            text='', xref='x', yref='y', axref='x', ayref='y',
            showarrow=True, arrowhead=2, arrowcolor=color, opacity=0.7
        ))
        px1.append(start_loc[0])
        py1.append(80 - start_loc[1])
        pcolors.append(color)
        ptime.append(f"{playerpassdata.loc[i, 'minute']}:{playerpassdata.loc[i, 'second']}")

    passes = pd.DataFrame({'x1': px1, 'y1': py1, 'Colors': pcolors, 'Time': ptime})
    passes['Hoverinfo'] = 'Time: ' + passes['Time']

    # ── SHOTS (with xG) ──
    playershotdata = playerdata[playerdata['type'] == 'Shot']
    shotannotation = []
    sx1, sy1, scolors, stime, sxg, soutcome_list = [500], [50], ['black'], ['00:00'], [0], ['']

    for i in playershotdata.index:
        shot_data = playershotdata.loc[i, 'shot'] if 'shot' in playershotdata.columns else None
        if isinstance(shot_data, dict):
            outcome = shot_data.get('outcome', {})
            outcome_name = outcome.get('name', '') if isinstance(outcome, dict) else str(outcome)
            xg = shot_data.get('statsbomb_xg', 0) or 0
            end_loc = shot_data.get('end_location')
        else:
            outcome_name = playershotdata.loc[i, 'shot_outcome'] if 'shot_outcome' in playershotdata.columns else ''
            xg = playershotdata.loc[i, 'shot_statsbomb_xg'] if 'shot_statsbomb_xg' in playershotdata.columns else 0
            if pd.isna(xg):
                xg = 0
            end_loc = playershotdata.loc[i, 'shot_end_location'] if 'shot_end_location' in playershotdata.columns else None

        color = 'blue' if outcome_name == 'Goal' else 'red'
        if end_loc is None or (isinstance(end_loc, float) and pd.isna(end_loc)):
            continue
        start_loc = playerdata.loc[i, 'location']
        shotannotation.append(dict(
            x=end_loc[0], y=80 - end_loc[1],
            ax=start_loc[0], ay=80 - start_loc[1],
            text='', xref='x', yref='y', axref='x', ayref='y',
            showarrow=True, arrowcolor=color,
            arrowsize=1, arrowwidth=4, arrowhead=4, opacity=0.7
        ))
        sx1.append(start_loc[0])
        sy1.append(80 - start_loc[1])
        scolors.append(color)
        stime.append(f"{playershotdata.loc[i, 'minute']}:{playershotdata.loc[i, 'second']}")
        sxg.append(round(float(xg), 2))
        soutcome_list.append(outcome_name)

    shots = pd.DataFrame({'x1': sx1, 'y1': sy1, 'Colors': scolors, 'Time': stime,
                          'xG': sxg, 'Outcome': soutcome_list})
    shots['Hoverinfo'] = shots.apply(
        lambda r: f"Time: {r['Time']}<br>xG: {r['xG']}<br>Outcome: {r['Outcome']}"
        if r['Time'] != '00:00' else '', axis=1
    )

    # ── TACKLES ──
    playerdueldata = playerdata[playerdata['type'] == 'Duel']
    tx1, ty1, tcolors, ttime = [500], [50], ['black'], ['00:00']

    for i in playerdueldata.index:
        try:
            duel_type = playerdueldata.loc[i, 'duel_type'] if 'duel_type' in playerdueldata.columns else ''
            duel_outcome = playerdueldata.loc[i, 'duel_outcome'] if 'duel_outcome' in playerdueldata.columns else ''
            if duel_type == 'Tackle':
                color = 'red' if duel_outcome in ('Lost In Play', 'Lost Out') else 'blue'
                tcolors.append(color)
                tx1.append(playerdueldata.loc[i, 'location'][0])
                ty1.append(80 - playerdueldata.loc[i, 'location'][1])
                ttime.append(f"{playerdueldata.loc[i, 'minute']}:{playerdueldata.loc[i, 'second']}")
        except (KeyError, TypeError):
            continue

    tackles = pd.DataFrame({'x1': tx1, 'y1': ty1, 'Colors': tcolors, 'Time': ttime})
    tackles['Hoverinfo'] = 'Time: ' + tackles['Time']

    # ── HEATMAP ──
    locs = playerdata['location'].dropna()
    heatmap = [[loc[0] for loc in locs], [80 - loc[1] for loc in locs]]

    return fig, passannotation, passes, shotannotation, shots, tackles, heatmap


# ── App setup ────────────────────────────────────────────────────────────────

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server  # Expose for gunicorn
app.config['suppress_callback_exceptions'] = True

COLORS = {'background': '#F9F9F9'}


# ── Layout (built lazily on first request) ───────────────────────────────────

def _build_layout():
    """Build the full layout with competition options loaded from games.csv."""
    comp = _get_comp()
    compname = comp['competition_name'].unique()

    return html.Div(
        style={'backgroundColor': COLORS['background']},
        children=[
            # Header
            html.Div(
                style={'textAlign': 'center', 'margin': -2, 'padding': -10, 'fontSize': 48},
                children=[html.B('Football Analytics')]
            ),
            html.H4(
                'Visualizing football event data',
                style={'textAlign': 'center', 'margin': -2, 'padding': -10}
            ),
            html.Div(
                style={'textAlign': 'center', 'margin': -2, 'padding': -10, 'fontSize': 26},
                children=[html.A('Hardik Agarwal',
                                 href='https://www.linkedin.com/in/hardy-agarwal/',
                                 target='_blank')]
            ),

            # Main content: sidebar + tabs
            html.Div(
                style={'display': 'flex', 'flexDirection': 'row',
                       'backgroundColor': COLORS['background']},
                children=[

                    # ── LEFT SIDEBAR ──
                    html.Div(
                        style={'width': '25%', 'border': 'thin lightgrey solid', 'padding': '10px'},
                        children=[
                            html.H3('Choose a team and player to analyse!'),
                            html.P('Note: Player dropdown options may take a few seconds to load.'),

                            html.P('Competition:'),
                            dcc.Dropdown(
                                id='competition',
                                options=[{'label': c, 'value': c} for c in compname]
                            ),

                            html.P('Season:'),
                            dcc.Dropdown(id='season'),

                            html.P('Match:'),
                            dcc.Dropdown(id='match'),

                            html.Hr(),
                            html.B('Passing Network', style={'fontSize': 16}),

                            html.P('Team:'),
                            dcc.Dropdown(id='team'),

                            html.Hr(),
                            html.B('Player Analysis', style={'fontSize': 16}),

                            html.P('Player:'),
                            dcc.Dropdown(id='player'),

                            html.P('Actions:'),
                            dcc.Checklist(
                                id='actions',
                                options=[
                                    {'label': ' Passes',  'value': 'Passes'},
                                    {'label': ' Shots',   'value': 'Shots'},
                                    {'label': ' Tackles', 'value': 'Tackles'},
                                    {'label': ' Heatmap', 'value': 'Heatmap'},
                                ]
                            ),
                        ]
                    ),

                    # ── RIGHT PANEL (tabs) ──
                    html.Div(
                        style={'width': '75%', 'padding': '10px'},
                        children=[
                            dcc.Tabs([
                                dcc.Tab(label='Match Stats', children=[
                                    html.Div(id='match-stats-container',
                                             style={'padding': '20px'},
                                             children=[html.P('Select a match to view statistics.')])
                                ]),
                                dcc.Tab(label='Passing Network', children=[
                                    html.Img(id='pitch2', src='',
                                             style={'maxWidth': '100%'}),
                                    html.P(
                                        'Passing network for the starting lineup. '
                                        'Only successful passes before the first substitution '
                                        'or red card are shown. Node size = number of passes.'
                                    )
                                ]),
                                dcc.Tab(label='Player Analysis', children=[
                                    dcc.Graph(id='pitch1', figure={})
                                ]),
                                dcc.Tab(label='Goals', children=[
                                    html.Div(style={'padding': '20px'}, children=[
                                        html.H3('Match Offensive Overview', style={'textAlign': 'center'}),
                                        html.Div(style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center', 'gap': '20px'}, children=[
                                            html.Div(style={'flex': '2', 'minWidth': '400px'}, children=[
                                                dcc.Graph(id='xg-flow-chart', config={'displayModeBar': False})
                                            ]),
                                            html.Div(style={'flex': '1', 'maxWidth': '450px', 'minWidth': '350px'}, children=[
                                                dcc.Graph(id='shot-map', config={'displayModeBar': False})
                                            ]),
                                        ]),
                                        html.Hr(),
                                        html.Div(id='shot-trace-container', children=[
                                            html.H4('Shot Trace Preview (Hover over a shot)', style={'textAlign': 'center'}),
                                            html.Img(id='shot-trace-img', src='', 
                                                     style={'display': 'block', 'margin': '0 auto', 'maxWidth': '600px', 'border': '1px solid #ddd'})
                                        ]),
                                        html.Hr(),
                                        html.H4('Key Goal Moments (Timed Build-ups)', style={'textAlign': 'center'}),
                                        html.Img(id='pitch3', src='',
                                                 style={'maxWidth': '100%', 'display': 'block', 'margin': '0 auto'})
                                    ])
                                ]),
                            ])
                        ]
                    ),
                ]
            ),

            # Footer
            html.Div(
                ['Data Source: ', html.A(
                    'StatsBomb Open Data',
                    href='https://statsbomb.com/what-we-do/hub/free-data/',
                    target='_blank'
                )],
                style={'textAlign': 'left', 'fontSize': '18px', 'padding': '10px'}
            ),
        ]
    )


# Pass the function (not the result) so Dash calls it per-request
app.layout = _build_layout


# ── Callbacks ────────────────────────────────────────────────────────────────

@app.callback(Output('season', 'options'), Input('competition', 'value'))
def set_season_options(selected_comp):
    if not selected_comp:
        return []
    comp = _get_comp()
    seasons = (comp[comp['competition_name'] == selected_comp]
               [['season_name', 'season_id']].drop_duplicates())
    return [{'label': row['season_name'], 'value': row['season_id']}
            for _, row in seasons.iterrows()]


@app.callback(
    Output('match', 'options'),
    [Input('competition', 'value'), Input('season', 'value')]
)
def set_match_options(selected_comp, selected_season):
    if not selected_comp or selected_season is None:
        return []
    comp = _get_comp()
    matches = comp[
        (comp['competition_name'] == selected_comp) &
        (comp['season_id'] == selected_season)
    ]
    return [{'label': f"{row.home_team_name} vs {row.away_team_name}", 'value': row.game_id}
            for _, row in matches.iterrows()]


@app.callback(Output('team', 'options'), Input('match', 'value'))
def set_team_options(selected_match):
    if not selected_match:
        return []
    return [{'label': t, 'value': t} for t in get_lineup_data(selected_match).keys()]


@app.callback(
    Output('player', 'options'),
    [Input('match', 'value'), Input('team', 'value')]
)
def set_player_options(selected_match, selected_team):
    if not selected_match or not selected_team:
        return []
    events = get_event_data(selected_match)
    lineups = get_lineup_data(selected_match)[selected_team]
    active_players = set(events[events['team'] == selected_team]['player'].dropna().unique())
    squad = set(lineups['player_name'])
    players = active_players.intersection(squad)
    return [{'label': p, 'value': p} for p in sorted(players)]


@app.callback(
    Output('pitch2', 'src'),
    [Input('match', 'value'), Input('team', 'value')]
)
def update_passing_network(selected_match, selected_team):
    if not selected_match or not selected_team:
        return _get_empty_pitch()
    _load_heavy_imports()
    events = get_event_data(selected_match)
    lineups = get_lineup_data(selected_match)
    data = passingnetwork(selected_match, selected_team, events, lineups, 'Count')
    return 'data:image/png;base64,{}'.format(data)


@app.callback(Output('match-stats-container', 'children'), Input('match', 'value'))
def update_match_stats(selected_match):
    if not selected_match:
        return [html.P('Select a match to view statistics.')]

    result = get_match_stats(selected_match)
    if result is None:
        return [html.P('No stats available for this match.')]

    teams, stats = result
    t1, t2 = teams[0], teams[1]
    s1, s2 = stats[t1], stats[t2]

    stat_rows = [
        ('Possession', f"{s1['possession']}%", f"{s2['possession']}%"),
        ('Goals', s1['goals'], s2['goals']),
        ('Shots', s1['shots'], s2['shots']),
        ('Shots on Target', s1['shots_on_target'], s2['shots_on_target']),
        ('Passes', s1['passes'], s2['passes']),
        ('Pass Accuracy', f"{s1['pass_accuracy']}%", f"{s2['pass_accuracy']}%"),
        ('Fouls', s1['fouls'], s2['fouls']),
        ('Yellow Cards', s1['yellow_cards'], s2['yellow_cards']),
        ('Red Cards', s1['red_cards'], s2['red_cards']),
    ]

    header_style = {'padding': '12px 16px', 'fontWeight': 'bold', 'fontSize': '16px',
                    'borderBottom': '2px solid #ddd', 'textAlign': 'center'}
    cell_style = {'padding': '10px 16px', 'textAlign': 'center', 'fontSize': '15px',
                  'borderBottom': '1px solid #eee'}
    label_style = {**cell_style, 'fontWeight': '500', 'color': '#555'}

    table = html.Table(
        style={'width': '100%', 'borderCollapse': 'collapse', 'maxWidth': '700px', 'margin': '0 auto'},
        children=[
            html.Thead(html.Tr([
                html.Th(t1, style=header_style),
                html.Th('', style=header_style),
                html.Th(t2, style=header_style),
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(str(v1), style=cell_style),
                    html.Td(label, style=label_style),
                    html.Td(str(v2), style=cell_style),
                ]) for label, v1, v2 in stat_rows
            ])
        ]
    )

    return [
        html.H3(f"{t1} vs {t2}", style={'textAlign': 'center', 'marginBottom': '20px'}),
        table
    ]


@app.callback(
    [Output('pitch3', 'src'), 
     Output('xg-flow-chart', 'figure'),
     Output('shot-map', 'figure')],
    Input('match', 'value')
)
def update_goals(selected_match):
    if not selected_match:
        return _get_empty_pitch(), {}, {}
    
    _load_heavy_imports()
    
    # 1. Existing timed build-ups plot
    events = get_event_data(selected_match)
    goals_data = plotaction(selected_match, events=events, w=10, h=8, zoom=False)
    
    # 2. xG Data and Plots
    xg_flow, shots, goals_markers = get_xg_data(selected_match)
    if xg_flow is None:
        return 'data:image/png;base64,{}'.format(goals_data), {}, {}
        
    flow_fig = create_xg_flow_fig(xg_flow, goals_markers)
    shot_map_fig = create_shot_map_fig(shots)
    
    return 'data:image/png;base64,{}'.format(goals_data), flow_fig, shot_map_fig


# Global cache for traces to avoid duplicate computation
_shot_trace_cache = {}

@app.callback(
    Output('shot-trace-img', 'src'),
    [Input('shot-map', 'hoverData'), Input('match', 'value')]
)
def update_shot_trace(hoverData, selected_match):
    if not hoverData or not selected_match:
        return ''
    
    try:
        # dash.callback_context can trigger multiple times. 
        # Check if customdata exists in the first point
        pt = hoverData['points'][0]
        if 'customdata' not in pt or pt['customdata'] is None:
            return ''
            
        event_idx = pt['customdata']
        
        # Check cache
        cache_key = f"{selected_match}_{event_idx}"
        if cache_key in _shot_trace_cache:
            return _shot_trace_cache[cache_key]
        
        _load_heavy_imports()
        events = get_event_data(selected_match)
        
        # Filter for SPADL types similar to how plotaction does it
        # (This logic should ideally be shared, but for now we re-implement a minimal version)
        # Note: actionplot.py already has a plotaction which we can't easily repurpose 
        # for a single index without modification. 
        # We will use plotaction but we need to modify it to accept a specific index.
        # For now, let's call a slightly modified plotaction or implement the slice here.
        
        # Let's try to use plotaction if we can pass a specific goal_idx. 
        # I'll check if I can modify plotaction to support this.
        
        # For a quick implementation, I will implement a single-shot trace generator here.
        # w=10, h=10 provides enough room for the legend table at the top without overlapping the pitch.
        data = plotaction(selected_match, events=events, number=5, w=10, h=10, zoom=False, shot_idx=event_idx)
        
        src = 'data:image/png;base64,{}'.format(data)
        _shot_trace_cache[cache_key] = src
        return src
    except Exception as e:
        print(f"Error generating trace: {e}")
        return ''


@app.callback(
    Output('pitch1', 'figure'),
    [Input('player', 'value'), Input('actions', 'value'), Input('match', 'value')]
)
def update_player_figure(selected_player, selected_actions, selected_match):
    if not selected_player or not selected_match:
        _load_heavy_imports()
        return field.drawfield()

    selected_actions = selected_actions or []
    fig, passannotation, passes, shotannotation, shots, tackles, heatmap = \
        get_player_data(selected_match, selected_player)

    # Tackles (trace 0)
    if 'Tackles' in selected_actions:
        fig.data[0].x = tackles['x1']
        fig.data[0].y = tackles['y1']
        fig.data[0].marker['color'] = tackles['Colors']
        fig.data[0].hovertext = tackles['Hoverinfo']
    else:
        fig.data[0].x = fig.data[0].y = []
        fig.data[0].marker['color'] = []

    # Heatmap (trace 1)
    if 'Heatmap' in selected_actions:
        fig.data[1].x = heatmap[0]
        fig.data[1].y = heatmap[1]
    else:
        fig.data[1].x = fig.data[1].y = []

    # Passes (trace 2)
    if 'Passes' in selected_actions:
        fig.data[2].x = passes['x1']
        fig.data[2].y = passes['y1']
        fig.data[2].marker['color'] = passes['Colors']
        fig.data[2].hovertext = passes['Hoverinfo']
    else:
        fig.data[2].x = fig.data[2].y = []
        fig.data[2].marker['color'] = []

    # Shots (trace 3)
    if 'Shots' in selected_actions:
        fig.data[3].x = shots['x1']
        fig.data[3].y = shots['y1']
        fig.data[3].marker['color'] = shots['Colors']
        fig.data[3].hovertext = shots['Hoverinfo']
    else:
        fig.data[3].x = fig.data[3].y = []
        fig.data[3].marker['color'] = []

    # Arrows
    if 'Passes' in selected_actions and 'Shots' in selected_actions:
        fig.layout.annotations = passannotation + shotannotation
    elif 'Passes' in selected_actions:
        fig.layout.annotations = passannotation
    elif 'Shots' in selected_actions:
        fig.layout.annotations = shotannotation
    else:
        fig.layout.annotations = []

    return fig


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
