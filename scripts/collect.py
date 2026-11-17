#!/usr/bin/env python3
"""Fetch public weather APIs; preserve provenance and last good data on outages."""
import argparse
import gzip
import json
import math
import os
import sys
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parent))
from community import collect_community, community_fallback
from meteo_france import collect as collect_meteo_france
from freshness import mark_observation_freshness

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
MODELS = {"dwd_icon": "DWD ICON", "ecmwf_ifs025": "ECMWF IFS", "gfs_seamless": "NOAA GFS"}
FIELDS = {"temperature": "temperature_2m", "precipitation": "precipitation", "wind": "wind_speed_10m", "humidity": "relative_humidity_2m"}
UA = "WeatherAtlas/1.0 (+https://github.com/uwarring82/weather-atlas)"


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def fetch(base, params):
    url = base + "?" + urlencode(params)
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=45) as response:
                return json.load(response), url
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def open_meteo(raw):
    hourly = raw["hourly"]
    return [{"time": iso(datetime.fromtimestamp(t, UTC)), **{
        key: number(hourly[field][i]) for key, field in FIELDS.items()
    }} for i, t in enumerate(hourly["time"])]


def met_no(raw):
    # MET reports rain for the NEXT hour. Normalize to the hour END,
    # matching Open-Meteo and Bright Sky's preceding-hour accumulations.
    series = raw["properties"]["timeseries"]
    rain = {}
    for row in series:
        details = row["data"].get("next_1_hours", {}).get("details", {})
        rain[iso(dt(row["time"]) + timedelta(hours=1))] = number(details.get("precipitation_amount"))
    rows = []
    for row in series:
        d = row["data"]["instant"]["details"]
        wind = number(d.get("wind_speed"))
        timestamp = iso(dt(row["time"]))
        rows.append({"time": timestamp, "temperature": number(d.get("air_temperature")),
                     "wind": round(wind * 3.6, 2) if wind is not None else None,
                     "humidity": number(d.get("relative_humidity")), "precipitation": rain.get(timestamp)})
    return rows


