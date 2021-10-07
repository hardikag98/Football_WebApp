import matplotlib
matplotlib.use('Agg')
from statsbombpy import sb 
<<<<<<< HEAD
import dash; import dash_core_components as dcc
import dash_html_components as html
=======
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go
>>>>>>> parent of c8372d9 (goals analysis added)
from dash.dependencies import Input, Output
import field 
import pandas as pd 
import numpy as np
import functools 
from graph import passingnetwork
from passing_network import draw_pitch

<<<<<<< HEAD
#Function to retrieve relevant event level data
@functools.lru_cache(maxsize=15)
def get_event_data(input1):
    return sb.events(match_id = input1)

#Function to retrieve relevant lineup data
@functools.lru_cache(maxsize=15)
=======
@functools.lru_cache(maxsize=25)
def get_event_data(input1):
    return sb.events(match_id = input1)

@functools.lru_cache(maxsize=25)
>>>>>>> parent of c8372d9 (goals analysis added)
def get_lineup_data(input1):
    return sb.lineups(match_id = input1)

#Function to plot player actions
@functools.lru_cache(maxsize=15)
def get_player_data(input1,input2):
    fig=field.drawfield()
    events = get_event_data(input1)
    playerdata = events[events['player']==input2]
    #pass data 
    playerpassdata = playerdata[(playerdata['type'] == "Pass")]
    passannotation=[]
    for i in playerpassdata.index.values:
        try:
            color = "red" if playerpassdata.loc[i,'pass']['outcome']['id'] == 9 else "green"
        except KeyError:
            color = "green"
        passannotation.append(dict(x=playerpassdata.loc[i,'pass']['end_location'][0],
                            y=playerpassdata.loc[i,'pass']['end_location'][1],text="",
                            ax=playerpassdata.loc[i,'location'][0],
                            ay=playerpassdata.loc[i,'location'][1],
                            xref="x",yref="y",axref = "x",ayref = "y",
                            showarrow=True,arrowhead=2,arrowcolor=color))
    #Shot data
    playershotdata = playerdata[(playerdata['type'] == "Shot")] 
    shotannotation=[]
    for i in playershotdata.index.values:
        color='green' if playershotdata.loc[i,'shot']['outcome']['id']==97 else 'red'
        shotannotation.append(dict(x=playershotdata.loc[i,'shot']['end_location'][0],
                                   y=playershotdata.loc[i,'shot']['end_location'][1]
                      ,ax=playerdata.loc[i,'location'][0],ay=playerdata.loc[i,'location'][1],
                      xref="x",yref="y",axref = "x",ayref = "y",showarrow=True,
                      arrowcolor=color,arrowsize=1,arrowwidth=3,arrowhead=3,text=""))
    #Tackle data
    playerdueldata = playerdata[(playerdata['type'] == "Duel")] 
    colors=[]
    x1=[]
    y1=[]
    for i in playerdueldata.index.values:
        if playerdueldata.loc[i,'duel']['type']['id']==11:
            color='red' if playerdueldata.loc[i,'duel']['outcome']['id']==14 else 'green'
            colors.append(color)
            x1.append(playerdueldata.loc[i,"location"][0])
            y1.append(playerdueldata.loc[i,"location"][1])
            
    x2 = [i[0] for i in playerdata.location.dropna()]
    y2 = [i[1] for i in playerdata.location.dropna()]
    return (fig,passannotation,shotannotation,x1,y1,x2,y2,colors)

#Setting up req for the app
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
<<<<<<< HEAD
fig=plt.figure()
fig.set_size_inches(10,8,forward=True)
matplotsoccer.field(ax=fig.add_subplot(111),color='green',show=False)
plt.tight_layout()
buf = io.BytesIO()
plt.savefig(buf, format = "png")
data = base64.b64encode(buf.getbuffer()).decode("utf8")
plt.close()
=======
>>>>>>> parent of c8372d9 (goals analysis added)

