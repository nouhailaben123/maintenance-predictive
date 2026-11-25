import os

def _f(name, default): return float(os.getenv(name, default))
def _i(name, default): return int(os.getenv(name, default))

# RabbitMQ
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = _i("RABBITMQ_PORT", 5672)
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
QUEUE = "q.monitoring"
HEALTH_EXCHANGE = "health.fanout"
PREFETCH = _i("PREFETCH", 100)

# PostgreSQL (rôle lecture seule)
PG_DSN = (f"host={os.getenv('POSTGRES_HOST', 'postgres')} port={_i('POSTGRES_PORT', 5432)} "
          f"dbname={os.getenv('POSTGRES_DB', 'maintenance')} "
          f"user={os.getenv('MONITORING_DB_USER', os.getenv('POSTGRES_USER', 'admin'))} "
          f"password={os.getenv('MONITORING_DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))} "
          f"connect_timeout=3")

# Fenêtre et score
WINDOW_SIZE = _i("WINDOW_SIZE", 60)
BASELINE_SKIP_LAST = _i("BASELINE_SKIP_LAST", 10)   # mesures récentes exclues de la référence
MIN_BASELINE = _i("MIN_BASELINE", 30)
Z_WARN = _f("Z_WARN", 3.0)
SIGMA_MIN = {                                       # plancher d'écart-type par métrique
    "temperature_c": _f("SIGMA_MIN_TEMP", 0.5),
    "vibration_mms": _f("SIGMA_MIN_VIB", 0.1),
    "power_kw": _f("SIGMA_MIN_POWER", 0.3),
    "rpm": _f("SIGMA_MIN_RPM", 10.0),
}

# États
ESCALATE_CONFIRM = _i("ESCALATE_CONFIRM", 2)
RECOVER_CONFIRM = _i("RECOVER_CONFIRM", 5)
SILENT_TIMEOUT_SEC = _f("SILENT_TIMEOUT_SEC", 15)
HEARTBEAT_SEC = _f("HEARTBEAT_SEC", 5)

# Divers
THRESHOLD_REFRESH_SEC = _f("THRESHOLD_REFRESH_SEC", 60)
REBUILD_LOOKBACK_MIN = _i("REBUILD_LOOKBACK_MIN", 10)
REBUILD_RETRIES = _i("REBUILD_RETRIES", 30)
METRICS_PORT = _i("METRICS_PORT", 9102)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")