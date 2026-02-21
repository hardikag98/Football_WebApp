# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
Refactored: 2025 — updated for current statsbombpy flat column format
"""

import matplotlib.pyplot as plt
from passing_network import draw_pitch, draw_pass_map
from MPS import drawactionfield
import io
import base64
import pandas as pd
import os


def _statsbomb_to_point(location, max_width=120, max_height=80):
    '''
    Convert a point's coordinates from a StatsBomb's range to 0-1 range.
    '''
    return location[0] / max_width, 1 - (location[1] / max_height)


def passingnetwork(match_id, teamname, events, lineups, passvalue='count'):
    # Build names dict from lineups
    names_dict = {player[1]["player_name"]: player[1]["player_name"]
                  for team in lineups for player in lineups[team].iterrows()}

    df_events = events.copy()

    # Determine cutoff minute (first sub or red card)
    try:
        # Current statsbombpy uses 'foul_committed_card' (string), not 'foul_committed_card_name'
        card_col = 'foul_committed_card' if 'foul_committed_card' in df_events.columns else 'foul_committed_card_name'
        first_red_card_minute = df_events[df_events[card_col].isin(
            ["Second Yellow", "Red Card"])]['minute'].min()
    except (KeyError, AttributeError):
        first_red_card_minute = 200
    try:
        first_substitution_minute = df_events[df_events['type'] == "Substitution"]['minute'].min()
    except (KeyError, AttributeError):
        first_substitution_minute = 200
    max_minute = df_events['minute'].max()
    num_minutes = min(first_substitution_minute, first_red_card_minute, max_minute)

    # Filter passes by this team before cutoff
    pass_events = df_events[
        (df_events['type'] == 'Pass') &
        (df_events['team'] == teamname) &
        (df_events['minute'] < num_minutes)
    ].copy()

    # Current statsbombpy: 'pass_outcome' (string) and 'pass_recipient' (string)
    # Successful passes have NaN in pass_outcome
    if 'pass_outcome' in pass_events.columns:
        outcome_col = pass_events['pass_outcome']
    elif 'pass_outcome_name' in pass_events.columns:
        outcome_col = pass_events['pass_outcome_name']
    else:
        outcome_col = pd.Series([None] * len(pass_events), index=pass_events.index)

    if 'pass_recipient' in pass_events.columns:
        recipient_col = pass_events['pass_recipient']
    elif 'pass_recipient_name' in pass_events.columns:
        recipient_col = pass_events['pass_recipient_name']
    else:
        recipient_col = pd.Series([None] * len(pass_events), index=pass_events.index)

    # Keep only successful passes (outcome is NaN) with a known recipient
    df_passes = pass_events[
        outcome_col.isna() & recipient_col.notna()
    ].copy()

    # Create clean player_name and pass_recipient_name columns
    # Drop any pre-existing ones to avoid duplicates
    for col in ['player_name', 'pass_recipient_name']:
        if col in df_passes.columns:
            df_passes = df_passes.drop(columns=[col])

    df_passes["pass_recipient_name"] = recipient_col[df_passes.index].apply(
        lambda x: names_dict.get(x, x) if x else x)
    df_passes["player_name"] = df_passes['player'].apply(
        lambda x: names_dict.get(x, x) if x else x)

    df_passes["origin_pos_x"] = df_passes['location'].apply(lambda x: _statsbomb_to_point(x)[0])
    df_passes["origin_pos_y"] = df_passes['location'].apply(lambda x: _statsbomb_to_point(x)[1])

    player_position = df_passes.groupby("player_name").agg({
        "origin_pos_x": "median",
        "origin_pos_y": "median"
    })

    if passvalue == 'Count':
        player_pass_count = df_passes.groupby("player_name").size().to_frame("num_passes")
        player_pass_value = df_passes.groupby("player_name").size().to_frame("pass_value")

        df_passes["pair_key"] = df_passes.apply(
            lambda x: "_".join(sorted([x["player_name"], x["pass_recipient_name"]])), axis=1)

        pair_pass_count = df_passes.groupby("pair_key").size().to_frame("num_passes")
        pair_pass_value = df_passes.groupby("pair_key").size().to_frame("pass_value")
        plot_legend = "Location: Pass origin\nSize: Number of passes\nColor: Number of passes"
    else:
        # VAEP path (currently disabled, kept for future use)
        df_result = df_passes[['period', "timestamp", "player_name", "pass_recipient_name", 'vaep_value']]
        df_result["vaep_value"] = df_result.vaep_value.apply(lambda x: x if x >= 0 else None)

        player_pass_count = df_result.groupby("player_name").size().to_frame("num_passes")
        player_pass_value = df_result.groupby("player_name").agg(pass_value=("vaep_value", "mean"))

        df_result["pair_key"] = df_result.apply(
            lambda x: "_".join(sorted([x["player_name"], x["pass_recipient_name"]])), axis=1)
        pair_pass_value = df_result.groupby("pair_key").agg(pass_value=("vaep_value", "mean"))
        pair_pass_count = df_result.groupby("pair_key").size().to_frame("num_passes")
        pair_pass_value[pair_pass_value.pass_value.isnull()] = pair_pass_value.pass_value.min() * 0.9
        plot_legend = "Location: Pass origin\nSize: Number of passes\nColor: Pass value (VAEP)"

    ax = draw_pitch()
    ax = draw_pass_map(ax, player_position, player_pass_count, player_pass_value,
                       pair_pass_count, pair_pass_value, title='', legend=plot_legend)
    fig = ax.figure
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close(fig)
    return data
