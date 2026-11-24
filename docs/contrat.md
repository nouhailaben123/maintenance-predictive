# Contrat de messages : Maintenance prédictive

Version 1.1. Ce document fixe les formats et les noms utilisés par tous les services.
Toute modification doit être validée par les 4 membres de l'équipe.

## 1. Vue d'ensemble

Deux messages circulent dans RabbitMQ :

1. **La mesure**, publiée par l'ingestion-service dans `measures.fanout`.
2. **L'événement de santé**, publié par le monitoring-service dans `health.fanout`.

Le simulateur envoie les mesures à l'ingestion en REST (`POST /measures`).

## 2. Mesure (exchange `measures.fanout`)

```json
{
  "message_id": "b1c9e0f2-7a4d-4c1e-9b3a-5d2f8e6a1c07",
  "machine_id": "M-07",
  "seq": 1842,
  "timestamp": "2026-11-20T10:15:00Z",
  "status": "running",
  "values": {
    "temperature_c": 71.4,
    "vibration_mms": 3.8,
    "power_kw": 22.6,
    "rpm": 2980
  }
}
```

`status` vaut `running`, `idle` ou `stopped`. C'est l'état déclaré par la machine,
distinct de l'état de santé calculé.

## 3. Événement de santé (exchange `health.fanout`)

```json
{
  "event_id": "4e7a2b90-31c5-4d8f-a6e1-0b9c7d5f2a38",
  "machine_id": "M-07",
  "window_end": "2026-11-20T10:15:00Z",
  "health_score": 62,
  "state": "WARN",
  "reasons": ["vibration_zscore>3"],
  "samples": 60
}
```

États de santé possibles : `OK`, `WARN`, `CRIT`, `SILENT` (machine qui n'envoie plus rien).

## 4. Règles sur les champs

| Champ | Règle | Pourquoi |
|---|---|---|
| `message_id` | UUID généré par le simulateur, jamais par l'ingestion | Un renvoi après timeout garde le même identifiant, donc pas de doublon en base |
| `seq` | Compteur croissant par machine | Détecte les pertes, les messages en retard et les doublons |
| `timestamp` | UTC, ISO 8601, heure de la mesure | Le monitoring ordonne par `timestamp`, pas par heure d'arrivée |
| `event_id` | UUID généré par le monitoring | Idempotence côté alertes et côté stockage |

## 5. Exchanges et files

| Exchange (fanout) | File | Consommateur | Rôle |
|---|---|---|---|
| `measures.fanout` | `q.storage` | storage-service | Historique des mesures |
| `measures.fanout` | `q.monitoring` | monitoring-service | Calcul du score de santé |
| `health.fanout` | `q.alerts` | alert-service | Création et résolution des alertes |
| `health.fanout` | `q.health.store` | storage-service | Historique des scores |
| `dead.exchange` | `q.dead` | aucun (inspection manuelle) | Messages invalides ou en échec répété (DLQ) |

Toutes les files sont **durables**. Tous les messages sont **persistants** (`delivery_mode=2`).
Les consommateurs utilisent l'**ack manuel**, seulement après traitement réussi.

## 6. Tables PostgreSQL

- `machines`
- `measurements` (`message_id` UNIQUE)
- `health_scores` (`event_id` UNIQUE)
- `thresholds` (type de machine, metric, limites warn et crit min/max)
- `alerts` (statut `active` ou `resolved`, une seule alerte active par machine et par type)

## 7. API REST de l'ingestion

| Méthode | Route | Rôle | Réponses |
|---|---|---|---|
| POST | `/measures` | Envoyer une mesure | 202 accepté, 401 clé invalide, 422 format invalide, 503 RabbitMQ indisponible |
| POST | `/measures/batch` | Envoyer plusieurs mesures | mêmes codes |

Authentification : en-tête `X-API-Key`.

## 8. Précisions sur les événements de santé (v1.1, proposées par BEN DRIOUICHE Maryam)

### 8.1 Moment de publication
Le monitoring publie un événement dans `health.fanout` :
- à chaque **changement d'état** ;
- puis **un battement toutes les 5 s** par machine (`HEARTBEAT_SEC`), même sans changement.
Il ne publie pas un événement par mesure (pour limiter la charge).

### 8.2 Champs
- `window_end` : timestamp de la dernière mesure de la fenêtre ; pour `SILENT`, heure de détection (UTC).
- `health_score` : entier de 0 à 100. `OK` ≥ 70, `WARN` ≤ 69, `CRIT` ≤ 39, `SILENT` = 0.
  L'état est décidé par les règles (limites, z-score), pas par le score seul.
- `samples` : nombre de mesures dans la fenêtre (60 au maximum).
- `reasons` : liste, valeurs possibles :
  `temperature_warn`, `temperature_crit`, `vibration_warn`, `vibration_crit`, `power_warn`, `power_crit`,
  `rpm_warn`, `rpm_crit`, `temperature_zscore>3`, `vibration_zscore>3`, `power_zscore>3`, `rpm_zscore>3`,
  `no_data>15s`, `declared_idle`, `declared_stopped`.

### 8.3 Machine à l'arrêt
Une mesure avec `status = idle` ou `stopped` ne déclenche **aucune alerte** (état `OK`, raison `declared_*`).
Une machine qui **n'envoie plus rien** passe en `SILENT` après 15 s (`SILENT_TIMEOUT_SEC`).
Le simulateur reproduit l'« arrêt de machine » en **cessant d'émettre**.

### 8.4 Base de données
- `measurements` : `message_id` (UNIQUE), `machine_id`, `seq`, `timestamp`, `status`, `temperature_c`,
  `vibration_mms`, `power_kw`, `rpm` ; index `(machine_id, timestamp)`.
- `machines` : `machine_id`, `type`.
- `thresholds` : `machine_type`, `metric`, `warn_min`, `warn_max`, `crit_min`, `crit_max` ;
  inclut un type `default`.
- Rôle SQL en lecture seule `monitoring_ro` sur `measurements`, `machines`, `thresholds`.

### 8.5 Divers
- L'ingestion publie avec `routing_key = machine_id` (sans effet sur un fanout ; prépare le partitionnement).
- Le monitoring expose `/metrics` sur le port 9102.
- Erreur **définitive** (message illisible, champ manquant) : `nack` sans remise en file → `q.dead`.
  Erreur **transitoire** (broker ou base indisponible) : pas d'ack, le message est redélivré.
- Type d'alerte : déduit par l'alert-service du préfixe de `reasons[0]`.