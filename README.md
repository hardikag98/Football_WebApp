# ⚽ Football Analytics Dashboard

An interactive football analytics web app built with Python and Dash, using StatsBomb's free open event data.

## Features

- **Goals tab** — visualises the sequence of actions leading up to every goal in a match
- **Passing Network tab** — shows which players passed to each other and how often
- **Player Analysis tab** — overlays a selected player's passes, shots, tackles and position heatmap on an interactive pitch

## Data

Powered by [StatsBomb Open Data](https://statsbomb.com/what-we-do/hub/free-data/). Includes:
- UEFA Champions League finals (2004–2019)
- FIFA World Cup 2018
- Women's World Cup 2019
- FA Women's Super League (2018/19, 2019/20, 2020/21)
- La Liga (2004/05 – 2020/21, Barcelona matches)
- UEFA Euro 2020
- UEFA Women's Euro 2022
- NWSL 2018
- Indian Super League 2021/22
- Premier League 2003/04 (Arsenal Invincibles)

## Running Locally

```bash
git clone https://github.com/hardikag98/Football_WebApp.git
cd Football_WebApp
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8050 in your browser.

## Deployment

This app is configured for deployment on [Render.com](https://render.com).

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` and configure everything

The app uses the `render.yaml` file for configuration. No environment variables required.

## Tech Stack

- [Dash](https://dash.plotly.com/) — web framework
- [Plotly](https://plotly.com/) — interactive charts
- [Matplotlib](https://matplotlib.org/) — pitch & action visualisations
- [StatsBombPy](https://github.com/statsbomb/statsbombpy) — event data
- [socceraction](https://github.com/ML-KULeuven/socceraction) — SPADL action format for goals tab
- [Gunicorn](https://gunicorn.org/) — production WSGI server

## Author

[Hardik Agarwal](https://www.linkedin.com/in/hardy-agarwal/)
