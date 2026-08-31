from flask import Flask, jsonify, render_template, request
import requests
import os
import json

app = Flask(__name__)

API_KEY = "rg_8091bd1a33724e8080251b8cc1c8d209"
API_BASE = "https://api.railradar.in/v1"

# Local station database file (built once by fetch_stations.py)
STATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.json")


class TrainAPIError(Exception):
    """Any API/network related error is raised as this exception."""
    pass


CITY_STATION_MAP = {
    "mumbai": "BCT",
    "delhi": "NDLS",
    "new delhi": "NDLS",
    "bengaluru": "SBC",
    "bangalore": "SBC",
    "chennai": "MAS",
    "kolkata": "HWH",
    "hyderabad": "SC",
    "pune": "PUNE",
    "ahmedabad": "ADI",
    "jaipur": "JP",
    "lucknow": "LKO",
    "surat": "ST",
    "kanpur": "CNB",
    "nagpur": "NGP",
    "indore": "INDB",
    "bhopal": "BPL",
    "patna": "PNBE",
    "vadodara": "BRC",
    "ludhiana": "LDH",
    "agra": "AGC",
    "varanasi": "BSB",
    "amritsar": "ASR",
    "prayagraj": "PRYJ",
    "allahabad": "PRYJ",
    "chandigarh": "CDG",
    "goa": "MAO",
    "kochi": "ERS",
    "coimbatore": "CBE",
    "guwahati": "GHY",
    "bhubaneswar": "BBS",
    "jodhpur": "JU",
    "udaipur": "UDZ",
    "gwalior": "GWL",
    "dehradun": "DDN",
    "haridwar": "HW",
    "jammu": "JAT",
    "raipur": "R",
    "ranchi": "RNC",
    "thiruvananthapuram": "TVC",
    "mysuru": "MYS",
    "mysore": "MYS",
    "visakhapatnam": "VSKP",
    "madurai": "MDU",
    "nashik": "NK",
}


def city_to_code(name: str) -> str:
    """
    Converts a city/station name into its station code.
    Checks the small fast list of major cities first, then searches the
    local stations.json database (all 10,000+ Indian stations, no API call
    needed). Falls back to a live API search only if stations.json hasn't
    been generated yet.
    """
    key = name.strip().lower()

    if key in CITY_STATION_MAP:
        return CITY_STATION_MAP[key]

    if name.strip().isupper() and 2 <= len(name.strip()) <= 5:
        return name.strip()

    results = search_stations(name, limit=1)
    if results:
        return results[0]["code"]

    raise TrainAPIError(
        f"Could not find a station for '{name}'. "
        f"Try a different spelling, a nearby major city, or a station code like NDLS."
    )


# ---------------------------------------------------------------------
# Local station database (stations.json) - built once by fetch_stations.py
# ---------------------------------------------------------------------
_local_stations_cache = None  # list of (code, name, name_lower) tuples


