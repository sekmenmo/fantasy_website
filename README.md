# Fantasy Broadcast Dashboard

A locally runnable Sleeper fantasy football dashboard for the league configured by `LEAGUE_ID`.

The app is Python-only and server-rendered:

- FastAPI
- Jinja2 templates
- HTMX served from `backend/app/static/js/htmx.min.js`
- custom CSS
- SQLModel with SQLite locally and PostgreSQL support for deployment
- Sleeper public APIs for league, roster, matchup, player, and projection data

## Local Use

Python 3.11 or newer is required.

Create a virtual environment from the project root:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r requirements.txt
```

Run the app from the project root:

```bash
python run.py
```

Then open:

```text
http://127.0.0.1:8000
```

In development, `run.py` opens the browser automatically unless `OPEN_BROWSER=false` is set.

Copy `.env.example` to `.env` if you want to override local defaults.

## Configuration

Common environment variables:

- `APP_ENV`: `development` locally, `production` on Render
- `APP_NAME`: application name
- `LEAGUE_ID`: Sleeper league id
- `DATABASE_URL`: defaults to `sqlite:///./fantasy.db`
- `HOST`: local bind host, default `127.0.0.1`
- `PORT`: local bind port, default `8000`
- `DEBUG`: enables local reload when true
- `OPEN_BROWSER`: controls browser auto-open for `run.py`
- `SLEEPER_CACHE_TTL`: short Sleeper cache TTL in seconds

Sleeper data uses public read-only APIs and does not require an API key.

## Pages

- `/` redirects to `/matchups`
- `/matchups?week=3&matchup=1` shows one matchup at a time
- `/standings` shows league standings
- `/power-rankings` shows the latest completed-week power rankings
- `/rankings` redirects to `/power-rankings`

Matchup navigation keeps `week` and `matchup` in the URL. Week changes reset to matchup `1`; matchup arrows wrap within the selected week. Benches are expanded by default, and Podcast Mode is stored locally in the browser.

## Power Rankings

Power Rankings are generated only for completed scoring weeks. The selected ranking week resolves from Sleeper state and scored matchup data.

The score is a weighted 0-100 total:

- 40% season scoring strength, based on actual points per game
- 25% projected strength, based on starting lineup projection
- 20% recent form, using the last three completed weeks with newer weeks weighted more heavily
- 10% record, using win percentage with ties as half a win
- 5% roster health, based on projected points lost from unavailable or limited starters

Roster health uses current projection when available, then falls back to a recent nonzero projection, then recent actual scoring. Legal bench replacements are considered and are not reused across multiple injured starters.

## Tests

Run tests from the project root:

```bash
backend/.venv/bin/pytest backend/tests
```

Or, with an active virtual environment:

```bash
pytest backend/tests
```

## Render Deployment

`render.yaml` is included for Render Blueprint deployment.

Manual Render setup:

```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT
```

Set `APP_ENV=production`, `LEAGUE_ID`, and a production `DATABASE_URL`. PostgreSQL URLs from Render are normalized by the app at startup.

Database tables are initialized automatically through SQLModel.
