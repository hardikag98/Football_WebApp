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
from statsbombpy import sb as _sb


# StatsBomb event types that correspond to SPADL actions.
# These are the only types that exist in the main branch's SPADL HDF5 data,
# plus fouls/tackles/handball for richer goal-sequence context.
_SPADL_TYPES = {
    'Pass', 'Carry', 'Dribble', 'Shot', 'Interception',
    'Clearance', 'Miscontrol', 'Goal Keeper',
    'Block', 'Foul Committed', 'Tackle', 'Bad Behaviour',
}

# Map StatsBomb event types to SPADL-style type names for MPS.actionsplot
_TYPE_MAP = {
    'Pass': 'pass',
    'Carry': 'dribble',
    'Dribble': 'dribble',
    'Shot': 'shot',
    'Interception': 'interception',
    'Clearance': 'clearance',
    'Miscontrol': 'miscontrol',
    'Goal Keeper': 'save',
    'Block': 'block',
    'Foul Committed': 'foul',
    'Tackle': 'tackle',
    'Bad Behaviour': 'handball',
}

# MPS.actionsplot applies scaling factors (1.1428x, 1.1765x) to convert
# from SPADL's 105x68 pitch to the 120x80 display. StatsBomb data is
# already in 120x80, so we need to scale DOWN before passing to actionsplot.
_SB_TO_SPADL_X = 105.0 / 120.0  # ≈ 0.875
_SB_TO_SPADL_Y = 68.0 / 80.0    # ≈ 0.85


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