#Defining app layout
app.layout = html.Div(style={'backgroundColor': colors['background']},children=[
    html.H1(children='Football  Analytics',style={'textAlign': 'center'}),
    html.H3(children='Note: Options in the team and player dropdown list can take a few seconds to load/update,',
            style={'textAlign': 'left'}),

    html.Div(
            [
                html.Div(
                    [
                        html.H3("Filters"),
                        html.P("Competition:", className="control_label"),
                        dcc.Dropdown(id='competition',
                                     options=[{'label': i, 'value': i} for i in compname]
                                     ),
                        html.P("Season:", className="control_label"),
                        dcc.Dropdown(id='season'),
                        html.P("Match:", className="control_label"),
                        dcc.Dropdown(id='match'),
                        html.P("Team:", className="control_label"),
                        dcc.Dropdown(id='team'),
                        html.P("Player:", className="control_label"),
                        dcc.Dropdown(id='player'),
                        dcc.Checklist(id='actions',
                            options=[
                            {'label': 'Passes', 'value': 'Passes'},
                            {'label': 'Shots', 'value': 'Shots'},
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
                            dcc.Tab(label='Passing network', children=[
                                    html.Img(id='pitch2',src="data:image/png;base64,{}".format(
                                            draw_pitch(empty_pitch=True)))]),
<<<<<<< HEAD
                            dcc.Tab(label='Player Analysis', children=[
                                    dcc.Graph(id='pitch1', figure=pitch)]),
                            dcc.Tab(label='Goals', children=[
                                    html.Img(id='pitch3',
                                             src="data:image/png;base64,{}".format(data))])
=======
>>>>>>> parent of c8372d9 (goals analysis added)
                            ]),
                        
                    ],
                    style={'width': '75%','padding': '10px'}
                    ),
                ],
                style={"display": "flex", "flex-direction": "row",
                       'backgroundColor': colors['background']}),
    
    html.H5(children='Data Credits: Statsbomb',
            style={'textAlign': 'left'})    
    ])

#Select season drop down
@app.callback(
    Output('season', 'options'),
    [Input('competition', 'value')])
def set_season_options(selected_comp):
    return [{'label': i['season_name'], 'value': i['season_id']} for index,i in 
            comp[comp['competition_name']==
                 str(selected_comp)][['season_name','season_id']].iterrows()]

#Select match dropdown    
@app.callback(
    Output('match', 'options'),
    [Input('competition', 'value'),
     Input('season', 'value')])
def set_match_options(selected_comp,selected_seas):
    compid = comp[comp.competition_name==str(selected_comp)]['competition_id'].iloc[0]
    matches = sb.matches(competition_id=compid, season_id=
                         selected_seas)[['home_team','away_team','match_id']]
    return [{'label': i.home_team+' vs '+i.away_team, 'value': i.match_id} 
            for index,i in matches.iterrows()]

#Select team drop down
@app.callback(
    Output('team', 'options'),
    [Input('match', 'value')])
def team_options(selected_match):
    return [{'label': i, 'value': i} for i in 
            list(get_lineup_data(selected_match).keys())]

#Select player drop down
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

#Updating passing network graph
@app.callback(
    Output('pitch2', 'src'),
    [Input('match', 'value'),
     Input('team', 'value')])
def update_graph(selected_match,selected_team):
    events = get_event_data(selected_match)
    lineups = get_lineup_data(selected_match)
    data = passingnetwork(selected_match,selected_team,events,lineups)
    return "data:image/png;base64,{}".format(data)  

#Updating goals graph
@app.callback(
<<<<<<< HEAD
    Output('pitch3', 'src'),
    [Input('match', 'value')])
def update_goals(selected_match): 
    actions=plotaction(selected_match,w=10,h=8,zoom=False)
    return "data:image/png;base64,{}".format(actions)

#Updating player action graph
@app.callback(
=======
>>>>>>> parent of c8372d9 (goals analysis added)
    Output('pitch1', 'figure'),
    [Input('player', 'value'),
     Input('actions','value'),
     Input('match', 'value')])
def update_figure(selected_player,selected_actions,selected_match):
    (fig,passannotation,shotannotation,x1,y1,x2,y2,colors) = get_player_data(
            selected_match,selected_player)
    
    if 'Tackles' in selected_actions:
        fig.data[1].x = x1  
        fig.data[1].y = y1
        fig.data[1].marker['color'] = colors
    else: 
        fig.data[1].x = []
        fig.data[1].y = []
        fig.data[1].marker['color'] = []
        
    if 'Heatmap' in selected_actions:
        fig.data[2].x = x2
        fig.data[2].y = y2
    else:
        fig.data[2].x = []
        fig.data[2].y = []
        
    fig.update_layout(showlegend=False)
    
    if ('Shots' in selected_actions) & ('Passes' in selected_actions):
        fig.layout.annotations = passannotation+ shotannotation
    elif 'Shots' in selected_actions:
        fig.layout.annotations = shotannotation
    elif 'Passes' in selected_actions:
        fig.layout.annotations = passannotation
    else:
        fig.layout.annotations = []
        
    return fig 

if __name__ == '__main__':
    app.run_server(debug=True)