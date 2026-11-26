# Résultats des scénarios de panne

Date : 2026-11-26 21:48 — 3 essai(s) par scénario — machine de test : M-01

| Scénario | Essai | Résultat | Mesures |
|---|---|---|---|
| 5. RabbitMQ coupé + message invalide | 1 | ✅ | {'ingestion_pendant_coupure': 503, 'refus_503_vus_par_ingestion': 19, 'retries_vus_dans_logs_simulateur': 0, 'rabbitmq_pret_s': 13.4, 'monitoring_reconnecte_s': 18.0, 'flux_repris_apres_s': 13.4, 'dlq_apres_s': 4.7, 'manquants': 0, 'doublons': 0, 'mesures_vues': 41} |
| 5. RabbitMQ coupé + message invalide | 2 | ✅ | {'ingestion_pendant_coupure': 503, 'refus_503_vus_par_ingestion': 19, 'retries_vus_dans_logs_simulateur': 0, 'rabbitmq_pret_s': 12.3, 'monitoring_reconnecte_s': 17.6, 'flux_repris_apres_s': 18.6, 'dlq_apres_s': 3.7, 'manquants': 0, 'doublons': 0, 'mesures_vues': 37} |
| 5. RabbitMQ coupé + message invalide | 3 | ✅ | {'ingestion_pendant_coupure': 503, 'refus_503_vus_par_ingestion': 19, 'retries_vus_dans_logs_simulateur': 0, 'rabbitmq_pret_s': 13.4, 'monitoring_reconnecte_s': 18.6, 'flux_repris_apres_s': 18.6, 'dlq_apres_s': 4.7, 'manquants': 0, 'doublons': 0, 'mesures_vues': 41} |

## Moyennes sur les essais

- **5. RabbitMQ coupé + message invalide** : dlq_apres_s = moy 4.4 (min 3.7, max 4.7), doublons = moy 0.0 (min 0.0, max 0.0), flux_repris_apres_s = moy 16.9 (min 13.4, max 18.6), ingestion_pendant_coupure = moy 503.0 (min 503.0, max 503.0), manquants = moy 0.0 (min 0.0, max 0.0), mesures_vues = moy 39.7 (min 37.0, max 41.0), monitoring_reconnecte_s = moy 18.1 (min 17.6, max 18.6), rabbitmq_pret_s = moy 13.0 (min 12.3, max 13.4), refus_503_vus_par_ingestion = moy 19.0 (min 19.0, max 19.0), retries_vus_dans_logs_simulateur = moy 0.0 (min 0.0, max 0.0)
