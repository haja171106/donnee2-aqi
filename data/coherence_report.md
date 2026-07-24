# ## Période couverte et trous connus

- Période couverte : `2026-04-25T20:00:00Z` → `2026-07-24T19:02:28Z` (mise à jour horaire continue depuis le premier run réussi, complétée par un backfill de 3 mois)
- Couverture globale : 10 431 lignes de faits sur 10 800 théoriques (5 villes × 2160 heures), soit un écart de 369 lignes (3,42 %)

| Ville | Lignes | Heures manquantes | Taux de couverture |
|---|---|---|---|
| Antananarivo | 2091 | 72 | 96,67 % |
| Paris | 2091 | 72 | 96,67 % |
| Nairobi | 2091 | 72 | 96,67 % |
| Mumbai | 2091 | 72 | 96,67 % |
| Beijing | 2067 | 96 | 95,56 % |

**Causes identifiées** (vérifiées à l'heure près via `scripts/check_coherence.py` et une requête SQL de détection de trous) :

- Trois journées complètes sont absentes pour **toutes les villes simultanément** : le 11 mai, le 19 mai et le 10 juillet 2026. Le motif (24h consécutives manquantes, identique pour 5 villes indépendantes) exclut une panne réseau isolée côté pipeline et pointe vers une lacune de l'historique disponible sur l'endpoint `air_pollution/history` d'OpenWeather à ces dates précises.
- Une quatrième journée, le 24 mai 2026, est absente **uniquement pour Beijing**. Cette anomalie isolée à une seule ville suggère un échec ponctuel du chunk de backfill correspondant à cette plage pour ces coordonnées, plutôt qu'une cause partagée.
- Aucun autre trou n'a été détecté sur le reste de la période : la collecte horaire continue fonctionne sans interruption en dehors de ces quatre journées.

Ces trous peuvent être comblés en rejouant sélectivement le backfill sur les plages concernées, via `python -m src.extract --mode backfill` avec des bornes de dates ciblées.
