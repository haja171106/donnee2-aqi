import json
from datetime import datetime, timezone

import pandas as pd

from config import RAW_DIR, CLEAN_FILE

COMPONENT_COLS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]


def _rows_from_file(path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    city_meta = payload.get("_city_meta", {})
    rows = []
    for item in payload.get("list", []):
        dt = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        row = {
            "ville": city_meta.get("name"),
            "pays": city_meta.get("country"),
            "latitude": city_meta.get("lat"),
            "longitude": city_meta.get("lon"),
            "timestamp_utc": dt.isoformat(),
            "aqi": item.get("main", {}).get("aqi"),
        }
        components = item.get("components", {})
        for col in COMPONENT_COLS:
            row[col] = components.get(col)
        rows.append(row)
    return rows


def rebuild_clean() -> pd.DataFrame:
    all_rows = []
    for path in RAW_DIR.glob("*.json"):
        all_rows.extend(_rows_from_file(path))

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("[transform] Aucune donnée brute trouvée — clean/ non modifié.")
        return df

    df = df.drop_duplicates(subset=["ville", "timestamp_utc"])
    df = df.sort_values(["ville", "timestamp_utc"]).reset_index(drop=True)

    df.to_csv(CLEAN_FILE, index=False)
    print(f"[transform] {len(df)} lignes écrites dans {CLEAN_FILE}")
    return df


if __name__ == "__main__":
    rebuild_clean()
