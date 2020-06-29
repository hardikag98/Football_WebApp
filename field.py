# -*- coding: utf-8 -*-
"""
Created on Fri Jun 26 15:15:47 2020

@author: Admin
"""
import plotly.graph_objects as go
from ipywidgets import widgets
import plotly.io as pio

pio.templates.default = "plotly_dark"

def drawfield(titl=""):
    fig = go.FigureWidget()

    # Add field
    fig.add_shape(type="rect",x0=0,y0=0,x1=120,y1=80)
    fig.add_shape(type="rect",x0=0,y0=62,x1=18,y1=18)
    fig.add_shape(type="rect",x0=102,y0=18,x1=120,y1=62)
    fig.add_shape(type="rect",x0=0,y0=30,x1=6,y1=50)
    fig.add_shape(type="rect",x0=114,y0=30,x1=120,y1=50)
    fig.add_shape(type="line",x0=60,y0=0,x1=60,y1=80)
    fig.add_shape(type="circle",x0=51,y0=31,x1=69,y1=49)
    fig.add_trace(go.Scatter(x=[12,108,60],y=[40,40,40],mode="markers",
                             hoverinfo='skip',line=dict(color="white")))
    fig.add_shape(type="rect",x0=120,y0=36,x1=122,y1=44)
    fig.add_shape(type="rect",x0=0,y0=36,x1=-2,y1=44)
    fig.update_xaxes(showgrid=False, zeroline=False,showticklabels=False,range=[-2.5, 122.5])
    fig.update_yaxes(showgrid=False, zeroline=False,showticklabels=False,range=[-2, 82])
    fig.update_shapes(dict(xref='x', yref='y')) 
    fig['layout']['yaxis']['autorange'] = "reversed"
    
    fig.add_trace(go.Scatter(x=[], y=[],mode='markers',name='Tackles',
                             marker=dict(color=[],symbol=4,size=16),hoverinfo='skip'))
    fig.add_trace(go.Histogram2dContour(x=[],y=[],colorscale='OrRd',line=dict(width=0),
                                        contours=dict(coloring="heatmap"),hoverinfo='skip',
                                        showscale=False,opacity=0.8,name='Heatmap',
                                        ybins=dict(start=-5,end=85,size=10),
                                        xbins=dict(start=-5,end=125,size=10)))
    fig.update_layout(title=titl,autosize=False,width=900,height=600,
                      margin=dict(l=10,b=10,r=10,t=10))
    #,plot_bgcolor='rgb(245,245,245)'
                                                                  
    return fig