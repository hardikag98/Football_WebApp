# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
"""

import matplotlib
matplotlib.use('Agg')
from statsbombpy import sb 
import dash; from dash import dcc
#import dash_daq as daq
from dash import html
from dash.dependencies import Input, Output
import field 
import MPS 
import matplotlib.pyplot as plt
import pandas as pd 
import functools 
from graph import passingnetwork
from passing_network import draw_pitch
from actionplot import plotaction
import io
import base64
import os
import psycopg2

#Establishing connection to the database
conn = psycopg2.connect("DATABASE_URL_REMOVED", 
                        sslmode='require')

#Defining cursor
cur = conn.cursor()

#Get event data for a match from database
@functools.lru_cache(maxsize=10)
def get_event_data(input1):
    events = sb.events(match_id = input1)
    try:
        cur.execute(f"""SELECT * from vaep
                            where "gameID" = {input1};""")
        data = cur.fetchall()
        df_vaep = pd.DataFrame(data,columns=['GameID','period_id','timestamp','vaep_value'])
    except:
        cur = conn.cursor()
        cur.execute(f"""SELECT * from vaep
                        where "gameID" = {input1};""")
        data = cur.fetchall()
        df_vaep = pd.DataFrame(data,columns=['GameID','period_id','timestamp','vaep_value'])
    #pd.read_hdf(os.path.join("data-fifa", "vaeptime.h5"), "game_{0}".format(input1))

    events.timestamp = pd.to_datetime(events.timestamp)
    events.timestamp = events.timestamp.dt.time

    df_vaep.timestamp = pd.to_datetime(df_vaep.timestamp)
    df_vaep.timestamp = df_vaep.timestamp.dt.time

    events = events.merge(df_vaep, left_on=['period','timestamp'], right_on=['period_id','timestamp'], how='left')
    return events

@functools.lru_cache(maxsize=10)
def get_lineup_data(input1):
    return sb.lineups(match_id = input1)

@functools.lru_cache(maxsize=10)
def get_player_data(input1,input2):
    fig=field.drawfield()
    events = get_event_data(input1)
    playerdata = events[events['player']==input2]
    playerdata.loc[:,'second'] = [str(playerdata.loc[i,'second']) if len(str(playerdata.loc[i,'second']))==2 else '0'+str(playerdata.loc[i,'second']) for i in  playerdata.index.values]
    

    #PASS DATA
    #Pass arrows
    playerpassdata = playerdata[(playerdata['type'] == "Pass")]
    passannotation=[]

    #Pass points
    px1=[500]
    py1=[50]
    pcolors=['black']
    ptime = ['00:00']
    pvaep = ['0.0']

    for i in playerpassdata.index.values:
        try:
            color = "red" if playerpassdata.loc[i,'pass']['outcome']['id'] == 9 else "blue"
        except KeyError:
            color = "blue"
        
        passannotation.append(dict(x=playerpassdata.loc[i,'pass']['end_location'][0],
                                y=80-playerpassdata.loc[i,'pass']['end_location'][1],text="",
                                ax=playerpassdata.loc[i,'location'][0],
                                ay=80-playerpassdata.loc[i,'location'][1],
                                xref="x",yref="y",axref = "x",ayref = "y",
                                showarrow=True,arrowhead=2,arrowcolor=color,opacity=0.7))#,
                                #hovertext='Time: '+ str(playerpassdata.loc[i,'minute'])+':'+str(playerpassdata.loc[i,'second'])+ ';\n' +
                                #'VAEP: ' + str(round(playerpassdata.loc[i,'vaep_value'],3))))
    
        px1.append(playerpassdata.loc[i,'location'][0])
        py1.append(80-playerpassdata.loc[i,'location'][1])
        pcolors.append(color)
        ptime.append(str(playerpassdata.loc[i,'minute'])+':'+str(playerpassdata.loc[i,'second']))
        pvaep.append(str(round(playerpassdata.loc[i,'vaep_value'],3)))
    passes = pd.DataFrame({'x1':px1,'y1':py1,'Colors':pcolors,'Time':ptime,'VAEP':pvaep})
    passes.loc[:,'Hoverinfo'] = 'Time: ' + passes['Time'].astype(str)  + '<br>VAEP: ' + passes['VAEP'].astype(str) 

    #SHOT DATA
    #Shot arrows
    playershotdata = playerdata[(playerdata['type'] == "Shot")] 
    shotannotation=[]

    #Shot points
    sx1=[500]
    sy1=[50]
    scolors=['black']
    stime = ['00:00']
    svaep = ['0.0']

    for i in playershotdata.index.values:
        color='blue' if playershotdata.loc[i,'shot']['outcome']['id']==97 else 'red'
        shotannotation.append(dict(x=playershotdata.loc[i,'shot']['end_location'][0],
                                y=80-playershotdata.loc[i,'shot']['end_location'][1],
                                ax=playerdata.loc[i,'location'][0],ay=80-playerdata.loc[i,'location'][1],
                                xref="x",yref="y",axref = "x",ayref = "y",showarrow=True,
                                arrowcolor=color,arrowsize=1,arrowwidth=4,arrowhead=4,text="",opacity=0.7))#,
                                #hovertext='Time: '+ str(playershotdata.loc[i,'minute'])+':'+str(playershotdata.loc[i,'second']) + ';\n' +
                                #'VAEP: ' + str(round(playershotdata.loc[i,'vaep_value'],3))))

        sx1.append(playerdata.loc[i,'location'][0])
        sy1.append(80-playerdata.loc[i,'location'][1])
        scolors.append(color)
        stime.append(str(playershotdata.loc[i,'minute'])+':'+str(playershotdata.loc[i,'second']))
        svaep.append(str(round(playershotdata.loc[i,'vaep_value'],3)))
    shots = pd.DataFrame({'x1':sx1,'y1':sy1,'Colors':scolors,'Time':stime,'VAEP':svaep})
    shots.loc[:,'Hoverinfo'] = 'Time: ' + shots['Time'].astype(str)  + '<br>VAEP: ' + shots['VAEP'].astype(str) 

    #Tackle data
    playerdueldata = playerdata[(playerdata['type'] == "Duel")] 
    tx1=[500]
    ty1=[50]
    tcolors=['black']
    ttime = ['00:00']
    tvaep = ['0.0']
    for i in playerdueldata.index.values:
        if playerdueldata.loc[i,'duel']['type']['id']==11:
            color='red' if playerdueldata.loc[i,'duel']['outcome']['id']==14 else 'blue'
            tcolors.append(color)
            tx1.append(playerdueldata.loc[i,"location"][0])
            ty1.append(80-playerdueldata.loc[i,"location"][1])
            ttime.append(str(playerdueldata.loc[i,'minute'])+':'+str(playerdueldata.loc[i,'second']))
            tvaep.append(str(round(playerdueldata.loc[i,'vaep_value'],3)))
    tackles = pd.DataFrame({'x1':tx1,'y1':ty1,'Colors':tcolors,'Time':ttime,'VAEP':tvaep})
    tackles.loc[:,'Hoverinfo'] = 'Time: ' + tackles['Time'].astype(str) + '<br>VAEP: ' + tackles['VAEP'].astype(str) 
            
    #heatmap
    x2 = [i[0] for i in playerdata.location.dropna()]
    y2 = [80-i[1] for i in playerdata.location.dropna()]
    heatmap=[x2,y2]
    return (fig,passannotation,passes,shotannotation,shots,tackles,heatmap)


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
pitch=field.drawfield()
comp = sb.competitions()
compname = comp['competition_name'].unique() 

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server 
app.config['suppress_callback_exceptions']=True
colors = {
    'background': '#F9F9F9',
    'text': '#7FDBFF'
}
fig=plt.figure()
fig.set_size_inches(6.7*1.5,6.7,forward=False)
MPS.drawactionfield(ax=fig.add_subplot(111),color='white',linecolor='lightgrey',show=False)
plt.tight_layout()
buf = io.BytesIO()
plt.savefig(buf, format = "png")
data = base64.b64encode(buf.getbuffer()).decode("utf8")
plt.close()

app.layout = html.Div(style={'backgroundColor': colors['background']},children=[
    html.Div(style={'textAlign': 'center', 'margin': -2, 'padding':-10, 'font-size': 48}, children=[
        html.B(children='Football  Analytics' )]),
    html.H4(children='Visualizing football event data', style={'textAlign': 'center','margin': -2, 'padding':-10}),
    html.Div(style={'textAlign': 'center','margin': -2, 'padding':-10, 'font-size': 26}, children=[
        html.A('Hardik Agarwal', href='https://www.linkedin.com/in/hardy-agarwal/', target="_blank")]),

    html.Div(
            [
                html.Div(
                    [
                        html.H3("Choose a team and player to analyse!"),
                        html.P(children='Note: Options in the player dropdown list can take a few seconds to load/update.'),
                        #    style={'textAlign': 'left'}),
                        html.P("Competition:", className="control_label"),
                        dcc.Dropdown(id='competition',
                                     options=[{'label': i, 'value': i} for i in compname]),
                        html.P("Season:", className="control_label"),
                        dcc.Dropdown(id='season'),
                        html.P("Match:", className="control_label"),
                        dcc.Dropdown(id='match'),
                        html.Div([html.B(children='Passing Network',
                                style={'margin': 0, 'padding': 0, 'font-size': 16})]),
                        html.P("Team:", className="control_label"),
                        dcc.Dropdown(id='team'),
                        html.P("Pass Value:", className="control_label"),
                        dcc.RadioItems(id='passingnetwork',
                                        options=['Count', 'VAEP'], 
                                        value='Count'),
                        html.A('(Valuing Actions by Estimating Probabilities)',
                                href='https://dtai.cs.kuleuven.be/sports/vaep', target="_blank"), 
                        html.Div([html.B(children='Player Analysis' ,
                                style={'margin': 0, 'padding': 0, 'font-size': 16})]),              
                        html.P("Player:", className="control_label"),
                        dcc.Dropdown(id='player'),
                        html.P("Action:", className="control_label"),
                        dcc.Checklist(id='actions',
                            options=[
                            {'label': 'Passes',  'value': 'Passes'},
                            {'label': 'Shots',   'value': 'Shots'},
                            {'label': 'Tackles', 'value': 'Tackles'},
                            {'label': 'Heatmap', 'value': 'Heatmap'}
                            ]),
                    ],
                    className="pretty_container four columns",
                    id="cross-filter-options",
                    style={'width': '25%','border': 'thin lightgrey solid','padding': '10px'}
                ),
                html.Div(
                    [
                        dcc.Tabs([
                            dcc.Tab(label='Goals', children=[
                                    html.Img(id='pitch3',
                                             src="data:image/png;base64,{}".format(data))]),
                            dcc.Tab(label='Passing network', children=[
                                    html.Img(id='pitch2',src="data:image/png;base64,{}".format(data)),
                                    html.P("""This graph displays passing network among players in the starting lineup of the selected team. 
                                            Only successful passes until the time of a change among the players (due to substitution/red card) are considered.
                                            If there are less than 11 nodes in the network, this is due to a player not having completed any successful passes in that time period.
                                            """)]), 
                                            #draw_pitch(empty_pitch=True)))]),
                            dcc.Tab(label='Player Analysis', children=[
                                    dcc.Graph(id='pitch1', figure=pitch)])
                            ]),
                        
                    ],
                    style={'width': '75%','padding': '10px'}
                    ),
                ],
                style={"display": "flex", "flex-direction": "row",
                       'backgroundColor': colors['background']}),
    
    html.Div(['Data Source: ',html.A('StatsBomb', href='https://statsbomb.com/what-we-do/hub/free-data/', 
                target="_blank")], style={'textAlign': 'left', 'font-size': '22px'})]) #,
    #html.P("References:"),
    #html.Div(['1) ',html.A('VAEP',href='https://dl.acm.org/doi/10.1145/3292500.3330758')], 
    #    style={'textAlign': 'left'}) ])
    

@app.callback(
    Output('season', 'options'),
    [Input('competition', 'value')])
def set_season_options(selected_comp):
    return [{'label': i['season_name'], 'value': i['season_id']} for index,i in 
            comp[comp['competition_name']==
                 str(selected_comp)][['season_name','season_id']].iterrows()]
    
@app.callback(
    Output('match', 'options'),
    [Input('competition', 'value'),
     Input('season', 'value')])
def set_match_options(selected_comp,selected_seas):
    compid = comp[comp.competition_name==str(selected_comp)]['competition_id'].iloc[0]
    matches = sb.matches(competition_id=compid, season_id=
                         selected_seas)[['home_team','away_team','match_id']]
    return [{'label': i.home_team +' vs '+ i.away_team, 'value': i.match_id} 
            for index,i in matches.iterrows()]

@app.callback(
    Output('team', 'options'),
    [Input('match', 'value')])
def team_options(selected_match):
    return [{'label': i, 'value': i} for i in 
            list(get_lineup_data(selected_match).keys())]

@app.callback(
    Output('player', 'options'),
    [Input('match', 'value'),
     Input('team', 'value')])
def player_options(selected_match,selected_team):
    events = get_event_data(selected_match)
    players = events[events.team==selected_team].player.unique()
    lineups = get_lineup_data(selected_match)[selected_team]
    players = set(players).intersection(set(lineups.player_name))
    names_dict = {player[1]["player_name"]: player[1]["player_nickname"] for 
                  team in lineups for player in lineups.iterrows()}
    options = []
    for i in players:
        if names_dict[i]!=None:
            options.append({'label': names_dict[i], 'value': i})
        else:
            options.append({'label': i, 'value': i})
    return options

@app.callback(
    Output('pitch2', 'src'),
    [Input('match', 'value'),
     Input('team', 'value') ,
     Input('passingnetwork', 'value')])
def update_graph(selected_match,selected_team,selected_passvalue):
    events = get_event_data(selected_match)
    lineups = get_lineup_data(selected_match)
    data = passingnetwork(selected_match,selected_team,events,lineups,selected_passvalue)
    return "data:image/png;base64,{}".format(data)  

@app.callback(
    Output('pitch3', 'src'),
    [Input('match', 'value')])
def update_goals(selected_match): 
    actions=plotaction(selected_match,w=10,h=8,zoom=False)
    return "data:image/png;base64,{}".format(actions)

@app.callback(
    Output('pitch1', 'figure'),
    [Input('player', 'value'),
     Input('actions','value'),
     Input('match', 'value')])
def update_figure(selected_player,selected_actions,selected_match):
    (fig,passannotation,passes,shotannotation,shots,tackles,heatmap) = get_player_data(selected_match,selected_player)
    
    if 'Tackles' in selected_actions:
        fig.data[0].x = tackles['x1']
        fig.data[0].y = tackles['y1']
        fig.data[0].marker['color'] = tackles['Colors']

        fig.data[0].hovertext = tackles['Hoverinfo']

    else: 
        fig.data[0].x = []
        fig.data[0].y = []
        fig.data[0].marker['color'] = []
        
    if 'Heatmap' in selected_actions:
        fig.data[1].x = heatmap[0]
        fig.data[1].y = heatmap[1]
    else:
        fig.data[1].x = []
        fig.data[1].y = []

    if 'Passes' in selected_actions:
        fig.data[2].x = passes['x1']
        fig.data[2].y = passes['y1']
        fig.data[2].marker['color'] = passes['Colors']

        fig.data[2].hovertext = passes['Hoverinfo']

    else: 
        fig.data[2].x = []
        fig.data[2].y = []
        fig.data[2].marker['color'] = []

    if 'Shots' in selected_actions:
        fig.data[3].x = shots['x1']
        fig.data[3].y = shots['y1']
        fig.data[3].marker['color'] = shots['Colors']

        fig.data[3].hovertext = shots['Hoverinfo']

    else: 
        fig.data[3].x = []
        fig.data[3].y = []
        fig.data[3].marker['color'] = []
        
    #fig.update_layout(showlegend=True,legend_tracegroupgap=2,legend_orientation='h',
    #    margin_autoexpand=True, height=860)
    
    if ('Shots' in selected_actions) & ('Passes' in selected_actions):
        fig.layout.annotations = passannotation + shotannotation
    elif 'Shots' in selected_actions:
        fig.layout.annotations = shotannotation
    elif 'Passes' in selected_actions:
        fig.layout.annotations = passannotation
    else:
        fig.layout.annotations = []
        
    return fig 

if __name__ == '__main__':
    app.run_server(debug=True)