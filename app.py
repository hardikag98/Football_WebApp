# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 22:28:30 2020

@author: Admin
"""
from statsbombpy import sb 
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go
#from ipywidgets import widgets
from dash.dependencies import Input, Output
import field 
import pandas as pd 
import functools 

@functools.lru_cache(maxsize=20)
def get_player_data(input1,input2):
    fig=field.drawfield()
    events = sb.events(match_id = input1)
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
                            ax=playerpassdata.loc[i,'location'][0],ay=playerpassdata.loc[i,'location'][1],
                            xref="x",yref="y",axref = "x",ayref = "y",showarrow=True,arrowhead=2,
                            arrowcolor=color))
    #Shot data
    playershotdata = playerdata[(playerdata['type'] == "Shot")] 
    shotannotation=[]
    for i in playershotdata.index.values:
        color='green' if playershotdata.loc[i,'shot']['outcome']['id']==97 else 'red'
        shotannotation.append(dict(x=playershotdata.loc[i,'shot']['end_location'][0],
                                   y=playershotdata.loc[i,'shot']['end_location'][1],text=""
                      ,ax=playerdata.loc[i,'location'][0],ay=playerdata.loc[i,'location'][1],
                      xref="x",yref="y",axref = "x",ayref = "y",showarrow=True,arrowhead=3,
                      arrowcolor=color,arrowsize=1,arrowwidth=3))
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

app.layout = html.Div(style={'backgroundColor': colors['background']},children=[
    html.H1(children='Football  Analytics',style={'textAlign': 'center'}),

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
                        html.P("Player:", className="control_label"),
                        dcc.Dropdown(id='player'),
                        html.P(" ", className="control_label"),
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
                    style={'border': 'thin lightgrey solid','padding': '30px 10px'}
                ),
                dcc.Graph(id='fb-pitch', figure=pitch)
                ],
                style={"display": "flex", "flex-direction": "row",'backgroundColor': colors['background']})
        ])

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
    return [{'label': i.home_team+' vs '+i.away_team, 'value': i.match_id} 
            for index,i in matches.iterrows()]

@app.callback(
    Output('player', 'options'),
    [Input('match', 'value')])
def set_player_otions(selected_match):
    lineup = sb.lineups(match_id = selected_match)
    return [{'label': i, 'value': i} for i in 
            lineup[list(lineup.keys())[0]].player_name
            .append(lineup[list(lineup.keys())[1]].player_name)]
    
@app.callback(
    Output('fb-pitch', 'figure'),
    [Input('player', 'value'),
     Input('actions','value'),
     Input('match', 'value')])
def update_figure(selected_player,selected_actions,selected_match):
    #ctx = dash.callback_context
    #if ctx.triggered[0]['prop_id']=='player.value':
    
    (fig,passannotation,shotannotation,x1,y1,x2,y2,colors) = get_player_data(selected_match,selected_player)
    
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