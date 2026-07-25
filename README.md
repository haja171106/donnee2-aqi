# Pipeline AQI — Qualité de l'air en continu

## Présentation

Ce dépôt contient un pipeline de données qui collecte, heure après heure et sans intervention humaine, l'indice de qualité de l'air (AQI) et les concentrations de polluants pour cinq villes, puis organise ces données dans un entrepôt (data warehouse) modélisé en étoile. Le pipeline est conçu pour continuer à s'exécuter après la remise du projet : chaque exécution horaire est autonome, s'appuie uniquement sur ce qui a déjà été collecté, et met à jour les trois couches du système (bruteclean, warehouse) sans intervention manuelle.

La source de données est l'API OpenWeather Air Pollution, qui fournit un indice AQI sur une échelle de 1 à 5 (et non l'échelle américaine EPA 0-500) ainsi que huit polluants (CO, NO, NO2, O3, SO2, PM2.5, PM10, NH3) en µg/m³.

## Villes suivies

| Ville | Pays | Latitude | Longitude |
|---|---|---|---|
| Antananarivo | MG | -18.8792 | 47.5079 |
| Paris | FR | 48.8566 | 2.3522 |
| Nairobi | KE | -1.2921 | 36.8219 |
| Mumbai | IN | 19.0760 | 72.8777 |
| Beijing | CN | 39.9042 | 116.4074 |

Ce choix couvre volontairement des contextes de pollution très différents (urbain tempéré, tropical, très fortement industrialisé), ce qui donne au warehouse une variance de données utile pour l'analyse en aval.

## Comment le pipeline fonctionne

Le système repose sur trois étapes séquentielles, rejouées automatiquement chaque heure :

1. **Extraction** (`src/extract.py`) — interroge l'API pour chacune des cinq villes et enregistre la réponse telle quelle, sans transformation, dans `data/raw/`. Un fichier JSON est créé par ville et par appel, nommé avec un horodatage précis (`ville_type_YYYYMMDDTHHMMSS.json`). Ces fichiers ne sont jamais réécrits ni supprimés : ils constituent l'unique source de vérité du pipeline. Le même module gère aussi le backfill, qui interroge l'endpoint historique par tranches de sept jours pour reconstituer le passé.

2. **Transformation** (`src/transform.py`) — relit l'intégralité du contenu de `data/raw/`, en extrait une ligne par mesure horaire et par ville, déduplique sur la paire (ville, timestamp), trie chronologiquement, puis réécrit entièrement `data/clean/qualite_air.csv`. Cette étape est idempotente : son résultat ne dépend que de l'état courant de `raw/`, jamais de son propre résultat précédent. Reconstruire `clean/` à partir de zéro à chaque run garantit qu'aucune anomalie ne s'accumule d'une exécution à l'autre.

3. **Chargement** (`src/load.py`) — lit `data/clean/qualite_air.csv` et synchronise l'entrepôt Postgres via des `INSERT ... ON CONFLICT`, ce qui rend le chargement rejouable sans jamais créer de doublons.

Un script de validation (`scripts/validate_clean.py`) s'intercale entre la transformation et le chargement : il vérifie la présence des colonnes attendues, l'absence de doublons et de champs clés manquants, le tri chronologique, la cohérence de l'échelle AQI (1-5), et la présence des cinq villes. Le pipeline s'arrête si cette validation échoue, ce qui empêche de charger des données non conformes dans le warehouse.

## Orchestration

L'exécution automatique est assurée par GitHub Actions plutôt que par un service externe à héberger :

- `.github/workflows/etl.yml` se déclenche chaque heure (`cron: 0 * * * *`) et enchaîne extraction → transformation → validation → chargement → commit des données mises à jour dans le dépôt.
- `.github/workflows/backfill.yml` se déclenche manuellement, avec le nombre de mois d'historique à récupérer en paramètre.

Comme les runners GitHub Actions sont éphémères, les fichiers `data/raw/` et `data/clean/` sont recommittés dans le dépôt à chaque run : c'est à la fois le mécanisme de persistance entre deux exécutions et la preuve, visible dans l'onglet Actions, que le pipeline tourne réellement heure après heure, y compris à des horaires où personne n'est devant l'écran.

