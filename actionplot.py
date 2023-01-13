# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
"""
import os;
import warnings
import pandas as pd
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
import io
import base64
import socceraction.spadl as spadl
import socceraction.spadl.statsbomb as statsbomb
import MPS 
import matplotlib.pyplot as plt

datafolder = os.getcwd() + "/data-fifa"
spadl_h5 = os.path.join(datafolder, "spadl-statsbomb.h5")
#%%

def nice_time(row):
    minute = int((row.period_id-1)*45 +row.time_seconds // 60)
    second = int(row.time_seconds % 60)
    return f"{minute}m{second}s"

def plotaction(match_id,number=5,w=1,h=1,zoom=False):
    #with h5py.File(spadl_h5, "r") as spadlstore:
    with pd.HDFStore(spadl_h5) as spadlstore:
        games = (
            spadlstore["games"]
            .merge(spadlstore["competitions"], how='left')
            .merge(spadlstore["teams"].add_prefix('home_'), how='left')
            .merge(spadlstore["teams"].add_prefix('away_'), how='left'))
        game = games[games.game_id==match_id]
        #try:
        hometeam = game.home_team_name.values[0]
        awayteam = game.away_team_name.values[0]

        actions = spadlstore[f"actions/game_{match_id}"]
        actions = (
            actions.merge(spadl.actiontypes_df(), how="left")
                .merge(spadl.results_df(), how="left")
                .merge(spadl.bodyparts_df(), how="left")
                .merge(spadlstore["players"], how="left")
                .merge(spadlstore["teams"], how="left")
                )
    
    # use nickname if available else use full name
    actions["player"] = actions[["nickname","player_name"]].apply(
            lambda x: x[0] if x[0] else x[1],axis=1)
    
    goalindex=actions[(actions.type_name=='shot')|(actions.type_name=='shot_penalty')][(actions.result_name=='success')|(actions.result_name=='owngoal')].index
    if len(goalindex)==0:
        fig=plt.figure()
        fig.set_size_inches(6.7*1.5,6.7,forward=False)
        MPS.drawactionfield(ax=fig.add_subplot(111),color='white',linecolor='lightgrey',show=False,title="Match ended goalless!")
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format = "png")
        data = base64.b64encode(buf.getbuffer()).decode("utf8")
        plt.close()
        return data
    goal=1
    h=h*len(goalindex)
    fig=plt.figure()
    fig.set_size_inches(w,h,forward=False)
    homescore = 0
    awayscore = 0
    for shot in goalindex:
        a = actions[shot-number:shot+1].copy()
        if a.iloc[-1,:].end_x>60:
            homescore += 1 
        else:
            awayscore += 1 
        
        a["nice_time"] = a.apply(nice_time,axis=1)
        labels = a[["nice_time", "type_name", "player", "team_name"]]
        MPS.actionsplot(
            location=a[["start_x", "start_y", "end_x", "end_y"]],
            action_type=a.type_name, team= a.team_name,
            title=f"{hometeam} {homescore} - {awayscore} {awayteam}",
            result= a.result_name == "success",
            label=labels,figsize=(w,h),
            labeltitle=["time","actiontype","player","team"],
            zoom=zoom, color='white', 
            linecolor="lightgrey", legloc='top',
            show=False,ax=fig.add_subplot(len(goalindex),1,goal)
        )
        goal += 1   
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format = "png")
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close()
    return data
