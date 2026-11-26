# Résultats des scénarios de panne

Date : 2026-11-26 22:32 — 3 essai(s) par scénario — machine de test : M-01

| Scénario | Essai | Résultat | Mesures |
|---|---|---|---|
| 4. Arrêt de storage-service | 1 | ✅ | {'file_pendant_arret': 90, 'publiees_pendant_arret': 117, 'rattrapage_s': 5.4, 'manquants': 0, 'doublons': 0, 'mesures_vues': 161, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'base': {'db_manquants': 0, 'db_doublons': 0}, 'publiees_uniques': 138, 'retrouvees_en_base': 138, 'perdues_avant_la_base': 0} |
| 4. Arrêt de storage-service | 2 | ✅ | {'file_pendant_arret': 105, 'publiees_pendant_arret': 115, 'rattrapage_s': 7.6, 'manquants': 0, 'doublons': 0, 'mesures_vues': 166, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'base': {'db_manquants': 0, 'db_doublons': 0}, 'publiees_uniques': 143, 'retrouvees_en_base': 143, 'perdues_avant_la_base': 0} |
| 4. Arrêt de storage-service | 3 | ✅ | {'file_pendant_arret': 89, 'publiees_pendant_arret': 114, 'rattrapage_s': 5.3, 'manquants': 0, 'doublons': 0, 'mesures_vues': 159, 'faux_silent_apres_redemarrage': 0, 'changements_etat_apres_redemarrage': 0, 'base': {'db_manquants': 0, 'db_doublons': 0}, 'publiees_uniques': 135, 'retrouvees_en_base': 135, 'perdues_avant_la_base': 0} |

## Moyennes sur les essais

- **4. Arrêt de storage-service** : changements_etat_apres_redemarrage = moy 0.0 (min 0.0, max 0.0), doublons = moy 0.0 (min 0.0, max 0.0), faux_silent_apres_redemarrage = moy 0.0 (min 0.0, max 0.0), file_pendant_arret = moy 94.7 (min 89.0, max 105.0), manquants = moy 0.0 (min 0.0, max 0.0), mesures_vues = moy 162.0 (min 159.0, max 166.0), perdues_avant_la_base = moy 0.0 (min 0.0, max 0.0), publiees_pendant_arret = moy 115.3 (min 114.0, max 117.0), publiees_uniques = moy 138.7 (min 135.0, max 143.0), rattrapage_s = moy 6.1 (min 5.3, max 7.6), retrouvees_en_base = moy 138.7 (min 135.0, max 143.0)
