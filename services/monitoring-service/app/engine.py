import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from . import config as cfg, metrics
from .scoring import SEVERITY, Limits, evaluate
from .window import Sample, Window

log = logging.getLogger("engine")

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

class MachineState:
    def __init__(self):
        self.window = Window(cfg.WINDOW_SIZE)
        self.stable = None            # None tant qu'aucune évaluation
        self.candidate = None
        self.streak = 0
        self.score = 100
        self.reasons: list = []
        self.last_seen = time.monotonic()
        self.last_seq = None
        self.last_window_end = None
        self.last_published = None
        self.last_publish_at = 0.0

    def update(self, raw: str):
        """Debounce : n'aggrave / ne récupère qu'après N confirmations."""
        if self.stable in (None, "SILENT"):          # sortie de SILENT : immédiate
            self.stable, self.candidate, self.streak = raw, None, 0
            return
        if raw == self.stable:
            self.candidate, self.streak = None, 0
            return
        self.streak = self.streak + 1 if raw == self.candidate else 1
        self.candidate = raw
        need = cfg.ESCALATE_CONFIRM if SEVERITY[raw] > SEVERITY[self.stable] else cfg.RECOVER_CONFIRM
        if self.streak >= need:
            self.stable, self.candidate, self.streak = raw, None, 0

class Engine:
    def __init__(self):
        self.machines: dict = {}
        self.pending: deque = deque(maxlen=10000)   # événements créés, pas encore confirmés
        self.thresholds: dict = {}                  # {type: {métrique: Limits}}
        self.machine_types: dict = {}               # {machine_id: type}

    # ---------- seuils ----------
    def limits_for(self, machine_id: str) -> dict:
        t = self.machine_types.get(machine_id)
        return self.thresholds.get(t) or self.thresholds.get("default") or {}

    # ---------- traitement d'une mesure ----------
    def process(self, s: Sample, now: float | None = None) -> bool:
        """Retourne False si doublon. Ne publie rien : les événements vont dans `pending`."""
        now = time.monotonic() if now is None else now
        m = self.machines.setdefault(s.machine_id, MachineState())
        m.last_seen = now

        if s.status != "running":                    # machine arrêtée/en veille déclarée
            m.score, m.reasons = 100, [f"declared_{s.status}"]
            m.update("OK")
            m.last_window_end = s.timestamp
            self._publish_if_due(s.machine_id, m, now, s.timestamp)
            return True

        if not m.window.add(s):
            metrics.DUPLICATES.inc()
            return False

        if m.last_seq is not None and s.seq > m.last_seq + 1:
            metrics.SEQ_GAPS.inc(s.seq - m.last_seq - 1)
            log.warning("Trou de seq pour %s : %d -> %d", s.machine_id, m.last_seq, s.seq)
        m.last_seq = s.seq if m.last_seq is None else max(m.last_seq, s.seq)

        latest = m.window.items[-1]
        baseline = {k: m.window.baseline(k, cfg.BASELINE_SKIP_LAST) for k in latest.values}
        ev = evaluate(latest.values, baseline, self.limits_for(s.machine_id))
        m.score, m.reasons = ev.score, ev.reasons
        m.update(ev.state)
        m.last_window_end = latest.timestamp
        metrics.MEASURES.inc()
        metrics.SCORE.labels(s.machine_id).set(m.score)
        self._publish_if_due(s.machine_id, m, now, latest.timestamp)
        return True

    # ---------- horloge : SILENT + battement (indépendant des messages) ----------
    def tick(self, now: float | None = None):
        now = time.monotonic() if now is None else now
        for mid, m in self.machines.items():
            if m.stable not in (None, "SILENT") and now - m.last_seen > cfg.SILENT_TIMEOUT_SEC:
                log.warning("%s : aucune mesure depuis %.0fs -> SILENT", mid, now - m.last_seen)
                m.stable, m.score = "SILENT", 0
                m.reasons = [f"no_data>{cfg.SILENT_TIMEOUT_SEC:g}s"]
                m.candidate, m.streak = None, 0
                metrics.SCORE.labels(mid).set(0)
            window_end = datetime.now(timezone.utc) if m.stable == "SILENT" else m.last_window_end
            if window_end is not None:
                self._publish_if_due(mid, m, now, window_end)

    # ---------- événements ----------
    def _publish_if_due(self, mid, m, now, window_end):
        if m.stable is None:
            return
        due = m.stable != m.last_published or now - m.last_publish_at >= cfg.HEARTBEAT_SEC
        if not due:
            return
        self.pending.append({
            "event_id": str(uuid.uuid4()),
            "machine_id": mid,
            "window_end": iso(window_end),
            "health_score": m.score,
            "state": m.stable,
            "reasons": m.reasons,
            "samples": len(m.window),
        })
        m.last_published, m.last_publish_at = m.stable, now
        metrics.PENDING.set(len(self.pending))
        log.info("Événement %s %s score=%s %s", mid, m.stable, m.score, m.reasons)