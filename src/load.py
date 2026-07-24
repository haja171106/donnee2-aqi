import sys
from datetime import datetime

import pandas as pd
import psycopg2
import psycopg2.extras

from config import CLEAN_FILE, DATABASE_URL

COMPONENT_COLS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]

JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _connect():
    return psycopg2.connect(DATABASE_URL)


def _load_villes(conn, df: pd.DataFrame) -> dict:
    """Upsert dim_ville, renvoie un mapping (nom, pays) -> id_ville."""
    villes = df[["ville", "pays", "latitude", "longitude"]].drop_duplicates()

    rows = list(villes.itertuples(index=False, name=None))
    sql = """
        INSERT INTO dim_ville (nom, pays, latitude, longitude)
        VALUES %s
        ON CONFLICT (nom, pays) DO UPDATE
            SET latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
        RETURNING id_ville, nom, pays
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows)
        result = cur.fetchall()

    with conn.cursor() as cur:
        cur.execute("SELECT id_ville, nom, pays FROM dim_ville")
        result = cur.fetchall()

    return {(nom, pays): id_ville for id_ville, nom, pays in result}


def _load_temps(conn, df: pd.DataFrame) -> dict:
    """Upsert dim_temps, renvoie un mapping timestamp_utc (str ISO) -> id_temps."""
    timestamps = pd.to_datetime(df["timestamp_utc"], utc=True).drop_duplicates()

    rows = []
    for ts in timestamps:
        rows.append((
            ts.to_pydatetime(),
            ts.date(),
            ts.hour,
            JOURS_FR[ts.weekday()],
            ts.weekday() >= 5,
            ts.month,
            (ts.month - 1) // 3 + 1,
            ts.year,
        ))

    sql = """
        INSERT INTO dim_temps
            (timestamp_utc, date, heure, jour_semaine, is_weekend, mois, trimestre, annee)
        VALUES %s
        ON CONFLICT (timestamp_utc) DO NOTHING
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows)

    with conn.cursor() as cur:
        cur.execute("SELECT id_temps, timestamp_utc FROM dim_temps")
        result = cur.fetchall()

    return {ts.isoformat(): id_temps for id_temps, ts in result}


def _load_faits(conn, df: pd.DataFrame, ville_map: dict, temps_map: dict) -> int:
    rows = []
    for row in df.itertuples(index=False):
        id_ville = ville_map[(row.ville, row.pays)]
        ts_key = pd.to_datetime(row.timestamp_utc, utc=True).isoformat()
        id_temps = temps_map[ts_key]
        rows.append((
            id_temps, id_ville, row.aqi,
            row.co, row.no, row.no2, row.o3, row.so2, row.pm2_5, row.pm10, row.nh3,
        ))

    sql = """
        INSERT INTO fact_qualite_air
            (id_temps, id_ville, aqi, co, no, no2, o3, so2, pm2_5, pm10, nh3)
        VALUES %s
        ON CONFLICT (id_temps, id_ville) DO UPDATE
            SET aqi = EXCLUDED.aqi,
                co = EXCLUDED.co,
                no = EXCLUDED.no,
                no2 = EXCLUDED.no2,
                o3 = EXCLUDED.o3,
                so2 = EXCLUDED.so2,
                pm2_5 = EXCLUDED.pm2_5,
                pm10 = EXCLUDED.pm10,
                nh3 = EXCLUDED.nh3
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows)

    return len(rows)


def load_warehouse() -> None:
    df = pd.read_csv(CLEAN_FILE)
    if df.empty:
        print("[load] data/clean/qualite_air.csv est vide, rien à charger.")
        return

    conn = _connect()
    try:
        ville_map = _load_villes(conn, df)
        temps_map = _load_temps(conn, df)
        n = _load_faits(conn, df, ville_map, temps_map)
        conn.commit()
        print(f"[load] {len(ville_map)} villes, {len(temps_map)} horodatages, "
              f"{n} lignes de faits synchronisées dans le warehouse.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        load_warehouse()
    except Exception as exc:
        print(f"[load] ÉCHEC : {exc}", file=sys.stderr)
        sys.exit(1)