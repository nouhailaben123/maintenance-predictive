# Résultats des scénarios de panne

Date : 2026-11-27 00:02 — 1 essai(s) par scénario — machine de test : M-01

| Scénario | Essai | Résultat | Mesures |
|---|---|---|---|
| 6. Faux positifs (aucune panne injectée) | 1 | ✅ | {'reglage': 'Z_WARN=3 (defaut)', 'machines': 3, 'observation_min': 30.0, 'fausses_alertes': 4, 'par_heure': 8.0, 'par_machine_et_heure': 2.67, 'duree_moyenne_s': 5.3, 'duree_max_s': 6.0, 'dont_crit': 0, 'dont_silence': 0, 'causes': {'ecart_statistique': 4}, 'detail': ["M-01 WARN ['rpm_zscore>3'] 5.0s", "M-01 WARN ['power_zscore>3'] 5.1s", "M-03 WARN ['rpm_zscore>3'] 6.0s", "M-02 WARN ['rpm_zscore>3'] 5.1s"]} |

## Moyennes sur les essais