def observations(raw, now):
    sources = {s["id"]: s for s in raw["sources"]}
    rows = []
    for r in raw["weather"]:
        source = sources.get(r["source_id"], {})
        # /weather can return MOSMIX forecasts even for recent hours.
        # Never relabel these as station measurements.
        if source.get("observation_type") not in {"historical", "synop", "current"} or dt(r["timestamp"]) > now:
            continue
        rows.append({"time": iso(dt(r["timestamp"])), "temperature": number(r.get("temperature")),
                     "precipitation": number(r.get("precipitation")), "wind": number(r.get("wind_speed")),
                     "humidity": number(r.get("relative_humidity")), "source_id": r["source_id"]})
    used = {r["source_id"] for r in rows}
    return sorted(rows, key=lambda r: r["time"]), [s for s in raw["sources"] if s["id"] in used]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def collect(output, now):
    previous = json.loads(output.read_text()) if output.exists() else {"locations": []}
    old = {l["id"]: l for l in previous["locations"]}
    result = {"schema_version": 1, "collected_at": iso(now), "timezone": "Europe/Berlin",
              "units": {"temperature": "°C", "precipitation": "mm", "wind": "km/h", "humidity": "%"}, "locations": []}
    archive = {"collected_at": iso(now), "responses": []}
    successes = 0
    community_failures = []
    for location in json.loads((ROOT / "locations.json").read_text()):
        loc = {**location, "forecasts": [], "observations": {}}
        last = old.get(location["id"], {})
        point = {"latitude": location["latitude"], "longitude": location["longitude"]}
        for model, label in {**MODELS, "met_no": "MET Norway"}.items():
            try:
                if model == "met_no":
                    raw, url = fetch("https://api.met.no/weatherapi/locationforecast/2.0/compact", {"lat": point["latitude"], "lon": point["longitude"]})
                    rows = met_no(raw)
                    extra = {"provider": "MET Norway", "issued_at": raw["properties"]["meta"]["updated_at"], "model": "Locationforecast (ECMWF outside Nordic region)"}
                else:
                    raw, url = fetch("https://api.open-meteo.com/v1/forecast", {**point, "models": model,
                                     "hourly": ",".join(FIELDS.values()), "forecast_days": 7, "timezone": "UTC", "timeformat": "unixtime", "wind_speed_unit": "kmh"})
                    rows = open_meteo(raw)
                    extra = {"provider": "Open-Meteo", "model": model, "issued_at": None,
                             "grid_latitude": raw.get("latitude"), "grid_longitude": raw.get("longitude"), "elevation": raw.get("elevation")}
                if not any(r["temperature"] is not None and dt(r["time"]) > now for r in rows):
                    raise ValueError("No future temperature data returned")
                item = {"id": model, "label": label, "fetched_at": iso(now), "status": "ok", "url": url, "rows": rows, **extra}
                archive["responses"].append({"location": loc["id"], "source": model, "url": url, "payload": raw})
                successes += 1
            except Exception as error:
                print(f"WARNING {loc['id']} {model}: {error}", flush=True)
                cached = next((f for f in last.get("forecasts", []) if f["id"] == model), {})
                item = {**cached, "id": model, "label": label, "status": "stale" if cached else "unavailable", "error": str(error), "rows": cached.get("rows", [])}
            loc["forecasts"].append(item)
        try:
            if location.get('observation_provider') == 'meteo_france':
                loc['observations'], raw_response = collect_meteo_france(location, last.get('observations', {}), now, UA)
                if raw_response:
                    archive['responses'].append(raw_response)
            else:
                raw, url = fetch("https://api.brightsky.dev/weather", {"lat": point["latitude"], "lon": point["longitude"],
                             "date": iso(now - timedelta(days=7)), "last_date": iso(now), "tz": "UTC", "units": "dwd", "max_dist": 50000})
                rows, sources = observations(raw, now)
                if not rows:
                    raise ValueError("No station observations returned within 50 km")
                loc["observations"] = {"provider": "DWD via Bright Sky", "status": "ok", "fetched_at": iso(now), "url": url, "rows": rows, "sources": sources}
                archive["responses"].append({"location": loc["id"], "source": "brightsky", "url": url, "payload": raw})
            successes += 1
        except Exception as error:
            print(f"WARNING {loc['id']} observations: {error}", flush=True)
            cached = last.get("observations", {})
            loc["observations"] = {**cached, "status": "stale" if cached else "unavailable", "error": str(error), "rows": cached.get("rows", []), "sources": cached.get("sources", [])}
        loc['observations'] = mark_observation_freshness(loc['observations'], now)
        try:
            loc['community'], community_raw = collect_community(location, last.get('community', {}), now, fetch)
            archive['responses'].extend(community_raw)
            if loc['community']['wunderground_status'] == 'configuration_error':
                community_failures.append(location['id'])
        except Exception as error:
            message = f'Community collector failed ({type(error).__name__}); retained recent history'
            print(f"WARNING {location['id']}: {message}", flush=True)
            loc['community'] = community_fallback(last.get('community', {}), now, message)
            community_failures.append(location['id'])
        result["locations"].append(loc)
    if successes == 0:
        raise RuntimeError("All sources failed; keeping the previous published dataset")
    save(output, result)
    # Immutable per-collection raw snapshots. Keep 30 days in the current tree;
    # earlier committed snapshots remain in Git history.
    folder = output.parent / "archive"
    folder.mkdir(exist_ok=True)
    name = now.strftime("%Y-%m-%dT%H%M%SZ") + ".json.gz"
    with gzip.open(folder / name, "wt", encoding="utf-8") as handle:
        json.dump(archive, handle, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H%M%SZ")
    for path in folder.glob("*.json.gz"):
        if path.name[:18] < cutoff:
            path.unlink()
    save(output.parent / "archive-index.json", {"snapshots": sorted(p.name for p in folder.glob("*.json.gz")), "retention_days": 30})
    total_sources = len(result['locations']) * 5
    print(f"Collected {successes}/{total_sources} official/forecast sources at {iso(now)}", flush=True)
    if community_failures:
        raise RuntimeError('Community collector failed for ' + ', '.join(community_failures) + '; fresh official data was saved')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "site/data/latest.json")
    args = parser.parse_args()
    collect(args.output, datetime.now(UTC).replace(microsecond=0))
