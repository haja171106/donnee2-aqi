# Architecture du pipeline

## Vue d'ensemble

Le système est construit comme une chaîne de trois transformations successives, entièrement rejouées à chaque exécution : une collecte qui produit des archives brutes, une reconstruction qui en dérive un fichier propre unique, et un chargement qui synchronise ce fichier avec un entrepôt relationnel. Chaque étape ne dépend que du résultat de la précédente, jamais de son propre état antérieur — ce qui permet de relancer n'importe quelle étape sans risque d'incohérence.

```
OpenWeather Air Pollution API
        │  un appel « current » par ville chaque heure
        │  + appels « history » par tranches de 7 jours pour le backfill
        ▼
GitHub Actions (cron horaire + déclenchement manuel)
        ▼
data/raw/     archives JSON, un fichier par ville et par appel, jamais réécrites
data/clean/   qualite_air.csv, régénéré en entier à chaque run depuis raw/
        ▼
Neon (Postgres managé) — dim_ville, dim_temps, fact_qualite_air
```

## La source de données

L'API OpenWeather Air Pollution a été retenue plutôt qu'une alternative comme OpenAQ ou IQAir parce qu'elle fournit à la fois un endpoint temps réel et un endpoint historique horaire remontant à fin 2020, dans le même format de réponse. Cela évite d'avoir à combiner deux sources différentes pour la collecte continue et le backfill : le module d'extraction (`src/extract.py`) utilise le même parseur pour les deux modes. Le quota gratuit (1000 appels/jour) suffit largement aux besoins du projet : cinq appels par heure en continu, plus quelques dizaines d'appels ponctuels lors d'un backfill.

## L'orchestrateur

GitHub Actions a été choisi plutôt qu'un orchestrateur dédié (Airflow, Prefect, Dagster) ou un outil no-code (n8n, Make). La raison principale est qu'il ne demande aucune infrastructure à faire tourner en dehors du dépôt lui-même : pas de serveur à payer, pas de service à surveiller pour qu'il reste en vie. Le cron (`0 * * * *`) déclenche un runner éphémère chaque heure, qui exécute extraction, transformation, validation et chargement dans une seule tâche, puis s'éteint. L'onglet **Actions** du dépôt donne directement, sans outil supplémentaire, l'historique complet des exécutions passées — un run réussi ou en échec, à quelle heure, avec les logs de chaque étape.

Ce choix a une contrepartie assumée : les runners GitHub Actions n'ont pas de disque persistant entre deux exécutions. C'est pour cette raison que `data/raw/` et `data/clean/` sont recommittés dans le dépôt Git à la fin de chaque run (dernière étape du workflow `etl.yml`) : le dépôt fait à la fois office de code source et de support de stockage pour les deux couches de fichiers.

Un second workflow, `backfill.yml`, est séparé du cycle horaire et se déclenche manuellement avec le nombre de mois d'historique en paramètre — il n'a pas vocation à tourner en continu, seulement à être rejoué si l'historique doit être reconstruit ou étendu.

## Le stockage des fichiers

`data/raw/` et `data/clean/` vivent comme de simples fichiers versionnés dans le dépôt Git plutôt que dans un bucket S3 ou équivalent. Ce choix découle directement de celui de l'orchestrateur : puisque GitHub Actions committe déjà le code à chaque run, ajouter les données au même commit évite d'introduire un service de stockage supplémentaire et ses propres identifiants à gérer. La contrepartie est que le dépôt grossit au fil du temps avec l'historique JSON — un compromis jugé acceptable à l'échelle de cinq villes et d'un projet de cours.

`data/raw/` n'est jamais modifié après écriture : chaque appel API produit un nouveau fichier horodaté, ce qui en fait une pile d'archives immuable. `data/clean/qualite_air.csv` est à l'inverse écrasé et régénéré en entier à chaque run, à partir de la totalité de `raw/` — ce choix (plutôt qu'un append incrémental) simplifie la déduplication : il suffit de dédupliquer sur la paire (ville, timestamp) sur l'ensemble des données à chaque reconstruction, sans avoir à gérer un état intermédiaire entre deux runs.

## L'entrepôt de données

Le warehouse est hébergé sur **Neon**, un service Postgres serverless managé. Ce choix évite d'avoir à provisionner et maintenir un serveur de base de données pour un projet dont la charge est faible et intermittente (une écriture par heure) : Neon met la base en veille automatiquement entre deux utilisations et la réactive à la demande, ce qui correspond bien au rythme du pipeline. La connexion se fait via une simple chaîne `DATABASE_URL`, ce qui rend la base accessible en réseau pour une consommation externe par le cours IA1, sans configuration réseau supplémentaire à opérer.

Le chargement (`src/load.py`) utilise des `INSERT ... ON CONFLICT` sur les clés naturelles de chaque table, ce qui rend le script rejouable à volonté sans jamais dupliquer une ligne, même si le même run est relancé plusieurs fois sur les mêmes données.

## La modélisation

Le schéma retenu est une étoile à deux dimensions (`dim_ville`, `dim_temps`) autour d'une seule table de faits (`fact_qualite_air`). Un flocon aurait par exemple pu séparer `dim_temps` en une hiérarchie date/heure distincte, mais cela n'apporte rien à l'échelle de cinq villes et d'un seul axe de mesure : l'étoile garde les requêtes d'analyse à une seule jointure par dimension, ce qui suffit largement aux besoins du projet. La table de faits ne contient que des clés étrangères et des mesures (AQI, huit polluants) ; aucune colonne descriptive (nom de ville, libellé temporel) n'y figure, et inversement aucune mesure n'apparaît dans les dimensions — ces deux règles sont vérifiées directement dans la définition SQL des tables (`sql/schema.sql`).

## Récapitulatif

| Composant | Choix | Pourquoi |
|---|---|---|
| Source de données | OpenWeather Air Pollution API | Un seul format pour le temps réel et l'historique horaire depuis fin 2020 ; quota gratuit suffisant |
| Orchestrateur | GitHub Actions (cron + déclenchement manuel) | Aucune infrastructure à héberger ; l'onglet Actions sert directement de preuve d'exécution |
| Stockage raw/ et clean/ | Fichiers versionnés dans le dépôt Git | Cohérent avec des runners éphémères qui committent déjà le code à chaque run |
| Warehouse | Neon (Postgres serverless managé) | Pas de serveur à maintenir, mise en veille automatique adaptée à une charge horaire, accessible en réseau pour IA1 |
| Modélisation | Schéma en étoile | Deux dimensions et un seul axe de mesure ne justifient pas la normalisation supplémentaire d'un flocon |