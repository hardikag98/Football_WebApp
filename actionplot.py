# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
Rewritten: 2025 — uses StatsBomb API data on-the-fly instead of HDF5/SPADL.
"""
import warnings
import pandas as pd
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
import io
import base64
import MPS
import matplotlib.pyplot as plt


# Map StatsBomb event types to SPADL-style type names for MPS.actionsplot
_TYPE_MAP = {
    'Pass': 'pass',
    'Ball Receipt*': 'pass',
    'Carry': 'dribble',
    'Dribble': 'dribble',
    'Shot': 'shot',
    'Ball Recovery': 'pass',
    'Interception': 'pass',
    'Clearance': 'pass',
    'Pressure': 'pass',
    'Foul Won': 'pass',
    'Duel': 'pass',
    'Miscontrol': 'pass',
    'Goal Keeper': 'pass',
    'Block': 'pass',
    'Dispossessed': 'pass',
}


def _get_shot_outcome(row):
    """Extract shot outcome from StatsBomb event row, handling both dict and flat formats."""
    if 'shot' in row.index:
        shot_data = row['shot']
        if isinstance(shot_data, dict):
            outcome = shot_data.get('outcome', {})
            return outcome.get('name', '') if isinstance(outcome, dict) else str(outcome)
    if 'shot_outcome' in row.index:
        val = row['shot_outcome']
        if pd.notna(val):
            return str(val)
    return ''


def _get_end_location(row):
    """Extract end location from a StatsBomb event row, trying multiple column sources."""
    # Try type-specific end locations first
    for col in ('pass_end_location', 'carry_end_location', 'shot_end_location'):
        if col in row.index:
            val = row[col]
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                return val[0], val[1]

    # Try nested dict format
    for key in ('pass', 'carry', 'shot'):
        if key in row.index and isinstance(row[key], dict):
            end_loc = row[key].get('end_location')
            if isinstance(end_loc, (list, tuple)) and len(end_loc) >= 2:
                return end_loc[0], end_loc[1]

    # Fallback: use start location (action stays in place)
    loc = row.get('location')
    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
        return loc[0], loc[1]
    return None, None


def _nice_time(row):
    """Format time as 'Xm Ys' from minute/second columns."""
    minute = int(row.get('minute', 0))
    second = int(row.get('second', 0))
    return f"{minute}m{second}s"


def plotaction(match_id, events=None, number=5, w=10, h=8, zoom=False):
    """
    Plot goal sequences using StatsBomb event data.

    For each goal in the match, shows the N preceding actions on a pitch.

    Parameters
    ----------
    match_id : int
        StatsBomb match ID.
    events : DataFrame, optional
        Pre-fetched event data. If None, a placeholder is shown.
    number : int
        Number of actions before the goal to display (default 5).
    w, h : int
        Figure width and base height per goal subplot.
    zoom : bool
        Whether to zoom into the action area.

    Returns
    -------
    str
        Base64-encoded PNG image.
    """
    if events is None:
        # No events provided — show placeholder
        fig = plt.figure()
        fig.set_size_inches(6.7 * 1.5, 6.7, forward=False)
        MPS.drawactionfield(
            ax=fig.add_subplot(111),
            color='white', linecolor='lightgrey', show=False,
            title="Select a match to view goal sequences"
        )
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        data = base64.b64encode(buf.getbuffer()).decode("utf8")
        plt.close()
        return data

    # ── Identify teams ──
    teams = events['team'].dropna().unique().tolist()
    if len(teams) >= 2:
        hometeam, awayteam = teams[0], teams[1]
    else:
        hometeam = teams[0] if teams else "Home"
        awayteam = "Away"

    # ── Find all goals ──
    shot_events = events[events['type'] == 'Shot'].copy()
    goal_indices = []
    for idx in shot_events.index:
        outcome = _get_shot_outcome(shot_events.loc[idx])
        if outcome == 'Goal':
            goal_indices.append(idx)

    if len(goal_indices) == 0:
        fig = plt.figure()
        fig.set_size_inches(6.7 * 1.5, 6.7, forward=False)
        MPS.drawactionfield(
            ax=fig.add_subplot(111), color='white',
            linecolor='lightgrey', show=False,
            title="Match ended goalless!"
        )
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        data = base64.b64encode(buf.getbuffer()).decode("utf8")
        plt.close()
        return data

    # ── Build figure with one subplot per goal ──
    num_goals = len(goal_indices)
    total_h = h * num_goals
    fig = plt.figure()
    fig.set_size_inches(w, total_h, forward=False)

    homescore = 0
    awayscore = 0

    # Get positional index of each row for slicing preceding actions
    idx_list = events.index.tolist()

    for goal_num, goal_idx in enumerate(goal_indices, start=1):
        # Determine which team scored
        goal_row = events.loc[goal_idx]
        scoring_team = goal_row.get('team', '')

        # Get goal location to determine direction (home attacks right: x > 60)
        goal_loc = goal_row.get('location', [0, 0])
        if isinstance(goal_loc, (list, tuple)) and len(goal_loc) >= 2:
            if goal_loc[0] > 60:
                # Shot towards right goal — home team convention
                if scoring_team == hometeam:
                    homescore += 1
                else:
                    awayscore += 1
            else:
                if scoring_team == awayteam:
                    awayscore += 1
                else:
                    homescore += 1
        else:
            # Fallback: just use team name
            if scoring_team == hometeam:
                homescore += 1
            else:
                awayscore += 1

        # Get preceding N actions + the goal itself
        pos = idx_list.index(goal_idx)
        start_pos = max(0, pos - number)
        action_indices = idx_list[start_pos:pos + 1]
        actions = events.loc[action_indices].copy()

        # Filter to only events with locations (skip events like Half Start, etc.)
        actions = actions[actions['location'].apply(
            lambda x: isinstance(x, (list, tuple)) and len(x) >= 2
        )].copy()

        if len(actions) == 0:
            continue

        # Build SPADL-like columns for MPS.actionsplot
        start_x = []
        start_y = []
        end_x = []
        end_y = []
        type_names = []
        team_names = []
        result_flags = []
        nice_times = []
        player_names = []

        for i in actions.index:
            row = actions.loc[i]
            loc = row['location']
            sx, sy = loc[0], loc[1]

            ex, ey = _get_end_location(row)
            if ex is None:
                ex, ey = sx, sy

            start_x.append(sx)
            start_y.append(sy)
            end_x.append(ex)
            end_y.append(ey)

            sb_type = str(row.get('type', 'pass'))
            type_names.append(_TYPE_MAP.get(sb_type, 'pass'))
            team_names.append(str(row.get('team', '')))
            nice_times.append(_nice_time(row))
            player_names.append(str(row.get('player', '')))

            # Determine success: passes with no outcome are successful,
            # shots with Goal outcome are successful
            if sb_type == 'Shot':
                result_flags.append(_get_shot_outcome(row) == 'Goal')
            elif sb_type == 'Pass':
                pass_outcome = None
                if 'pass_outcome' in row.index:
                    pass_outcome = row['pass_outcome']
                elif 'pass' in row.index and isinstance(row['pass'], dict):
                    pass_outcome = row['pass'].get('outcome')
                result_flags.append(pd.isna(pass_outcome) if not isinstance(pass_outcome, dict) else pass_outcome is None)
            else:
                result_flags.append(True)

        location_df = pd.DataFrame({
            'start_x': start_x, 'start_y': start_y,
            'end_x': end_x, 'end_y': end_y
        })
        labels = pd.DataFrame({
            'nice_time': nice_times,
            'type_name': type_names,
            'player': player_names,
            'team_name': team_names
        })

        MPS.actionsplot(
            location=location_df[['start_x', 'start_y', 'end_x', 'end_y']],
            action_type=pd.Series(type_names),
            team=pd.Series(team_names),
            title=f"{hometeam} {homescore} - {awayscore} {awayteam}",
            result=pd.Series(result_flags),
            label=labels,
            figsize=(w, total_h),
            labeltitle=["time", "actiontype", "player", "team"],
            zoom=zoom,
            color='white',
            linecolor="lightgrey",
            legloc='top',
            show=False,
            ax=fig.add_subplot(num_goals, 1, goal_num)
        )

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close()
    return data
