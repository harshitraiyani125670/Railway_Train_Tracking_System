"""
fetch_stations.py - Run this ONCE to build a local database of all Indian
railway stations (stations.json), so the main app never needs to call the
API for station lookups.

USAGE:
    python fetch_stations.py

This uses the same API_KEY you put in app.py. Re-run this occasionally
(e.g. every few months) if you want to pick up newly added stations.
"""

import json
import sys
import requests

# Reuse the same key you set in app.py
from app import API_KEY, API_BASE, _check_key


def fetch_all_stations():
    _check_key()
    headers = {"Authorization": f"Bearer {API_KEY}"}

    print("Downloading full India station database from RailRadar...")
    try:
        resp = requests.get(f"{API_BASE}/legacy/stations/all-kvs", headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network problem: {e}")
        sys.exit(1)

    if not resp.ok:
        print(f"[ERROR] API returned status {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    body = resp.json()
    if not body.get("success"):
        print(f"[ERROR] {body.get('error', {}).get('message', 'Unknown error')}")
        sys.exit(1)

    raw = body["data"]

    # Normalize into a simple list of {code, name} - handles a couple of
    # possible shapes since this is an unofficial/legacy endpoint format.
    stations = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                code, label = entry[0], entry[1]
                name = label.split(" - ", 1)[1] if " - " in label else label
                stations.append({"code": code, "name": name})
            elif isinstance(entry, dict):
                code = entry.get("code") or entry.get("stationCode")
                name = entry.get("name") or entry.get("stationName")
                if code and name:
                    stations.append({"code": code, "name": name})
    elif isinstance(raw, dict):
        for code, name in raw.items():
            stations.append({"code": code, "name": name})

    if not stations:
        print("[ERROR] Got a response but couldn't find any stations in it.")
        print(f"Raw response sample: {str(raw)[:500]}")
        sys.exit(1)

    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)

    print(f"Done! Saved {len(stations)} stations to stations.json")


if __name__ == "__main__":
    fetch_all_stations()
