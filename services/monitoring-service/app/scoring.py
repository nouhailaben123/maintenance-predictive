import math
from dataclasses import dataclass
from typing import Optional
from . import config as cfg

METRICS = ("temperature_c", "vibration_mms", "power_kw", "rpm")
# Noms courts utilisés dans `reasons` (alignés sur l'exemple du contrat : "vibration_zscore>3")
SHORT = {"temperature_c": "temperature", "vibration_mms": "vibration", "power_kw": "power", "rpm": "rpm"}
SEVERITY = {"OK": 0, "WARN": 1, "CRIT": 2}
STATES = ("OK", "WARN", "CRIT")

@dataclass(frozen=True)
class Limits:
    warn_min: Optional[float] = None
    warn_max: Optional[float] = None
    crit_min: Optional[float] = None
    crit_max: Optional[float] = None

@dataclass(frozen=True)
class Evaluation:
    state: str
    score: int
    reasons: list

def limit_level(x: float, lim: Optional[Limits]) -> int:
    """0 = dans les limites, 1 = au-delà de warn, 2 = au-delà de crit."""
    if lim is None:
        return 0
    if (lim.crit_max is not None and x > lim.crit_max) or (lim.crit_min is not None and x < lim.crit_min):
        return 2
    if (lim.warn_max is not None and x > lim.warn_max) or (lim.warn_min is not None and x < lim.warn_min):
        return 1
    return 0

def zscore(x: float, baseline: list, sigma_min: float) -> Optional[float]:
    n = len(baseline)
    if n < 2:
        return None
    mu = sum(baseline) / n
    var = sum((v - mu) ** 2 for v in baseline) / (n - 1)
    sigma = max(math.sqrt(var), sigma_min)       # plancher : évite la division par ~0
    return (x - mu) / sigma

def evaluate(latest: dict, baseline: dict, limits: dict) -> Evaluation:
    """latest : {métrique: valeur} ; baseline : {métrique: [valeurs de référence]} ;
    limits : {métrique: Limits}."""
    level, penalty, reasons = 0, 0.0, []
    for m in METRICS:
        x = latest[m]
        lv = limit_level(x, limits.get(m))
        if lv == 2:
            level, penalty = 2, penalty + 60
            reasons.append(f"{SHORT[m]}_crit")
        elif lv == 1:
            level, penalty = max(level, 1), penalty + 30
            reasons.append(f"{SHORT[m]}_warn")
        ref = baseline.get(m, [])
        if len(ref) >= cfg.MIN_BASELINE:
            z = zscore(x, ref, cfg.SIGMA_MIN[m])
            if z is not None and abs(z) > 2:
                penalty += min(40, 15 * (abs(z) - 2))
                if abs(z) > cfg.Z_WARN:
                    level = max(level, 1)
                    reasons.append(f"{SHORT[m]}_zscore>{cfg.Z_WARN:g}")
    score = max(0, min(100, round(100 - penalty)))
    if level == 2:
        score = min(score, 39)
    elif level == 1:
        score = min(score, 69)
    else:
        score = max(score, 70)
    return Evaluation(STATES[level], score, reasons)