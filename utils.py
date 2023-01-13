import os
import pandas as pd 
#%%

datafolder = os.getcwd() + "/data-fifa"
spadl_h5 = os.path.join(datafolder, "spadl-statsbomb.h5")

def get_comp_names():
    with pd.HDFStore(spadl_h5) as spadlstore:
        comp = spadlstore["competitions"]
    compname = comp['competition_name'].unique() 
    return (comp,compname)

def get_matches(selected_comp,selected_seas):
    with pd.HDFStore(spadl_h5) as spadlstore:
        games = (
            spadlstore["games"]
            .merge(spadlstore["competitions"], how='left')
            .merge(spadlstore["teams"].add_prefix('home_'), how='left')
            .merge(spadlstore["teams"].add_prefix('away_'), how='left'))
    matches = games[(games.competition_name==str(selected_comp)) & 
            (games.season_id==selected_seas)][['home_team_name','away_team_name','game_id']]
    return matches