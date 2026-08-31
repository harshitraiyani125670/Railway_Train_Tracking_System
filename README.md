# Train Schedule Finder (Flask + HTML/CSS/JS, RailRadar Edition)

A real web app: Python/Flask backend + browser-based frontend (HTML, CSS,
vanilla JavaScript). Styled like an old railway station split-flap
departure board.

Three features:
1. **Search Trains** — find trains running between two cities
2. **Live Status** — track any train's real-time position and delay
3. **Route Timeline** — click any train in the search results to see its
   full station-by-station route

Data source: [RailRadar API](https://railradar.in) — documented, free
sandbox tier (1,000 requests/month). Requires a free API key.

## Project structure

```
train_web/
├── app.py                  Flask backend (routes + RailRadar API calls)
├── fetch_stations.py       One-time script: builds the local station database
├── stations.json           Local database of all India stations (created by
│                            fetch_stations.py — not included until you run it)
├── templates/
│   └── index.html          Page structure
├── static/
│   ├── css/style.css       Departure-board styling
│   └── js/app.js           Frontend logic (fetch calls, rendering)
├── requirements.txt
└── README.md
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Get a free API key:
   - Sign up at https://railradar.in
   - Generate a key at https://railradar.in/developers (format: `rr_live_xxxxxxxx`)

3. Open `app.py`, find this line near the top, and paste your key in:
   ```python
   API_KEY = "rr_live_xxxxxxxxxxxxxxxx"
   ```

4. **Build the local station database (one-time step, important!)**
   ```bash
   python fetch_stations.py
   ```
   This downloads all ~10,000 Indian railway stations once and saves them
   to `stations.json`. After this, searching for ANY Indian city or
   station (not just the ~40 major ones) is instant and doesn't use up
   your API quota — the app reads straight from this local file.

   You only need to re-run this occasionally (e.g. every few months) to
   pick up newly added stations. If you skip this step, the app still
   works — it just falls back to calling the API live for station lookups
   (slower, and uses up your monthly quota faster).

5. Run the server:
   ```bash
   python app.py
   ```

6. Open your browser to:
   ```
   http://127.0.0.1:5000
   ```

## How it works

- **`GET /`** — serves the HTML page (`templates/index.html`)
- **`GET /api/trains?from=Mumbai&to=Delhi&date=2026-07-15`** — returns JSON list of trains
- **`GET /api/live/12951`** — returns JSON live status for that train number
- **`GET /api/route/12951`** — returns the full station-by-station timeline
- **`GET /api/stations/search?q=raj`** — autocomplete search (uses `stations.json` if present)
- **`GET /api/stations/debug?q=delhi`** — shows whether the local database is
  loaded and runs a test search, useful for troubleshooting

City/station name lookups (`city_to_code`) check, in order:
1. The small built-in list of ~40 major cities (`CITY_STATION_MAP`) — instant
2. `stations.json` if it exists — instant, covers all of India
3. RailRadar's live search API — only used if `stations.json` is missing

## Supported cities

The 40+ major cities in `CITY_STATION_MAP` always work out of the box.
Every other Indian station works too once you've run `fetch_stations.py`.

## Notes

- Free tier: 1,000 requests/month sandbox.
- Debug mode is on (`app.run(debug=True)`) for easier development — turn
  this off (`debug=False`) before deploying anywhere public.
- Don't share `app.py` publicly with your real API key still in it —
  remove or replace it first.
