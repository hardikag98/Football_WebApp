# -*- coding: utf-8 -*-
"""
@author: Hardy Agarwal
"""
import plotly.graph_objects as go
import plotly.io as pio

pio.templates.default = "none"

def drawfield(title="Hover over actions to see timestamp and VAEP value"):
    fig = go.FigureWidget()

    # Add field
    #Full pitch outline
    fig.add_shape(type="rect",x0=0,y0=0,x1=120,y1=80,line=dict(color='lightgrey'))
    #Left side penalty area
    fig.add_shape(type="rect",x0=0,y0=62,x1=18,y1=18,line=dict(color='lightgrey'))
    #Right side penalty area
    fig.add_shape(type="rect",x0=102,y0=18,x1=120,y1=62,line=dict(color='lightgrey'))
    #Left - 6 yard box
    fig.add_shape(type="rect",x0=0,y0=30,x1=6,y1=50,line=dict(color='lightgrey'))
    #Right - 6 yard box
    fig.add_shape(type="rect",x0=114,y0=30,x1=120,y1=50,line=dict(color='lightgrey'))
    #Halfway line
    fig.add_shape(type="line",x0=60,y0=0,x1=60,y1=80,line=dict(color='lightgrey'))
    # Central circle
    fig.add_shape(type="circle",x0=50,y0=30,x1=70,y1=50,line=dict(color='lightgrey'))
    #fig.add_trace(go.Scatter(x=[12,108,60],y=[40,40,40],mode="markers",
    #                         hoverinfo='skip',
    #                         line=dict(color="white")))
    #
    #Left goal line
    fig.add_shape(type="rect",x0=0,y0=36,x1=-0.5,y1=44,line=dict(color='lightgrey'))
    #Right goal line
    fig.add_shape(type="rect",x0=120,y0=36,x1=120.5,y1=44,line=dict(color='lightgrey'))
    
    fig.update_xaxes(showgrid=False, zeroline=False, ticks='',showticklabels=False,range=[-1, 121])
    fig.update_yaxes(showgrid=False, zeroline=False, ticks='',showticklabels=False,range=[-0.5, 80.5])
    fig.update_shapes(dict(xref='x', yref='y')) 
    fig['layout']['yaxis']['autorange'] = "reversed"
    
    fig.add_trace(go.Scatter(x=[], y=[],mode='markers',name='Tackles',
                             marker=dict(color=[],symbol=4,size=16),
                             hoverinfo='text',showlegend=True))

    fig.add_trace(go.Histogram2dContour(x=[],y=[],colorscale='OrRd',line=dict(width=0),
                                        contours=dict(coloring="heatmap"),hoverinfo='skip',
                                        showscale=False,opacity=0.8,name='Heatmap',
                                        ybins=dict(start=-5,end=85,size=10),
                                        xbins=dict(start=-5,end=125,size=10)))

    fig.add_trace(go.Scatter(x=[], y=[],mode='markers',name='Passes',
                             marker=dict(color=[],symbol=300,size=16),
                             hoverinfo='text'))

    fig.add_trace(go.Scatter(x=[], y=[],mode='markers',name='Shots',
                             marker=dict(color=[],symbol=302,size=16),
                             hoverinfo='text'))

    fig.update_layout(title=title,title_xanchor='right',title_yanchor='middle', title_font_color='grey', title_pad_t=10,
                      width=1000,height=720,autosize=False,
                      margin=dict(l=10,b=10,r=10,t=25),margin_autoexpand=True,
                      showlegend=True, 
                      legend=dict(orientation="h", tracegroupgap=2, 
                                  yanchor="bottom", xanchor="right",
                                  y=1.005, x=1,
                                  title_text='Actions:', 
                                  ))

    fig.update_layout()
    #fig.layout.xaxis.fixedrange = Tru
    #fig.layout.yaxis.fixedrange = True
    #,plot_bgcolor='rgb(245,245,245)'
                                                                  
    return fig