import argparse
import json
import time
from datetime import datetime, timedelta, timezone

import requests

from config import CITIES, OW_CURRENT_URL, OW_HISTORY_URL, OPENWEATHER_API_KEY, RAW_DIR, BACKFILL_MONTHS


def _raw_path(city_name: str, kind: str, ts: datetime) -> "Path":
    stamp = ts.strftime("%Y%m%dT%H%M%S")
    fname = f"{city_name.lower()}_{kind}_{stamp}.json"
    return RAW_DIR / fname


def _save_raw(city_name: str, kind: str, payload: dict) -> None:
    path = _raw_path(city_name, kind, datetime.now(timezone.utc))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def fetch_current(lat: float, lon: float) -> dict:
    resp = requests.get(
        OW_CURRENT_URL,
        params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_history(lat: float, lon: float, start: int, end: int) -> dict:
    resp = requests.get(
        OW_HISTORY_URL,
        params={"lat": lat, "lon": lon, "start": start, "end": end, "appid": OPENWEATHER_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run_hourly() -> None:
    for city in CITIES:
        payload = fetch_current(city["lat"], city["lon"])
        payload["_city_meta"] = city  # on garde le contexte ville dans le fichier brut
        _save_raw(city["name"], "current", payload)
        print(f"[hourly] {city['name']} OK")
        time.sleep(1)  # respect soft du rate limit


def run_backfill(months: int = BACKFILL_MONTHS, chunk_days: int = 7) -> None:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=30 * months)

    for city in CITIES:
        cursor = start_dt
        while cursor < end_dt:
            chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)
            payload = fetch_history(
                city["lat"], city["lon"], int(cursor.timestamp()), int(chunk_end.timestamp())
            )
            payload["_city_meta"] = city
            _save_raw(city["name"], "history", payload)
            print(f"[backfill] {city['name']} {cursor.date()} -> {chunk_end.date()} OK")
            cursor = chunk_end
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hourly", "backfill"], required=True)
    parser.add_argument("--months", type=int, default=BACKFILL_MONTHS)
    args = parser.parse_args()

    if args.mode == "hourly":
        run_hourly()
    else:
        run_backfill(months=args.months)
