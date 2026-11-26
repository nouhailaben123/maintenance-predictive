# Résultats des scénarios de panne

Date : 2026-11-26 20:36 — 3 essai(s) par scénario — machine de test : M-01

| Scénario | Essai | Résultat | Mesures |
|---|---|---|---|
| 1. Surchauffe | 1 | ✅ | {'delai_warn_s': 4.1, 'delai_crit_s': 16.2, 'raisons_crit': ['temperature_crit', 'temperature_zscore>3'], 'etats': 'WARN->CRIT', 'alertes_en_base': None, 'retour_ok_s': 5.0} |
| 1. Surchauffe | 2 | ✅ | {'delai_warn_s': 9.1, 'delai_crit_s': 14.2, 'raisons_crit': ['temperature_crit'], 'etats': 'OK->WARN->CRIT', 'alertes_en_base': None, 'retour_ok_s': 5.0} |
| 1. Surchauffe | 3 | ✅ | {'delai_warn_s': 8.1, 'delai_crit_s': 15.2, 'raisons_crit': ['temperature_crit'], 'etats': 'OK->WARN->CRIT', 'alertes_en_base': None, 'retour_ok_s': 5.1} |
| 2. Dérive de vibration | 1 | ✅ | {'premier_etat': 'WARN', 'raisons': ['vibration_zscore>3'], 'delai_detection_s': 17.2, 'limite_warn_franchie_apres_s': 48.7, 'avance_sur_limite_warn_s': 31.4, 'limite_crit_franchie_apres_s': 88.3, 'avance_sur_limite_crit_s': 71.1, 'retour_ok_s': 18.3} |
| 2. Dérive de vibration | 2 | ❌ | {'premier_etat': 'WARN', 'raisons': ['vibration_warn', 'vibration_zscore>3'], 'delai_detection_s': 39.7, 'limite_warn_franchie_apres_s': 39.7, 'avance_sur_limite_warn_s': -0.0, 'limite_crit_franchie_apres_s': 89.3, 'avance_sur_limite_crit_s': 49.6, 'retour_ok_s': 17.7} |
| 2. Dérive de vibration | 3 | ❌ | {'premier_etat': 'WARN', 'raisons': ['vibration_warn', 'vibration_zscore>3'], 'delai_detection_s': 52.3, 'limite_warn_franchie_apres_s': 51.2, 'avance_sur_limite_warn_s': -1.0, 'limite_crit_franchie_apres_s': 80.6, 'avance_sur_limite_crit_s': 28.4, 'retour_ok_s': 5.1} |
| 3. Machine silencieuse | 1 | ✅ | {'delai_silent_s': 14.8, 'raisons': ['no_data>15s'], 'score': 0, 'delai_reprise_s': 1.0, 'alertes_en_base': None} |
| 3. Machine silencieuse | 2 | ✅ | {'delai_silent_s': 15.3, 'raisons': ['no_data>15s'], 'score': 0, 'delai_reprise_s': 1.0, 'alertes_en_base': None} |
| 3. Machine silencieuse | 3 | ✅ | {'delai_silent_s': 15.3, 'raisons': ['no_data>15s'], 'score': 0, 'delai_reprise_s': 0.5, 'alertes_en_base': None} |
| 4. Arrêt de storage-service | 1 | ⏭ ignoré | {'note': "service 'storage-service' absent du docker-compose (pas encore livré)"} |
| 4. Arrêt de storage-service | 2 | ⏭ ignoré | {'note': "service 'storage-service' absent du docker-compose (pas encore livré)"} |
| 4. Arrêt de storage-service | 3 | ⏭ ignoré | {'note': "service 'storage-service' absent du docker-compose (pas encore livré)"} |
| 4. Arrêt de monitoring-service | 1 | ✅ | {'file_pendant_arret': 87, 'publiees_pendant_arret': 113, 'rattrapage_s': 5.9, 'manquants': 0, 'doublons': 0, 'mesures_vues': 161, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'seq_trous_vus_par_monitoring': 0.0, 'doublons_ignores_par_monitoring': 0.0, 'log_fenetres_reconstruites': True} |
| 4. Arrêt de monitoring-service | 2 | ✅ | {'file_pendant_arret': 99, 'publiees_pendant_arret': 117, 'rattrapage_s': 2.1, 'manquants': 0, 'doublons': 0, 'mesures_vues': 150, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'seq_trous_vus_par_monitoring': 0.0, 'doublons_ignores_par_monitoring': 0.0, 'log_fenetres_reconstruites': True} |
| 4. Arrêt de monitoring-service | 3 | ✅ | {'file_pendant_arret': 90, 'publiees_pendant_arret': 117, 'rattrapage_s': 8.0, 'manquants': 0, 'doublons': 0, 'mesures_vues': 168, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'seq_trous_vus_par_monitoring': 0.0, 'doublons_ignores_par_monitoring': 0.0, 'log_fenetres_reconstruites': True} |
| 5. RabbitMQ coupé + message invalide | 1 | ✅ | {'ingestion_pendant_coupure': 503, 'retries_du_simulateur': 0, 'monitoring_reconnecte_s': 42.9, 'flux_repris_apres_s': 0.0, 'dlq_apres_s': 4.8, 'manquants': 0, 'doublons': 0, 'mesures_vues': 113} |
| 5. RabbitMQ coupé + message invalide | 2 | ✅ | {'ingestion_pendant_coupure': 503, 'retries_du_simulateur': 0, 'monitoring_reconnecte_s': 43.3, 'flux_repris_apres_s': 0.0, 'dlq_apres_s': 4.7, 'manquants': 0, 'doublons': 0, 'mesures_vues': 111} |
| 5. RabbitMQ coupé + message invalide | 3 | ✅ | {'ingestion_pendant_coupure': 503, 'retries_du_simulateur': 0, 'monitoring_reconnecte_s': 43.5, 'flux_repris_apres_s': 0.0, 'dlq_apres_s': 4.8, 'manquants': 0, 'doublons': 0, 'mesures_vues': 113} |

