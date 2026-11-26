import logging
import time
import psycopg

from . import config as cfg
from .scoring import Limits
from .window import Sample

log = logging.getLogger("db")

# ⏳ Étudiant 2 : adapter les noms de tables/colonnes au init.sql final
SQL_THRESHOLDS = "SELECT machine_type, metric, warn_min, warn_max, crit_min, crit_max FROM thresholds"
SQL_MACHINES = "SELECT machine_id, type FROM machines"
SQL_WINDOWS = """
SELECT message_id, machine_id, seq, "timestamp", status,
       temperature_c, vibration_mms, power_kw, rpm
FROM (
    SELECT *, row_number() OVER (PARTITION BY machine_id ORDER BY "timestamp" DESC) AS rn
    FROM measurements
    WHERE "timestamp" > now() - make_interval(mins => %s)
) t
WHERE rn <= %s
ORDER BY machine_id, "timestamp"
"""

def refresh_reference(engine) -> bool:
    """Recharge seuils et types de machines. Échec silencieux : on garde le cache."""
    try:
        with psycopg.connect(cfg.PG_DSN) as conn:
            th: dict = {}
            for t, metric, wmin, wmax, cmin, cmax in conn.execute(SQL_THRESHOLDS):
                th.setdefault(t, {})[metric] = Limits(wmin, wmax, cmin, cmax)
            engine.thresholds = th
            engine.machine_types = dict(conn.execute(SQL_MACHINES).fetchall())
        return True
    except psycopg.Error as exc:
        log.warning("Rechargement des seuils impossible : %s", exc)
        return False

def rebuild_windows(engine) -> bool:
    """Reconstruit les fenêtres depuis PostgreSQL (le monitoring est le seul service à état)."""
    for attempt in range(1, cfg.REBUILD_RETRIES + 1):
        try:
            with psycopg.connect(cfg.PG_DSN) as conn:
                rows = conn.execute(SQL_WINDOWS, (cfg.REBUILD_LOOKBACK_MIN, cfg.WINDOW_SIZE)).fetchall()
            from .engine import MachineState
            for (mid_msg, mid, seq, ts, status, t, v, p, r) in rows:
                m = engine.machines.setdefault(mid, MachineState())
                if m.window.add(Sample(mid_msg, mid, seq, ts, status,
                                       {"temperature_c": t, "vibration_mms": v, "power_kw": p, "rpm": r})):
                    m.last_seq = seq if m.last_seq is None else max(m.last_seq, seq)
                    m.last_window_end = ts
            now = time.monotonic()
            for m in engine.machines.values():
                m.last_seen = now        # le compte à rebours SILENT repart à zéro
            log.info("Fenêtres reconstruites : %d machines, %d mesures", len(engine.machines), len(rows))
            return True
        except psycopg.Error as exc:
            log.warning("PostgreSQL indisponible (tentative %d/%d) : %s", attempt, cfg.REBUILD_RETRIES, exc)
            time.sleep(2)
    log.error("Reconstruction impossible : démarrage avec des fenêtres vides (mode dégradé)")
    return False