# Render Deployment Guide

## Setup Steps:

1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect repository: `hardikag98/Football_WebApp`
4. Select branch: `render-deployment`

## Configuration:

- **Name**: football-analytics
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:server --workers 1 --threads 4 --timeout 120`
- **Instance Type**: Free

The app will be live at: `https://football-analytics-[random].onrender.com`

## Notes:

- Python version: 3.9.13 (from runtime.txt)
- Dependencies: 7 packages (dash, plotly, pandas, matplotlib, statsbombpy, numpy, gunicorn)
- Data: Fetched live from StatsBomb Open Data API (no local files needed)