def plotaction(match_id, events=None, number=5, w=10, h=8, zoom=False, shot_idx=None):
    if events is None:
        # No events provided — show placeholder
        fig = plt.figure()
        fig.set_size_inches(6.7 * 1.5, 6.7, forward=False)
        ax = fig.add_subplot(111)
        MPS.drawactionfield(
            ax=ax,
            color='white', linecolor='lightgrey', show=False,
            title="Select a match to view goal sequences"
        )
        ax.axis('off')
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight')
        data = base64.b64encode(buf.getbuffer()).decode("utf8")
        plt.close(fig)
        return data

    # ── Sort events chronologically ──
    # Sort by period, minute, second to ensure correct chronological order.
    # Preserve original index for lookup
    if 'index' in events.columns:
        events = events.sort_values('index')
    else:
        events = events.sort_values(['period', 'minute', 'second'], ascending=True)
    
    # Store original index before reset for shot_idx lookup
    events['original_index'] = events.index
    events = events.reset_index(drop=True)

    # ── Build nickname lookup from lineups ──
    _nickname_map = {}
    try:
        lineups = _sb.lineups(match_id=match_id)
        for _team_name, roster in lineups.items():
            for _, p in roster.iterrows():
                full = p.get('player_name', '')
                nick = p.get('player_nickname')
                if nick and str(nick) not in ('None', 'nan', ''):
                    _nickname_map[full] = str(nick)
    except Exception:
        pass  # graceful fallback — use full names

    # ── Identify teams (before filtering) ──
    teams = events['team'].dropna().unique().tolist()
    if len(teams) >= 2:
        hometeam, awayteam = teams[0], teams[1]
    else:
        hometeam = teams[0] if teams else "Home"
        awayteam = "Away"

    # ── Filter to SPADL-equivalent actions with valid locations ──
    # Main branch uses SPADL data which only contains specific action types.
    # We must filter to the same types to get matching preceding-action slices.
    # Also exclude penalty shootout (period 5).
    spadl_actions = events[
        (events['type'].isin(_SPADL_TYPES)) &
        (events['location'].apply(lambda x: isinstance(x, (list, tuple)) and len(x) >= 2)) &
        (events['period'] < 5)
    ].copy()
    # Remove passive GK events (observations, not actual plays)
    _PASSIVE_GK = {'Shot Faced', 'Goal Conceded', 'Penalty Conceded'}
    spadl_actions = spadl_actions[
        ~((spadl_actions['type'] == 'Goal Keeper') &
          (spadl_actions['goalkeeper_type'].isin(_PASSIVE_GK) if 'goalkeeper_type' in spadl_actions.columns else False))
    ]
    spadl_actions = spadl_actions.reset_index(drop=True)

    # ── Find all goals (or specific shot_idx) ──
    if shot_idx is not None:
        # Find the index in spadl_actions that matches the original event index
        match = spadl_actions[spadl_actions['original_index'] == shot_idx]
        if not match.empty:
            goal_indices = [match.index[0]]
        else:
            goal_indices = []
    else:
        shot_events = spadl_actions[spadl_actions['type'] == 'Shot'].copy()
        goal_indices = []
        for idx in shot_events.index:
            outcome = _get_shot_outcome(shot_events.loc[idx])
            if outcome == 'Goal':
                goal_indices.append(idx)

    if len(goal_indices) == 0:
        fig = plt.figure()
        fig.set_size_inches(6.7 * 1.5, 6.7, forward=False)
        ax = fig.add_subplot(111)
        MPS.drawactionfield(
            ax=ax, color='white',
            linecolor='lightgrey', show=False,
            title="Match ended goalless!"
        )
        ax.set_axis_off()
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight')
        data = base64.b64encode(buf.getbuffer()).decode("utf8")
        plt.close(fig)
        return data

    # ── Build figure with one subplot per goal ──
    num_goals = len(goal_indices)
    
    # Adjust sizing for single trace
    if shot_idx is not None:
        fig_w, fig_h = w, h
    else:
        fig_w, fig_h = w, h * num_goals
        
    fig = plt.figure()
    fig.set_size_inches(fig_w, fig_h, forward=False)

    for goal_num, current_shot_idx in enumerate(goal_indices, start=1):
        # ── Score calculation (at the moment of the shot) ──
        # We need the score BEFORE this shot happened.
        current_shots_so_far = spadl_actions.iloc[:current_shot_idx]
        current_goals_so_far = 0
        h_score, a_score = 0, 0
        
        # Count goals in all actions BEFORE this one
        for _, r in current_shots_so_far[current_shots_so_far['type'] == 'Shot'].iterrows():
            if _get_shot_outcome(r) == 'Goal':
                if str(r.get('team', '')) == hometeam: h_score += 1
                else: a_score += 1

        goal_row = spadl_actions.loc[current_shot_idx]
        scoring_team = str(goal_row.get('team', ''))
        outcome = _get_shot_outcome(goal_row)
        
        # If this is a goal, the display should show the score AFTER it's scored
        display_h, display_a = h_score, a_score
        if outcome == 'Goal':
            if scoring_team == hometeam: display_h += 1
            else: display_a += 1
        
        # Title logic
        player_name = str(goal_row.get('player', ''))
        player_nick = _nickname_map.get(player_name, player_name)
        time_str = _nice_time(goal_row)
        
        if shot_idx is not None:
            # Hover-to-trace preview
            status = "GOAL" if outcome == 'Goal' else "ATTEMPT"
            header = f"[{status}] {player_nick} ({time_str})"
        else:
            # Static goals tab
            header = f"Goal {goal_num}: {player_nick} ({time_str})"

        # ── Helper: normalise coords to scoring-team reference frame ──
        def _normalise(x, y, team):
            """Flip opposing-team coords so everything is in scoring-team's frame."""
            if team != scoring_team:
                return 120.0 - x, 80.0 - y
            return x, y

        def _row_coords(row):
            """Return (sx, sy, ex, ey) normalised to scoring-team frame."""
            loc = row['location']
            team = str(row.get('team', ''))
            sx, sy = _normalise(loc[0], loc[1], team)
            ex, ey = _get_end_location(row)
            if ex is None:
                ex, ey = loc[0], loc[1]
            ex, ey = _normalise(ex, ey, team)
            return sx, sy, ex, ey

        # ── Walk backward from goal, picking preceding actions ──
        # We take the N preceding on-ball actions. 
        chain = [current_shot_idx]
        # Track timestamps of selected events to skip simultaneous technical artifacts
        chain_timestamps = {(int(goal_row.get('minute', 0)), int(goal_row.get('second', 0)))}

        search_start = max(0, current_shot_idx - 50)  # look-back window
        for candidate_idx in range(current_shot_idx - 1, search_start - 1, -1):
            if len(chain) > number:
                break
            cand = spadl_actions.loc[candidate_idx]
            
            # 1. Skip trivial carries/dribbles (< 1 yard movement)
            cand_type = str(cand.get('type', ''))
            if cand_type in ('Carry', 'Dribble'):
                csx, csy, cex_c, cey_c = _row_coords(cand)
                carry_dist = ((cex_c - csx) ** 2 + (cey_c - csy) ** 2) ** 0.5
                if carry_dist < 1.0:
                    continue
            
            # 2. Skip simultaneous technical artifacts (Block, Goal Keeper) 
            # if we already have a primary action at this timestamp.
            cand_ts = (int(cand.get('minute', 0)), int(cand.get('second', 0)))
            if cand_ts in chain_timestamps and cand_type in ('Block', 'Goal Keeper'):
                continue
                
            # No spatial filtering - just take the action
            chain.append(candidate_idx)
            chain_timestamps.add(cand_ts)

        chain.reverse()
        actions = spadl_actions.loc[chain].copy()

        if len(actions) == 0:
            continue

        # ── Build SPADL-like columns for MPS.actionsplot ──
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
            sx, sy, ex, ey = _row_coords(row)

            # StatsBomb coordinates are already 120x80, no scaling needed
            start_x.append(sx)
            start_y.append(sy)
            end_x.append(ex)
            end_y.append(ey)

            sb_type = str(row.get('type', 'pass'))
            # Distinguish penalties from open-play shots
            if sb_type == 'Shot' and str(row.get('shot_type', '')) == 'Penalty':
                type_names.append('penalty')
            elif sb_type == 'Goal Keeper':
                gk_type = str(row.get('goalkeeper_type', ''))
                type_names.append(gk_type.lower() if gk_type else 'save')
            else:
                type_names.append(_TYPE_MAP.get(sb_type, 'pass'))
            team_names.append(str(row.get('team', '')))
            nice_times.append(_nice_time(row))
            # Use nickname from lineups, fall back to full name
            full_name = str(row.get('player', ''))
            player_names.append(_nickname_map.get(full_name, full_name))

            # Determine success
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
            title=f"{header} | {hometeam} {display_h} - {display_a} {awayteam}",
            result=pd.Series(result_flags),
            label=labels,
            figsize=(fig_w, fig_h),
            labeltitle=["time", "actiontype", "player", "team"],
            zoom=zoom,
            color='white',
            linecolor="lightgrey",
            legloc='top',
            show=False,
            ax=fig.add_subplot(num_goals, 1, goal_num)
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight')
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close(fig)
    return data