La clé API OpenWeather et l'URL de connexion à la base de données ne figurent jamais dans le code : elles sont lues depuis des variables d'environnement (`config.py`), fournies localement par un fichier `.env` non versionné, et par les secrets GitHub Actions (`OPENWEATHER_API_KEY`, `DATABASE_URL`) en production.

## Contrat de données — `data/clean/qualite_air.csv`

Chaque ligne correspond à une mesure pour une ville à une heure donnée. Le fichier est trié chronologiquement par ville et ne contient aucun doublon sur la paire (ville, timestamp).

| Colonne | Description | Unité |
|---|---|---|
| `ville` | Nom de la ville | texte |
| `pays` | Code pays ISO | texte |
| `latitude`, `longitude` | Coordonnées de la ville | degrés décimaux |
| `timestamp_utc` | Horodatage de la mesure | ISO 8601, UTC |
| `aqi` | Indice de qualité de l'air | échelle OpenWeather 1 à 5 (pas l'échelle US EPA 0-500) |
| `co`, `no`, `no2`, `o3`, `so2`, `pm2_5`, `pm10`, `nh3` | Concentrations des polluants | µg/m³ |

## Modélisation du warehouse

Le warehouse (`sql/schema.sql`) suit un schéma en étoile, jugé suffisant pour un volume de cinq villes et deux axes d'analyse (temps, ville) sans besoin de normaliser davantage :

- **`dim_ville`** : identifiant, nom, pays, latitude, longitude. Aucune mesure n'y figure.
- **`dim_temps`** : identifiant, timestamp, date, heure, jour de la semaine, indicateur week-end, mois, trimestre, année.
- **`fact_qualite_air`** : clés étrangères vers les deux dimensions, l'AQI et les huit polluants. Aucune colonne descriptive (nom de ville, libellé de date) n'y figure, uniquement des clés et des mesures. La clé primaire composite (id_temps, id_ville) garantit qu'il ne peut exister qu'une seule ligne de faits par ville et par heure.

Le nombre de lignes de `fact_qualite_air` est donc attendu proche de (nombre de villes × nombre d'heures couvertes par le backfill et la collecte continue) ; les écarts éventuels proviennent de pannes ponctuelles de l'API ou de trous dans l'historique disponible pour certaines plages.

## Installation et exécution locale

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # renseigner OPENWEATHER_API_KEY et DATABASE_URL
psql "$DATABASE_URL" -f sql/schema.sql
```

Cycle complet manuel :

```bash
python -m src.extract --mode backfill --months 3   # historique initial
python -m src.extract --mode hourly                 # un appel horaire
python -m src.transform                             # reconstruction de clean/
python -m scripts.validate_clean                    # contrôle du contrat de données
python -m src.load                                  # synchronisation du warehouse
```

## Période couverte et trous connus

Voir `data/coherence_report.md`, généré et mis à jour par `scripts/check_coherence.py` : période couverte, taux de couverture par ville et causes identifiées des trous.

## Accès au warehouse

- Base : Neon.
- Connexion via la variable d'environnement `DATABASE_URL`.

## Structure du dépôt

```
.
├── ARCHITECTURE.md              # choix techniques et justifications
├── config.py                    # configuration centrale (villes, chemins, secrets)
├── src/
│   ├── extract.py               # collecte horaire + backfill → data/raw/
│   ├── transform.py             # reconstruction de data/clean/qualite_air.csv
│   └── load.py                  # chargement idempotent dans le warehouse
├── scripts/
│   └── validate_clean.py        # contrôle du contrat de données
├── sql/
│   └── schema.sql                # dim_ville, dim_temps, fact_qualite_air
├── data/
│   ├── raw/                     # fichiers JSON bruts, un par ville et par appel
│   └── clean/                   # qualite_air.csv, régénéré à chaque run
├── .github/workflows/
│   ├── etl.yml                  # cron horaire : extract → transform → validate → load → commit
│   └── backfill.yml             # déclenchement manuel du backfill
├── notebooks/                    # analyses exploratoires éventuelles
└── requirements.txt
```
