# Résultats des scénarios de panne

Date : 2026-11-26 21:40 — 3 essai(s) par scénario — machine de test : M-01

| Scénario | Essai | Résultat | Mesures |
|---|---|---|---|
| 2. Dérive de vibration | 1 | ✅ | {'premier_etat': 'WARN', 'raisons': ['vibration_zscore>3'], 'delai_detection_s': 21.6, 'limite_warn_franchie_apres_s': 48.0, 'avance_sur_limite_warn_s': 26.4, 'limite_crit_franchie_apres_s': 88.4, 'avance_sur_limite_crit_s': 66.8, 'retour_ok_s': 16.7} |
| 2. Dérive de vibration | 2 | ✅ | {'premier_etat': 'WARN', 'raisons': ['vibration_zscore>3'], 'delai_detection_s': 31.1, 'limite_warn_franchie_apres_s': 47.7, 'avance_sur_limite_warn_s': 16.5, 'limite_crit_franchie_apres_s': 82.7, 'avance_sur_limite_crit_s': 51.6, 'retour_ok_s': 15.7} |
| 2. Dérive de vibration | 3 | ✅ | {'premier_etat': 'WARN', 'raisons': ['vibration_zscore>3'], 'delai_detection_s': 23.8, 'limite_warn_franchie_apres_s': 39.1, 'avance_sur_limite_warn_s': 15.3, 'limite_crit_franchie_apres_s': 80.9, 'avance_sur_limite_crit_s': 57.1, 'retour_ok_s': 23.6} |

## Moyennes sur les essais

- **2. Dérive de vibration** : avance_sur_limite_crit_s = moy 58.5 (min 51.6, max 66.8), avance_sur_limite_warn_s = moy 19.4 (min 15.3, max 26.4), delai_detection_s = moy 25.5 (min 21.6, max 31.1), limite_crit_franchie_apres_s = moy 84.0 (min 80.9, max 88.4), limite_warn_franchie_apres_s = moy 44.9 (min 39.1, max 48.0), retour_ok_s = moy 18.7 (min 15.7, max 23.6)
