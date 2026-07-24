# Architecture

| Composant | Choix | Justification |
|---|---|---|
| Source de données | OpenWeather Air Pollution API (current + history) | Historique horaire disponible depuis fin 2020, gratuit jusqu'à 1000 appels/jour — suffisant pour 5 villes en backfill + collecte horaire |
| Orchestrateur | GitHub Actions (cron `0 * * * *` + `workflow_dispatch`) | Aucune infra à héberger ni maintenir ; l'historique des runs dans l'onglet Actions sert directement de preuve d'exécution automatique |
| Exécution 24/7 | Runners GitHub Actions à la demande (éphémères) | Le repo lui-même héberge le déclenchement — pas de VM à payer/surveiller ; le cron reste actif tant que le repo a de l'activité (ce qui est garanti puisque chaque run commit des données) |
| Persistance de raw/ et clean/ | Committées dans le dépôt Git à chaque run | Les runners ne gardent aucun état entre deux exécutions ; committer est la façon la plus simple de conserver raw/ (immuable) et clean/ sans service de stockage externe |
| Base / Warehouse | Postgres managé (Supabase ou Neon, plan gratuit) | Hébergement managé, pas de serveur DB à maintenir, accessible en réseau pour IA1 |
| Modélisation | Schéma en étoile (dim_ville, dim_temps, fact_qualite_air) | Suffisant pour le volume du projet (5 villes) ; requêtes simples avec peu de jointures, cf. cours |
