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
    global _heavy_imports_loaded, sb, pd, io, base64, plt, matplotlib
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


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
