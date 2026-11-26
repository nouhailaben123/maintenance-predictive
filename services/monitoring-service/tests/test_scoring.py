from app.scoring import Limits, evaluate, limit_level, zscore

LIM = {"temperature_c": Limits(warn_max=80, crit_max=90),
       "vibration_mms": Limits(warn_max=6, crit_max=8)}
NORMAL = {"temperature_c": 70.0, "vibration_mms": 3.8, "power_kw": 22.0, "rpm": 2980.0}
REF = {k: [v + d for d in (-0.2, 0.1, 0.0, 0.2, -0.1) * 8] for k, v in NORMAL.items()}  # 40 valeurs

def test_limit_levels():
    assert limit_level(79, LIM["temperature_c"]) == 0
    assert limit_level(81, LIM["temperature_c"]) == 1
    assert limit_level(91, LIM["temperature_c"]) == 2

def test_normal_is_ok_and_high_score():
    ev = evaluate(NORMAL, REF, LIM)
    assert ev.state == "OK" and ev.score >= 70

def test_warn_limit():
    ev = evaluate({**NORMAL, "temperature_c": 85}, REF, LIM)
    assert ev.state == "WARN" and ev.score <= 69

def test_crit_limit():
    ev = evaluate({**NORMAL, "temperature_c": 95}, REF, LIM)
    assert ev.state == "CRIT" and ev.score <= 39

def test_zscore_warns_before_limit():
    """Dérive : sous la limite warn (6) mais très loin de la référence -> WARN prédictif."""
    ev = evaluate({**NORMAL, "vibration_mms": 4.8}, REF, LIM)
    assert ev.state == "WARN"
    assert any("zscore" in r for r in ev.reasons)

def test_sigma_floor_avoids_false_alarm():
    flat = {k: [v] * 40 for k, v in NORMAL.items()}       # signal parfaitement plat (σ=0)
    ev = evaluate({**NORMAL, "temperature_c": 70.2}, flat, LIM)
    assert ev.state == "OK"

def test_zscore_needs_two_points():
    assert zscore(1.0, [1.0], 0.1) is None

def test_score_decreases_with_deviation():
    a = evaluate({**NORMAL, "vibration_mms": 4.2}, REF, LIM).score
    b = evaluate({**NORMAL, "vibration_mms": 4.8}, REF, LIM).score
    assert b < a