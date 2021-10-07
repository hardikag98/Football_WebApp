import os;
import warnings
import pandas as pd
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
import io
import base64
import socceraction.spadl as spadl
import socceraction.spadl.statsbomb as statsbomb
import matplotsoccer
import matplotlib.pyplot as plt

datafolder = os.getcwd() + "/data-fifa"
spadl_h5 = os.path.join(datafolder, "spadl-statsbomb.h5")

#Print time in easy to read format
def nice_time(row):
    minute = int((row.period_id-1)*45 +row.time_seconds // 60)
    second = int(row.time_seconds % 60)
    return f"{minute}m{second}s"

#Plot actions in lead up to goals
def plotaction(match_id,number=5,w=1,h=1,zoom=False):
    with pd.HDFStore(spadl_h5) as spadlstore:
        games = spadlstore["games"].merge(spadlstore["competitions"])
        game = games[games.game_id==match_id]
        hometeam = game.home_team_name.values[0]
        awayteam = game.away_team_name.values[0]
        actions = spadlstore[f"actions/game_{match_id}"]
        actions = (
            actions.merge(spadlstore["actiontypes"],how="left")
            .merge(spadlstore["results"],how="left")
            .merge(spadlstore["bodyparts"],how="left")
            .merge(spadlstore["players"],how="left")
            .merge(spadlstore["teams"],how="left")
        )
    
    # use nickname if available else use full name
    actions["player"] = actions[["player_nickname","player_name"]].apply(
            lambda x: x[0] if x[0] else x[1],axis=1)
    
    goalindex=actions[(actions.type_name=='shot')|(actions.type_name=='shot_penalty')][(actions.result_name=='success')|(actions.result_name=='owngoal')].index
    goal=1
    h=h*len(goalindex)
    fig=plt.figure()
    fig.set_size_inches(w,h,forward=True)
    homescore = 0
    awayscore = 0
    for shot in goalindex:
        a = actions[shot-number:shot+1].copy()
        if a.iloc[-1,:].end_x>52.5:
            homescore += 1 
        else:
            awayscore += 1 
        
        a["nice_time"] = a.apply(nice_time,axis=1)
        labels = a[["nice_time", "type_name", "player", "team_name"]]
        matplotsoccer.actions(
            location=a[["start_x", "start_y", "end_x", "end_y"]],
            action_type=a.type_name, team= a.team_name,
            title=f"{hometeam} {homescore} - {awayscore} {awayteam}",
            result= a.result_name == "success",
            label=labels,figsize=(w,h),
            labeltitle=["time","actiontype","player","team"],
            zoom=zoom, color='green', legloc='top',
            show=False,ax=fig.add_subplot(len(goalindex),1,goal)
        )
        goal += 1   
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format = "png")
    data = base64.b64encode(buf.getbuffer()).decode("utf8")
    plt.close()
    return data
