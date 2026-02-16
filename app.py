# -*- coding: utf-8 -*-
"""
Football Analytics Dashboard
Author: Hardy Agarwal
Refactored: 2025 — removed VAEP/DB dependencies, simplified for Render deployment
Performance optimized: 2025 — lazy loading for faster startup
"""

# Minimal imports for startup
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import functools

# Lazy-loaded globals
_heavy_imports_loaded = False
_comp_data = None


# ─────────────────────────────────────────────
# LAZY IMPORT HELPER
# ─────────────────────────────────────────────

def _ensure_heavy_imports():
    """Load heavy dependencies only when needed (first user interaction)."""
    global _heavy_imports_loaded, sb, pd, io, base64, plt, matplotlib, go
    global field, MPS, passingnetwork, plotaction

    if not _heavy_imports_loaded:
        import matplotlib as mpl
        mpl.use('Agg')
        matplotlib = mpl

        from statsbombpy import sb
        import pandas as pd
        import io
        import base64
        import matplotlib.pyplot as plt
        import plotly.graph_objects as go

        import field
        import MPS
        from graph import passingnetwork
        from actionplot import plotaction

        _heavy_imports_loaded = True


def _get_comp_data():
    """Lazy-load competition data on first access."""
    global _comp_data
    if _comp_data is None:
        _ensure_heavy_imports()
        _comp_data = pd.read_csv('games.csv')
    return _comp_data


# ─────────────────────────────────────────────
# DATA HELPERS (cached for performance)
# ─────────────────────────────────────────────

@functools.lru_cache(maxsize=20)
def get_event_data(match_id):
    """Fetch and lightly process StatsBomb event data for a match."""
    _ensure_heavy_imports()
    events = sb.events(match_id=match_id)
    events['timestamp'] = pd.to_datetime(events['timestamp']).dt.time
    return events


@functools.lru_cache(maxsize=20)
def get_lineup_data(match_id):
    """Fetch StatsBomb lineup data for a match."""
    _ensure_heavy_imports()
    return sb.lineups(match_id=match_id)


@functools.lru_cache(maxsize=20)
def get_player_data(match_id, player_name):
    """
    Build all visualisation data for a single player in a match.
    Returns pitch figure + pass/shot/tackle/heatmap data.
    """
    _ensure_heavy_imports()
    fig = field.drawfield()
    events = get_event_data(match_id)
    playerdata = events[events['player'] == player_name].copy()

    # Pad seconds to always be 2 digits
    playerdata['second'] = playerdata['second'].apply(
        lambda s: str(s).zfill(2)
    )

    # Current statsbombpy uses flat columns:
    #   pass_end_location (list), pass_outcome (string), pass_recipient (string)
    #   shot_end_location (list), shot_outcome (string like 'Goal', 'Off T', etc.)
    #   duel_type (string like 'Tackle'), duel_outcome (string like 'Won', 'Lost')

    # ── PASSES ──
    playerpassdata = playerdata[playerdata['type'] == 'Pass']
    passannotation = []
    px1, py1, pcolors, ptime = [500], [50], ['black'], ['00:00']

    for i in playerpassdata.index:
        # pass_outcome is NaN for successful passes, a string like 'Incomplete' for failed
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

    # ── SHOTS ──
    playershotdata = playerdata[playerdata['type'] == 'Shot']
    shotannotation = []
    sx1, sy1, scolors, stime = [500], [50], ['black'], ['00:00']

    for i in playershotdata.index:
        # shot_outcome is a string like 'Goal', 'Saved', 'Off T', 'Blocked', etc.
        outcome = playershotdata.loc[i, 'shot_outcome'] if 'shot_outcome' in playershotdata.columns else ''
        color = 'blue' if outcome == 'Goal' else 'red'

        end_loc = playershotdata.loc[i, 'shot_end_location'] if 'shot_end_location' in playershotdata.columns else None
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

    shots = pd.DataFrame({'x1': sx1, 'y1': sy1, 'Colors': scolors, 'Time': stime})
    shots['Hoverinfo'] = 'Time: ' + shots['Time']

    # ── TACKLES ──
    playerdueldata = playerdata[playerdata['type'] == 'Duel']
    tx1, ty1, tcolors, ttime = [500], [50], ['black'], ['00:00']

    for i in playerdueldata.index:
        try:
            # duel_type is a string like 'Tackle', 'Aerial Lost', etc.
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


def _safe_get(row, col, nested_key=None, default=None):
    """Safely extract a value from event data, handling both flat and nested formats."""
    if col not in row.index:
        return default
    val = row[col]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    if nested_key and isinstance(val, dict):
        return val.get(nested_key, default)
    return val


