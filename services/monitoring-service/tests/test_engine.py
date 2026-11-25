from datetime import datetime, timedelta, timezone
from app import config as cfg
from app.engine import Engine
from app.scoring import Limits
from app.window import Sample

T0 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)

def mk(seq, temp=70.0, status="running"):
    return Sample(f"id-{seq}", "M-01", seq, T0 + timedelta(seconds=seq), status,
                  {"temperature_c": temp, "vibration_mms": 3.8, "power_kw": 22.0, "rpm": 2980.0})

def new_engine():
    e = Engine()
    e.thresholds = {"default": {"temperature_c": Limits(warn_max=80, crit_max=90)}}
    return e

def test_duplicate_is_ignored():
    e = new_engine()
    assert e.process(mk(1), now=0) is True
    assert e.process(mk(1), now=1) is False          # même message_id

def test_state_change_requires_confirmation():
    e = new_engine()
    for i in range(1, 45): e.process(mk(i), now=i)
    e.process(mk(45, temp=85), now=45)               # 1ère mesure WARN : pas encore confirmée
    assert e.machines["M-01"].stable == "OK"
    e.process(mk(46, temp=85), now=46)               # 2e : confirmée (ESCALATE_CONFIRM=2)
    assert e.machines["M-01"].stable == "WARN"

def test_silent_after_timeout_then_recovers():
    e = new_engine()
    for i in range(1, 5): e.process(mk(i), now=i)
    e.tick(now=4 + cfg.SILENT_TIMEOUT_SEC + 1)
    assert e.machines["M-01"].stable == "SILENT"
    e.process(mk(5), now=100)                        # reprise des mesures
    assert e.machines["M-01"].stable == "OK"

def test_event_published_on_state_change():
    e = new_engine()
    e.process(mk(1), now=0)
    assert e.pending and e.pending[-1]["state"] == "OK"

def test_declared_stopped_is_not_an_alert():
    e = new_engine()
    e.process(mk(1, temp=0, status="stopped"), now=0)
    assert e.machines["M-01"].stable == "OK"
    
def test_published_score_matches_state_bands():
    """Contrat v1.1 : OK >= 70, WARN <= 69, CRIT <= 39, SILENT = 0."""
    e = new_engine()
    e.process(mk(1), now=0)
    m = e.machines["M-01"]
    for state, raw, lo, hi in [("OK", 40, 70, 100), ("WARN", 88, 0, 69),
                               ("CRIT", 88, 0, 39), ("SILENT", 50, 0, 0)]:
        m.stable, m.score = state, raw
        assert lo <= e._score_for_state(m) <= hi