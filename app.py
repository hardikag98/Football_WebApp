# -*- coding: utf-8 -*-
"""
Football Analytics Dashboard
Author: Hardy Agarwal
Refactored: 2025 — removed VAEP/DB dependencies, simplified for Render deployment
"""

import matplotlib
matplotlib.use('Agg')

from statsbombpy import sb
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import functools
import io
import base64
import matplotlib.pyplot as plt

import field
import MPS
from graph import passingnetwork
from actionplot import plotaction


# ─────────────────────────────────────────────
# DATA HELPERS (cached for performance)
# ─────────────────────────────────────────────

@functools.lru_cache(maxsize=20)
def get_event_data(match_id):
    """Fetch and lightly process StatsBomb event data for a match."""
    events = sb.events(match_id=match_id)
    events['timestamp'] = pd.to_datetime(events['timestamp']).dt.time
    return events


@functools.lru_cache(maxsize=20)
def get_lineup_data(match_id):
    """Fetch StatsBomb lineup data for a match."""
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

        # Possession: count of events as proxy
        possession_events = len(te)

        # Goals
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

        # Passes
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

        # Fouls
        fouls = len(te[te['type'] == 'Foul Committed'])

        # Cards
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

    # Calculate possession %
    total_events = sum(s['possession_events'] for s in stats.values())
    for team in stats:
        stats[team]['possession'] = round(100 * stats[team]['possession_events'] / total_events, 1) if total_events > 0 else 0

    return teams, stats


@functools.lru_cache(maxsize=20)
def get_player_data(match_id, player_name):
    """
    Build all visualisation data for a single player in a match.
    Returns pitch figure + pass/shot/tackle/heatmap data.
    """
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

    shots = pd.DataFrame({'x1': sx1, 'y1': sy1, 'Colors': scolors, 'Time': stime, 'xG': sxg, 'Outcome': soutcome_list})
    shots['Hoverinfo'] = shots.apply(
        lambda r: f"Time: {r['Time']}<br>xG: {r['xG']}<br>Outcome: {r['Outcome']}" if r['Time'] != '00:00' else '',
        axis=1
    )

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

comp = pd.read_csv('games.csv')
compname = comp['competition_name'].unique()

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server  # Expose server for gunicorn
app.config['suppress_callback_exceptions'] = True

COLORS = {'background': '#F9F9F9'}

# Generate empty pitch image for initial tab display
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

pitch = field.drawfield()


# ─────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────

app.layout = html.Div(
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
                                html.Img(id='pitch2', src=EMPTY_PITCH_SRC,
                                         style={'maxWidth': '100%'}),
                                html.P(
                                    'Passing network for the starting lineup. '
                                    'Only successful passes before the first substitution '
                                    'or red card are shown. Node size = number of passes.'
                                )
                            ]),
                            dcc.Tab(label='Player Analysis', children=[
                                dcc.Graph(id='pitch1', figure=pitch)
                            ]),
                            dcc.Tab(label='Goals', children=[
                                html.Img(id='pitch3', src=EMPTY_PITCH_SRC,
                                         style={'maxWidth': '100%'})
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


# ─────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────

@app.callback(Output('season', 'options'), Input('competition', 'value'))
def set_season_options(selected_comp):
    if not selected_comp:
        return []
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
        return EMPTY_PITCH_SRC
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


@app.callback(Output('pitch3', 'src'), Input('match', 'value'))
def update_goals(selected_match):
    if not selected_match:
        return EMPTY_PITCH_SRC
    events = get_event_data(selected_match)
    data = plotaction(selected_match, events=events, w=10, h=8, zoom=False)
    return 'data:image/png;base64,{}'.format(data)


@app.callback(
    Output('pitch1', 'figure'),
    [Input('player', 'value'), Input('actions', 'value'), Input('match', 'value')]
)
def update_player_figure(selected_player, selected_actions, selected_match):
    if not selected_player or not selected_match:
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


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