@functools.lru_cache(maxsize=20)
def get_xg_shot_data(match_id):
    """Extract shot data with xG values for both teams."""
    _ensure_heavy_imports()
    events = get_event_data(match_id)
    shots = events[events['type'] == 'Shot'].copy()

    result = []
    for i in shots.index:
        loc = shots.loc[i, 'location']
        if loc is None or (isinstance(loc, float) and pd.isna(loc)):
            continue

        # Handle both nested dict format and flat column format
        shot_data = shots.loc[i, 'shot'] if 'shot' in shots.columns else None
        if isinstance(shot_data, dict):
            xg = shot_data.get('statsbomb_xg', 0) or 0
            outcome = shot_data.get('outcome', {}).get('name', '') if isinstance(shot_data.get('outcome'), dict) else shot_data.get('outcome', '')
            shot_type = shot_data.get('type', {}).get('name', '') if isinstance(shot_data.get('type'), dict) else shot_data.get('type', '')
        else:
            xg = _safe_get(shots.loc[i], 'shot_statsbomb_xg', default=0)
            outcome = _safe_get(shots.loc[i], 'shot_outcome', default='')
            shot_type = _safe_get(shots.loc[i], 'shot_type', default='')

        result.append({
            'x': loc[0],
            'y': 80 - loc[1],
            'xg': float(xg),
            'outcome': outcome,
            'team': shots.loc[i, 'team'],
            'player': shots.loc[i, 'player'],
            'minute': int(shots.loc[i, 'minute']),
            'shot_type': shot_type,
            'is_goal': outcome == 'Goal'
        })

    return pd.DataFrame(result) if result else pd.DataFrame()


@functools.lru_cache(maxsize=20)
def get_match_stats(match_id):
    """Compute match summary statistics from event data."""
    _ensure_heavy_imports()
    events = get_event_data(match_id)
    teams = [t for t in events['team'].dropna().unique()][:2]

    def _extract_nested(row, col, key, default=None):
        """Extract from nested dict or flat column."""
        if col in row.index:
            val = row[col]
            if isinstance(val, dict):
                if key == 'name' and isinstance(val.get('outcome'), dict):
                    return val['outcome'].get('name', default)
                return val.get(key, default)
        flat_col = f"{col}_{key}"
        if flat_col in row.index:
            val = row[flat_col]
            return default if (val is None or (isinstance(val, float) and pd.isna(val))) else val
        return default

    stats = {}
    for team in teams:
        team_events = events[events['team'] == team]

        # Pass completion — handle both nested and flat formats
        passes = team_events[team_events['type'] == 'Pass']
        total_passes = len(passes)
        successful_passes = 0
        for idx in passes.index:
            if 'pass' in passes.columns:
                pass_data = passes.loc[idx, 'pass']
                if isinstance(pass_data, dict):
                    outcome = pass_data.get('outcome')
                    if outcome is None:
                        successful_passes += 1
                    continue
            if 'pass_outcome' in passes.columns:
                if pd.isna(passes.loc[idx, 'pass_outcome']):
                    successful_passes += 1
            else:
                successful_passes += 1
        pass_pct = (successful_passes / total_passes * 100) if total_passes > 0 else 0

        # Shots — handle both formats
        shots = team_events[team_events['type'] == 'Shot']
        total_shots = len(shots)
        goals = 0
        shots_on_target = 0
        for idx in shots.index:
            outcome = ''
            if 'shot' in shots.columns:
                shot_data = shots.loc[idx, 'shot']
                if isinstance(shot_data, dict):
                    outcome_obj = shot_data.get('outcome', {})
                    outcome = outcome_obj.get('name', '') if isinstance(outcome_obj, dict) else str(outcome_obj)
            elif 'shot_outcome' in shots.columns:
                outcome = shots.loc[idx, 'shot_outcome'] or ''
            if outcome == 'Goal':
                goals += 1
                shots_on_target += 1
            elif outcome == 'Saved':
                shots_on_target += 1

        # Fouls and cards
        fouls = team_events[team_events['type'] == 'Foul Committed']
        total_fouls = len(fouls)
        yellow_cards = 0
        red_cards = 0
        for idx in fouls.index:
            card = None
            if 'foul_committed' in fouls.columns:
                fc = fouls.loc[idx, 'foul_committed']
                if isinstance(fc, dict):
                    card_obj = fc.get('card', {})
                    card = card_obj.get('name', '') if isinstance(card_obj, dict) else ''
            elif 'foul_committed_card' in fouls.columns:
                card = fouls.loc[idx, 'foul_committed_card'] or ''
            if card == 'Yellow Card':
                yellow_cards += 1
            elif card in ('Red Card', 'Second Yellow'):
                red_cards += 1

        # Corners
        corners = 0
        for idx in passes.index:
            ptype = ''
            if 'pass' in passes.columns:
                p = passes.loc[idx, 'pass']
                if isinstance(p, dict):
                    type_obj = p.get('type', {})
                    ptype = type_obj.get('name', '') if isinstance(type_obj, dict) else ''
            elif 'pass_type' in passes.columns:
                ptype = passes.loc[idx, 'pass_type'] or ''
            if ptype == 'Corner':
                corners += 1

        stats[team] = {
            'Goals': goals,
            'Total Shots': total_shots,
            'Shots on Target': shots_on_target,
            'Pass Completion': f"{pass_pct:.1f}%",
            'Total Passes': total_passes,
            'Fouls': total_fouls,
            'Yellow Cards': yellow_cards,
            'Red Cards': red_cards,
            'Corners': corners,
        }

    # Possession based on event duration
    if 'duration' in events.columns and 'possession_team' in events.columns:
        poss = events.groupby('possession_team')['duration'].sum()
        poss_total = poss.sum()
        for team in teams:
            poss_pct = (poss.get(team, 0) / poss_total * 100) if poss_total > 0 else 0
            stats[team]['Possession'] = f"{poss_pct:.1f}%"

    return stats


# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server  # Expose server for gunicorn
app.config['suppress_callback_exceptions'] = True

COLORS = {'background': '#F9F9F9'}

# Placeholder empty pitch - generated on-demand instead of at startup
EMPTY_PITCH_SRC = ''  # Will be populated on first use

def _get_empty_pitch():
    """Generate empty pitch image only when first needed."""
    global EMPTY_PITCH_SRC
    if not EMPTY_PITCH_SRC:
        _ensure_heavy_imports()
        _fig = plt.figure()
        _fig.set_size_inches(6.7 * 1.5, 6.7, forward=False)
        MPS.drawactionfield(ax=_fig.add_subplot(111), color='white', linecolor='lightgrey', show=False)
        plt.tight_layout()
        _buf = io.BytesIO()
        plt.savefig(_buf, format='png')
        EMPTY_PITCH_SRC = 'data:image/png;base64,{}'.format(
            base64.b64encode(_buf.getbuffer()).decode('utf8')
        )
        plt.close()
    return EMPTY_PITCH_SRC

def _get_pitch():
    """Generate interactive pitch figure only when first needed."""
    _ensure_heavy_imports()
    return field.drawfield()


# ─────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────

def _get_layout():
    """Generate layout with lazy-loaded competition names."""
    comp = _get_comp_data()
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
                                dcc.Tab(label='Goals', children=[
                                    html.Img(id='pitch3', src='',
                                             style={'maxWidth': '100%'})
                                ]),
                                dcc.Tab(label='xG Shot Map', children=[
                                    dcc.Graph(id='xg-shot-map', figure={}),
                                    html.Div(id='xg-summary', style={
                                        'display': 'flex', 'justifyContent': 'space-around',
                                        'padding': '10px', 'fontSize': '16px'
                                    })
                                ]),
                                dcc.Tab(label='Match Stats', children=[
                                    html.Div(id='match-stats-container',
                                             style={'padding': '20px'})
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

# Use lazy layout generation
app.layout = _get_layout


# ─────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────

@app.callback(Output('season', 'options'), Input('competition', 'value'))
def set_season_options(selected_comp):
    if not selected_comp:
        return []
    comp = _get_comp_data()
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
    comp = _get_comp_data()
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
    _ensure_heavy_imports()
    events = get_event_data(selected_match)
    lineups = get_lineup_data(selected_match)
    data = passingnetwork(selected_match, selected_team, events, lineups, 'Count')
    return 'data:image/png;base64,{}'.format(data)


@app.callback(Output('pitch3', 'src'), Input('match', 'value'))
def update_goals(selected_match):
    if not selected_match:
        return _get_empty_pitch()
    _ensure_heavy_imports()
    data = plotaction(selected_match, w=10, h=8, zoom=False)
    return 'data:image/png;base64,{}'.format(data)


@app.callback(
    Output('pitch1', 'figure'),
    [Input('player', 'value'), Input('actions', 'value'), Input('match', 'value')]
)
def update_player_figure(selected_player, selected_actions, selected_match):
    if not selected_player or not selected_match:
        return _get_pitch()

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


@app.callback(
    [Output('xg-shot-map', 'figure'),
     Output('xg-summary', 'children')],
    Input('match', 'value')
)
def update_xg_shot_map(selected_match):
    if not selected_match:
        return {}, []

    _ensure_heavy_imports()
    fig = field.drawfield()
    # Hide the base placeholder traces and their legend entries
    for trace in fig.data:
        trace.showlegend = False

    shot_df = get_xg_shot_data(selected_match)

    if shot_df.empty:
        return fig, [html.P("No shot data available for this match.")]

    teams = shot_df['team'].unique()
    summary_children = []

    for team in teams:
        team_shots = shot_df[shot_df['team'] == team]
        goals_df = team_shots[team_shots['is_goal']]
        misses_df = team_shots[~team_shots['is_goal']]

        total_xg = team_shots['xg'].sum()
        actual_goals = len(goals_df)

        if len(goals_df) > 0:
            fig.add_trace(go.Scatter(
                x=goals_df['x'], y=goals_df['y'],
                mode='markers',
                name=f'{team} - Goals',
                marker=dict(
                    color='green', size=goals_df['xg'] * 40 + 8,
                    symbol='circle',
                    line=dict(width=1, color='darkgreen'),
                    opacity=0.8
                ),
                hovertext=goals_df.apply(
                    lambda r: f"{r['player']}<br>{r['minute']}' - {r['shot_type']}<br>xG: {r['xg']:.2f}",
                    axis=1
                ),
                hoverinfo='text'
            ))

        if len(misses_df) > 0:
            fig.add_trace(go.Scatter(
                x=misses_df['x'], y=misses_df['y'],
                mode='markers',
                name=f'{team} - Missed/Saved',
                marker=dict(
                    color='red', size=misses_df['xg'] * 40 + 8,
                    symbol='x',
                    line=dict(width=1, color='darkred'),
                    opacity=0.6
                ),
                hovertext=misses_df.apply(
                    lambda r: f"{r['player']}<br>{r['minute']}' - {r['outcome']}<br>xG: {r['xg']:.2f}",
                    axis=1
                ),
                hoverinfo='text'
            ))

        summary_children.append(
            html.Div([
                html.B(team),
                html.P(f"xG: {total_xg:.2f} | Goals: {actual_goals}")
            ], style={'textAlign': 'center', 'padding': '10px',
                      'border': 'thin lightgrey solid', 'borderRadius': '5px',
                      'minWidth': '200px'})
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
    )

    return fig, summary_children


@app.callback(
    Output('match-stats-container', 'children'),
    Input('match', 'value')
)
def update_match_stats(selected_match):
    if not selected_match:
        return html.P("Select a match to view stats.", style={'textAlign': 'center', 'color': 'grey'})

    _ensure_heavy_imports()
    stats = get_match_stats(selected_match)
    teams = list(stats.keys())

    if len(teams) < 2:
        return html.P("Insufficient data for this match.")

    stat_keys = ['Possession', 'Goals', 'Total Shots', 'Shots on Target',
                 'Pass Completion', 'Total Passes', 'Fouls',
                 'Yellow Cards', 'Red Cards', 'Corners']

    header = html.Tr([
        html.Th(teams[0], style={'textAlign': 'center', 'width': '30%', 'fontSize': '18px',
                                  'padding': '12px', 'backgroundColor': '#f0f0f0'}),
        html.Th('', style={'width': '40%', 'backgroundColor': '#f0f0f0'}),
        html.Th(teams[1], style={'textAlign': 'center', 'width': '30%', 'fontSize': '18px',
                                  'padding': '12px', 'backgroundColor': '#f0f0f0'}),
    ])

    rows = [header]
    for key in stat_keys:
        val1 = stats[teams[0]].get(key, '-')
        val2 = stats[teams[1]].get(key, '-')
        rows.append(html.Tr([
            html.Td(str(val1), style={'textAlign': 'center', 'padding': '8px', 'fontSize': '16px'}),
            html.Td(key, style={'textAlign': 'center', 'fontWeight': 'bold', 'padding': '8px'}),
            html.Td(str(val2), style={'textAlign': 'center', 'padding': '8px', 'fontSize': '16px'}),
        ], style={'borderBottom': '1px solid #eee'}))

    return html.Table(rows, style={
        'width': '100%', 'borderCollapse': 'collapse',
        'border': 'thin lightgrey solid', 'marginTop': '10px'
    })


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
