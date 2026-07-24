CREATE TABLE IF NOT EXISTS dim_ville (
    id_ville   SERIAL PRIMARY KEY,
    nom        TEXT NOT NULL,
    pays       TEXT NOT NULL,
    latitude   DOUBLE PRECISION NOT NULL,
    longitude  DOUBLE PRECISION NOT NULL,
    UNIQUE (nom, pays)
);

CREATE TABLE IF NOT EXISTS dim_temps (
    id_temps       SERIAL PRIMARY KEY,
    timestamp_utc  TIMESTAMPTZ NOT NULL UNIQUE,  
    date           DATE NOT NULL,
    heure          SMALLINT NOT NULL,             
    jour_semaine   TEXT NOT NULL,                 
    is_weekend     BOOLEAN NOT NULL,
    mois           SMALLINT NOT NULL,
    trimestre      SMALLINT NOT NULL,
    annee          SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_qualite_air (
    id_temps  INTEGER NOT NULL REFERENCES dim_temps(id_temps),
    id_ville  INTEGER NOT NULL REFERENCES dim_ville(id_ville),
    aqi       SMALLINT,        
    co        DOUBLE PRECISION,  
    no        DOUBLE PRECISION,
    no2       DOUBLE PRECISION,
    o3        DOUBLE PRECISION,
    so2       DOUBLE PRECISION,
    pm2_5     DOUBLE PRECISION,
    pm10      DOUBLE PRECISION,
    nh3       DOUBLE PRECISION,
    PRIMARY KEY (id_temps, id_ville)  
);

CREATE INDEX IF NOT EXISTS idx_fact_ville ON fact_qualite_air(id_ville);
CREATE INDEX IF NOT EXISTS idx_fact_temps ON fact_qualite_air(id_temps);
