from prometheus_client import Counter, Gauge, Histogram, start_http_server

MEASURES = Counter("monitoring_measures_processed_total", "Mesures traitées")
DUPLICATES = Counter("monitoring_measures_duplicates_total", "Doublons ignorés")
REJECTED = Counter("monitoring_measures_rejected_total", "Messages invalides envoyés en DLQ")
SEQ_GAPS = Counter("monitoring_seq_gaps_total", "Trous détectés dans seq")
EVENTS = Counter("monitoring_health_events_published_total", "Événements de santé publiés", ["state"])
PENDING = Gauge("monitoring_pending_events", "Événements en attente de publication")
SCORE = Gauge("monitoring_health_score", "Dernier score de santé", ["machine_id"])
PROCESS_SECONDS = Histogram("monitoring_process_seconds", "Durée de traitement d'une mesure")

def start(port: int):
    start_http_server(port)     