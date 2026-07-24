import argparse
from datetime import datetime, timezone

import pandas as pd
import psycopg2

from config import DATABASE_URL

REPORT_PATH = "data/coherence_report.md"


def _connect():
    return psycopg2.connect(DATABASE_URL)


def _bounds(conn):
    """Bornes temporelles globales couvertes par le warehouse (toutes villes confondues)."""
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(timestamp_utc), MAX(timestamp_utc) FROM dim_temps")
        min_ts, max_ts = cur.fetchone()
    return min_ts, max_ts


def _counts_par_ville(conn):
    query = """
        SELECT v.nom, v.pays, COUNT(f.*) AS n_lignes,
               MIN(t.timestamp_utc) AS premiere_mesure,
               MAX(t.timestamp_utc) AS derniere_mesure
        FROM dim_ville v
        LEFT JOIN fact_qualite_air f ON f.id_ville = v.id_ville
        LEFT JOIN dim_temps t ON t.id_temps = f.id_temps
        GROUP BY v.nom, v.pays
        ORDER BY v.nom
    """
    return pd.read_sql(query, conn)


def _heures_manquantes(conn, nom_ville: str, min_ts, max_ts) -> int:
    """Compte les heures théoriques (bornées à min_ts/max_ts globaux) où cette
    ville n'a AUCUNE ligne de faits — un vrai trou, pas juste un décalage de
    quelques minutes."""
    query = """
        WITH heures_theoriques AS (
            SELECT generate_series(
                date_trunc('hour', %(min_ts)s::timestamptz),
                date_trunc('hour', %(max_ts)s::timestamptz),
                interval '1 hour'
            ) AS heure
        ),
        heures_presentes AS (
            SELECT date_trunc('hour', t.timestamp_utc) AS heure
            FROM fact_qualite_air f
            JOIN dim_temps t ON t.id_temps = f.id_temps
            JOIN dim_ville v ON v.id_ville = f.id_ville
            WHERE v.nom = %(nom)s
        )
        SELECT COUNT(*) FROM heures_theoriques ht
        LEFT JOIN heures_presentes hp ON hp.heure = ht.heure
        WHERE hp.heure IS NULL
    """
    with conn.cursor() as cur:
        cur.execute(query, {"min_ts": min_ts, "max_ts": max_ts, "nom": nom_ville})
        (n,) = cur.fetchone()
    return n


def check_coherence(write_report: bool = False) -> pd.DataFrame:
    conn = _connect()
    try:
        min_ts, max_ts = _bounds(conn)
        if min_ts is None:
            print("[coherence] dim_temps est vide — rien à vérifier.")
            return pd.DataFrame()

        heures_theoriques_totales = int((max_ts - min_ts).total_seconds() // 3600) + 1

        df = _counts_par_ville(conn)
        df["heures_theoriques"] = heures_theoriques_totales
        df["heures_manquantes"] = df["nom"].apply(
            lambda nom: _heures_manquantes(conn, nom, min_ts, max_ts)
        )
        df["taux_couverture_pct"] = (
            (1 - df["heures_manquantes"] / df["heures_theoriques"]) * 100
        ).round(2)

        print(f"Période couverte (globale) : {min_ts} -> {max_ts}")
        print(f"Heures théoriques par ville : {heures_theoriques_totales}")
        print()
        print(df[[
            "nom", "pays", "n_lignes", "heures_manquantes", "taux_couverture_pct"
        ]].to_string(index=False))

        total_attendu = heures_theoriques_totales * len(df)
        total_reel = int(df["n_lignes"].sum())
        print()
        print(f"Total attendu (villes x heures) : {total_attendu}")
        print(f"Total réel (lignes de faits)    : {total_reel}")
        print(f"Écart global                    : {total_attendu - total_reel} "
              f"({100 * (total_attendu - total_reel) / total_attendu:.2f} %)")

        if write_report:
            _write_markdown(df, min_ts, max_ts, heures_theoriques_totales, total_attendu, total_reel)
            print(f"\n[coherence] Rapport écrit dans {REPORT_PATH}")

        return df
    finally:
        conn.close()


def _write_markdown(df, min_ts, max_ts, heures_theoriques, total_attendu, total_reel):
    lignes = [
        "# Rapport de cohérence du warehouse",
        "",
        f"_Généré le {datetime.now(timezone.utc).isoformat()}_",
        "",
        f"- Période couverte : `{min_ts}` → `{max_ts}`",
        f"- Heures théoriques par ville : **{heures_theoriques}**",
        f"- Total attendu (villes × heures) : **{total_attendu}**",
        f"- Total réel (lignes de faits) : **{total_reel}**",
        f"- Écart global : **{total_attendu - total_reel}** "
        f"({100 * (total_attendu - total_reel) / total_attendu:.2f} %)",
        "",
        "| Ville | Pays | Lignes | Heures manquantes | Taux de couverture |",
        "|---|---|---|---|---|",
    ]
    for _, row in df.iterrows():
        lignes.append(
            f"| {row['nom']} | {row['pays']} | {row['n_lignes']} | "
            f"{row['heures_manquantes']} | {row['taux_couverture_pct']} % |"
        )
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true",
                         help="Écrit aussi le rapport dans data/coherence_report.md")
    args = parser.parse_args()
    check_coherence(write_report=args.write_report)