import sys

import pandas as pd

from config import CLEAN_FILE, CITIES

REQUIRED_COLS = [
    "ville", "pays", "latitude", "longitude", "timestamp_utc", "aqi",
    "co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3",
]

EXPECTED_CITIES = {c["name"] for c in CITIES}


def validate() -> list[str]:
    errors = []
    df = pd.read_csv(CLEAN_FILE)

    missing_cols = set(REQUIRED_COLS) - set(df.columns)
    if missing_cols:
        errors.append(f"Colonnes manquantes : {missing_cols}")
        return errors  

    key_cols = ["ville", "pays", "latitude", "longitude", "timestamp_utc"]
    n_missing = df[key_cols].isna().any(axis=1).sum()
    if n_missing:
        errors.append(f"{n_missing} lignes avec des champs clés manquants")

    n_dupes = df.duplicated(subset=["ville", "timestamp_utc"]).sum()
    if n_dupes:
        errors.append(f"{n_dupes} doublons sur (ville, timestamp_utc)")

    for ville, g in df.groupby("ville"):
        ts = pd.to_datetime(g["timestamp_utc"])
        if not ts.is_monotonic_increasing:
            errors.append(f"{ville} : timestamps non triés chronologiquement")

    bad_aqi = df["aqi"].dropna()
    if not bad_aqi.between(1, 5).all():
        errors.append("Valeurs d'aqi hors de l'échelle OpenWeather 1-5")

    missing_cities = EXPECTED_CITIES - set(df["ville"].unique())
    if missing_cities:
        errors.append(f"Villes absentes de clean/ : {missing_cities}")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("VALIDATION ÉCHOUÉE :")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("clean/qualite_air.csv conforme au contrat de données.")