## Moyennes sur les essais

- **1. Surchauffe** : delai_crit_s = moy 15.2 (min 14.2, max 16.2), delai_warn_s = moy 7.1 (min 4.1, max 9.1), retour_ok_s = moy 5.0 (min 5.0, max 5.1)
- **2. Dérive de vibration** : avance_sur_limite_crit_s = moy 49.7 (min 28.4, max 71.1), avance_sur_limite_warn_s = moy 10.1 (min -1.0, max 31.4), delai_detection_s = moy 36.4 (min 17.2, max 52.3), limite_crit_franchie_apres_s = moy 86.1 (min 80.6, max 89.3), limite_warn_franchie_apres_s = moy 46.5 (min 39.7, max 51.2), retour_ok_s = moy 13.7 (min 5.1, max 18.3)
- **3. Machine silencieuse** : delai_reprise_s = moy 0.8 (min 0.5, max 1.0), delai_silent_s = moy 15.1 (min 14.8, max 15.3), score = moy 0.0 (min 0.0, max 0.0)
- **4. Arrêt de monitoring-service** : changements_etat_apres_redemarrage = moy 0.0 (min 0.0, max 0.0), doublons = moy 0.0 (min 0.0, max 0.0), doublons_ignores_par_monitoring = moy 0.0 (min 0.0, max 0.0), faux_silent_apres_redemarrage = moy 0.0 (min 0.0, max 0.0), file_pendant_arret = moy 92.0 (min 87.0, max 99.0), manquants = moy 0.0 (min 0.0, max 0.0), mesures_vues = moy 159.7 (min 150.0, max 168.0), publiees_pendant_arret = moy 115.7 (min 113.0, max 117.0), rattrapage_s = moy 5.3 (min 2.1, max 8.0), seq_trous_vus_par_monitoring = moy 0.0 (min 0.0, max 0.0)
- **5. RabbitMQ coupé + message invalide** : dlq_apres_s = moy 4.8 (min 4.7, max 4.8), doublons = moy 0.0 (min 0.0, max 0.0), flux_repris_apres_s = moy 0.0 (min 0.0, max 0.0), ingestion_pendant_coupure = moy 503.0 (min 503.0, max 503.0), manquants = moy 0.0 (min 0.0, max 0.0), mesures_vues = moy 112.3 (min 111.0, max 113.0), monitoring_reconnecte_s = moy 43.2 (min 42.9, max 43.5), retries_du_simulateur = moy 0.0 (min 0.0, max 0.0)
