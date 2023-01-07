# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
"""

#from statsbombpy import sb
import matplotlib.pyplot as plt 
from passing_network import draw_pitch, draw_pass_map
from MPS import drawactionfield
import matplotlib.pyplot as plt
import io
import base64
from pandas import json_normalize
import pandas as pd
#import socceraction.vaep as vaep
import os
#%%
def _statsbomb_to_point(location, max_width=120, max_height=80):
    '''
    Convert a point's coordinates from a StatsBomb's range to 0-1 range.
    '''
    return location[0] / max_width, 1-(location[1] / max_height)

#%%
def passingnetwork(match_id,teamname,events,lineups,passvalue='count'):
    names_dict = {player[1]["player_name"]: player[1]["player_nickname"] for 
                  team in lineups for player in lineups[team].iterrows()}
    eventsdict = events.to_dict('records')
    df_events = json_normalize(eventsdict, sep="_").assign(match_id=match_id)

    try:
        first_red_card_minute = df_events[df_events.foul_committed_card_name.isin(
            ["Second Yellow", "Red Card"])].minute.min()
    except:
        first_red_card_minute = 200
    try:
        first_substitution_minute = df_events[df_events.type == "Substitution"].minute.min()
    except:
        first_substitution_minute = 200
    max_minute = df_events.minute.max()
    num_minutes = min(first_substitution_minute, first_red_card_minute, max_minute)
    
    #plot_name = "statsbomb_match{0}_{1}".format(match_id, teamname)
    #opponent_team = [x for x in df_events.team.unique() if x != teamname][0]
    #plot_title ="{0}'s passing network against {1}".format(teamname, opponent_team)
    #plot_legend = "Location: pass origin\nSize: number of passes\nColor: number of passes"
    
    df_passes = df_events[(df_events.type == "Pass") &
                          (df_events.pass_outcome_name.isna()) &
                          (df_events.team == teamname) &
                          (df_events.minute < num_minutes)].copy()
    # If available, use player's nickname instead of full name to optimize space in plot
    #df_passes["player_name"] = df_passes.apply(lambda x: x["nickname"] if x["nickname"] else x["player_name"], axis=1)
    df_passes["pass_recipient_name"] = df_passes.pass_recipient_name.apply(lambda x: 
                                                    names_dict[x] if names_dict[x] else x)
    df_passes["player_name"] = df_passes.player.apply(lambda x: names_dict[x] if names_dict[x] else x)
    
    df_passes["origin_pos_x"] = df_passes.location.apply(lambda x: _statsbomb_to_point(x)[0])
    df_passes["origin_pos_y"] = df_passes.location.apply(lambda x: _statsbomb_to_point(x)[1])
    player_position = df_passes.groupby("player_name").agg({"origin_pos_x": "median", 
                                       "origin_pos_y": "median"})
    
    if passvalue=='Count':
        player_pass_count = df_passes.groupby("player_name").size().to_frame("num_passes")
        player_pass_value = df_passes.groupby("player_name").size().to_frame("pass_value")
        
        df_passes["pair_key"] = df_passes.apply(lambda x: "_".join(sorted([x["player_name"], 
                                                                    x["pass_recipient_name"]])), axis=1)
        pair_pass_count = df_passes.groupby("pair_key").size().to_frame("num_passes")
        pair_pass_value = df_passes.groupby("pair_key").size().to_frame("pass_value")
        plot_legend = "Location: Pass origin\nSize: Number of passes\nColor: Number of passes"

    else:
        ## IMPORT SAVED VAEP VALUES
        #df_vaep = pd.read_hdf(os.path.join("data-fifa", "vaeptime.h5"), "game_{0}".format(match_id))

        #df_passes.timestamp = pd.to_datetime(df_passes.timestamp)
        #df_passes.timestamp = df_passes.timestamp.dt.time

        #df_vaep.timestamp = df_vaep.timestamp.dt.time

        # Set the VAEP metric to each pass
        #df_result = pd.merge(df_passes[['period',"timestamp", "player_name", "pass_recipient_name"]], 
        #                    df_vaep, left_on=['period','timestamp'], right_on=['period_id','timestamp'],how="left")
        df_result = df_passes[['period',"timestamp", "player_name", "pass_recipient_name", 'vaep_value']]
        
        df_result["vaep_value"]  = df_result.vaep_value.apply(lambda x: x if x >= 0 else None)  # Filter out negative actions

        # Aggregate number of passes and VAEP metric for each player
        player_pass_count = df_result.groupby("player_name").size().to_frame("num_passes")
        player_pass_value = df_result.groupby("player_name").agg(pass_value=("vaep_value", "mean"))

        # 'pair_key' combines the names of the passer and receiver of each pass (sorted alphabetically)
        df_result["pair_key"] = df_result.apply(lambda x: "_".join(sorted([x["player_name"], x["pass_recipient_name"]])), axis=1)
        pair_pass_value = df_result.groupby("pair_key").agg(pass_value=("vaep_value", "mean"))
        pair_pass_count = df_result.groupby("pair_key").size().to_frame("num_passes")

        pair_pass_value[pair_pass_value.pass_value.isnull()] = pair_pass_value.pass_value.min() * 0.9

        plot_legend = "Location: Pass origin\nSize: Number of passes\nColor: Pass value (VAEP)"
    
    
    ax = draw_pitch()
    ax = draw_pass_map(ax, player_position, player_pass_count, player_pass_value,
                  pair_pass_count, pair_pass_value, title='',legend=plot_legend)
    #plt.savefig("demo/{0}.png".format(plot_name))
    buf = io.BytesIO()
    plt.savefig(buf, format = "png")
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close()
    return data 

#%% Testing passingnetwork function 