def _load_local_stations():
    """Loads stations.json into memory once and keeps it cached for the
    lifetime of the running app. Returns None if the file doesn't exist."""
    global _local_stations_cache
    if _local_stations_cache is not None:
        return _local_stations_cache

    if not os.path.exists(STATIONS_FILE):
        return None

    with open(STATIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    _local_stations_cache = [(s["code"], s["name"], s["name"].lower()) for s in raw]
    return _local_stations_cache


def search_stations(query: str, limit: int = 10):
    """
    Searches for stations matching the query. Uses the local stations.json
    database if it exists (instant, no API call); otherwise falls back to
    RailRadar's live search endpoint.
    Returns a list of {"code": ..., "name": ...} dicts.
    """
    query = query.strip()
    if len(query) < 2:
        return []

    local = _load_local_stations()
    if local is not None:
        q = query.lower()
        exact = [(c, n) for c, n, nl in local if nl == q]
        starts = [(c, n) for c, n, nl in local if nl.startswith(q) and nl != q]
        contains = [(c, n) for c, n, nl in local if q in nl and not nl.startswith(q)]
        ordered = exact + starts + contains
        return [{"code": c, "name": n} for c, n in ordered[:limit]]

    # No local database yet - fall back to the live API search
    allowed_limits = (5, 10, 20, 50)
    api_limit = min(allowed_limits, key=lambda x: abs(x - limit))
    data = _get("/lookup/search/stations", {"q": query, "limit": api_limit})
    if not data:
        return []

    results = []
    for s in data:
        code = s.get("code")
        name = s.get("name")
        if code and name:
            results.append({"code": code, "name": name})
    return results[:limit]


def _check_key():
    if not API_KEY or API_KEY == "rr_live_PASTE_YOUR_KEY_HERE":
        raise TrainAPIError(
            "API key is not set. Open app.py, find the 'API_KEY = ...' line "
            "near the top, and paste your real key there. "
            "Get a free key: https://railradar.in/developers"
        )


def _get(path: str, params: dict = None):
    """Shared GET helper for the RailRadar API with standard error handling."""
    _check_key()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        resp = requests.get(f"{API_BASE}{path}", headers=headers, params=params or {}, timeout=15)
    except requests.exceptions.RequestException as e:
        raise TrainAPIError(f"Network problem: {e}")

    if resp.status_code == 404:
        return None
    if resp.status_code == 401:
        raise TrainAPIError("API key is invalid. Copy the correct key from your RailRadar dashboard.")
    if resp.status_code == 429:
        raise TrainAPIError("Today's free daily limit (50 requests) is used up. Try again tomorrow.")
    if not resp.ok:
        raise TrainAPIError(f"API returned status {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    if not body.get("success"):
        raise TrainAPIError(body.get("error", {}).get("message", "Unknown error"))
    return body["data"]


def fetch_trains(from_city: str, to_city: str, date: str = None):
    """Returns a normalized list of trains running between two cities."""
    from_code = city_to_code(from_city)
    to_code = city_to_code(to_city)

    params = {"byCity": "true"}
    if date:
        params["date"] = date

    data = _get(f"/trains/between/{from_code}/{to_code}", params)
    if data is None:
        return []

    normalized = []
    for t in data.get("trains", []):
        train = t.get("train", {})
        normalized.append({
            "number": train.get("number", "?"),
            "name": train.get("name", "Unknown"),
            "type": train.get("type", ""),
            "departure": t.get("from", {}).get("departure", "-"),
            "arrival": t.get("to", {}).get("arrival", "-"),
            "duration": t.get("duration"),
            "days": ", ".join(train.get("runDays", [])) or "-",
        })
    return normalized


def fetch_live_status(train_number: str, date: str = None, halts_only: bool = False):
    """Returns live status (summary) for a single train."""
    number = train_number.strip()
    if not number.isdigit():
        raise TrainAPIError("Train number should be digits only, e.g. 12951")

    params = {}
    if date:
        params["date"] = date
    if halts_only:
        params["haltsOnly"] = "true"

    data = _get(f"/trains/{number}/live", params)
    if data is None:
        raise TrainAPIError(f"Train {number} not found (check the number, or it may not run today).")
    return data


def fetch_route(train_number: str, date: str = None):
    """
    Returns the station-by-station route for a train, showing only the
    stops where the train actually halts (pass-through stations are
    excluded via RailRadar's haltsOnly=true).
    """
    live = fetch_live_status(train_number, date, halts_only=True)

    stations = []
    for s in live.get("route", []):
        scheduled_arr = _fmt_time(s.get("scheduledArrival"))
        scheduled_dep = _fmt_time(s.get("scheduledDeparture"))
        actual_arr = _fmt_time(s.get("actualArrival"))
        actual_dep = _fmt_time(s.get("actualDeparture"))
        status = s.get("status", "upcoming")
        delay = s.get("delayArrival") if s.get("delayArrival") is not None else s.get("delayDeparture")

        if status == "upcoming":
            color = "upcoming"
        elif delay is not None and delay > 15:
            color = "late"
        else:
            color = "ontime"

        stations.append({
            "name": s.get("stationName", "?"),
            "code": s.get("stationCode", "-"),
            "distance": s.get("distance", "-"),
            "scheduledArrival": scheduled_arr,
            "scheduledDeparture": scheduled_dep,
            "actualArrival": actual_arr,
            "actualDeparture": actual_dep,
            "platform": s.get("platform") or "-",
            "statusText": status.replace("-", " ").title() + (
                f" ({delay:+d} min)" if delay not in (None, 0) else ""),
            "color": color,
        })

    return {
        "train": {
            "number": live.get("trainNumber", train_number),
            "name": live.get("trainName", "Unknown"),
            "delay": f"{live.get('delayMinutes', 0)} min" if live.get("delayMinutes") is not None else "-",
        },
        "stations": stations,
    }


def _fmt_time(iso_str):
    """Extracts just HH:MM from an ISO timestamp like '2026-06-23T01:07:00+05:30'."""
    if not iso_str:
        return None
    try:
        return iso_str.split("T")[1][:5]
    except (IndexError, AttributeError):
        return iso_str


# ===========================================================================
# ROUTES
# ===========================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stations/search")
def api_stations_search():
    """Autocomplete endpoint: returns up to 10 matching stations
    (searches RailRadar's full India station database live)."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})

    try:
        results = search_stations(q, limit=10)
    except TrainAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"results": results})


@app.route("/api/stations/debug")
def api_stations_debug():
    """Debug helper: shows whether stations.json is being used, and runs
    a test search so you can confirm everything is working."""
    local = _load_local_stations()
    q = request.args.get("q", "delhi")
    try:
        results = search_stations(q, limit=10)
    except TrainAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({
        "using_local_file": local is not None,
        "local_station_count": len(local) if local is not None else 0,
        "stations_file_path": STATIONS_FILE,
        "query": q,
        "results": results,
    })


@app.route("/api/trains")
def api_trains():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()
    date = request.args.get("date", "").strip() or None

    if not from_city or not to_city:
        return jsonify({"error": "Both 'from' and 'to' cities are required."}), 400

    try:
        trains = fetch_trains(from_city, to_city, date)
    except TrainAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"from": from_city, "to": to_city, "trains": trains})


@app.route("/api/live/<train_number>")
def api_live(train_number):
    date = request.args.get("date", "").strip() or None

    try:
        data = fetch_live_status(train_number, date)
    except TrainAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({
        "TrainNo": data.get("trainNumber"),
        "TrainName": data.get("trainName"),
        "LastUpdate": data.get("lastUpdatedAt"),
        "DelayDep": f"{data.get('delayMinutes', 0)} min" if data.get("delayMinutes") is not None else "-",
        "CurrentStation": data.get("currentLocation", {}).get("stationCode", "-"),
        "CurrentStationName": data.get("previousHalt", {}).get("stationName", "-"),
        "Platform": data.get("currentLocation", {}).get("platform", "-"),
        "NextStationName": data.get("nextHalt", {}).get("stationName"),
        "NextStationCode": data.get("nextHalt", {}).get("stationCode"),
        "exceptions": [
            {"ExceptionType": e.get("type"), "ExceptionDate": e.get("message")}
            for e in data.get("exceptions", [])
        ],
    })


@app.route("/api/route/<train_number>")
def api_route(train_number):
    date = request.args.get("date", "").strip() or None

    try:
        data = fetch_route(train_number, date)
    except TrainAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
