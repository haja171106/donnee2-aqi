"""
Configuration centrale du pipeline AQI.
Toutes les variables sensibles viennent de l'environnement (.env en local,
secrets de la plateforme en prod) — jamais en dur dans le code.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]  
DATABASE_URL = os.environ["DATABASE_URL"]  

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
CLEAN_FILE = CLEAN_DIR / "qualite_air.csv"

RAW_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

CITIES = [
    {"name": "Antananarivo", "country": "MG", "lat": -18.8792, "lon": 47.5079},
    {"name": "Paris", "country": "FR", "lat": 48.8566, "lon": 2.3522},
    {"name": "Nairobi", "country": "KE", "lat": -1.2921, "lon": 36.8219},
    {"name": "Mumbai", "country": "IN", "lat": 19.0760, "lon": 72.8777},
    {"name": "Beijing", "country": "CN", "lat": 39.9042, "lon": 116.4074},
]

OW_CURRENT_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
OW_HISTORY_URL = "https://api.openweathermap.org/data/2.5/air_pollution/history"

BACKFILL_MONTHS = 3 
