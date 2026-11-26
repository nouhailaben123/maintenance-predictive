"""Étape 9 : les 5 scénarios de panne du monitoring.

Preuves relevées SANS dépendre du stockage ni de l'alert-service : le script se branche lui-même sur
RabbitMQ avec deux files d'espionnage (copie de measures.fanout et de health.fanout), sans voler de
messages aux vrais services.

Usage (depuis la racine du dépôt, venv du monitoring activé, variables chargées par dev_env.ps1) :
    python scripts/scenarios/run_scenarios.py 1 2 3 --runs 1
    python scripts/scenarios/run_scenarios.py --runs 3          # tous les scénarios, 3 essais chacun

Scénarios : 1 surchauffe, 2 dérive de vibration, 3 machine silencieuse,
            4a arrêt du stockage, 4b arrêt du monitoring, 5 RabbitMQ coupé + message invalide.
Résultats : docs/tests/scenarios_results.md
"""
import argparse
import base64
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pika

try:
    import psycopg
except ImportError:          # la base n'est utilisée que pour des preuves optionnelles
    psycopg = None

# ---------------------------------------------------------------- configuration
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "admin")
RABBIT_PASS = os.getenv("RABBITMQ_PASSWORD", "admin123")
AUTH = (RABBIT_USER, RABBIT_PASS)
MGMT = os.getenv("RABBITMQ_MGMT_URL", "http://localhost:15672")
SIM = os.getenv("SIMULATOR_URL", "http://localhost:8001")
INGESTION = os.getenv("INGESTION_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key")
MACHINE = os.getenv("TEST_MACHINE", "M-01")
PG_DSN = (f"host={os.getenv('POSTGRES_HOST', 'localhost')} port=5432 "
          f"dbname={os.getenv('POSTGRES_DB', 'maintenance')} "
          f"user={os.getenv('POSTGRES_USER', 'admin')} password={os.getenv('POSTGRES_PASSWORD', 'admin123')}")
VIB_WARN_LIMIT = 6.0     # seuils du type "default" (db/init.sql)
VIB_CRIT_LIMIT = 8.0


@dataclass
class Result:
    name: str
    ok: bool = False
    skipped: bool = False
    data: dict = field(default_factory=dict)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- HTTP / Docker / PostgreSQL
def http(method, url, body=None, headers=None, auth=None, timeout=10):
    """Retourne (code HTTP, JSON ou None). Lève OSError si le serveur est injoignable."""
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def queue_info(name):
    try:
        code, js = http("GET", f"{MGMT}/api/queues/%2F/{name}", auth=AUTH, timeout=5)
        return js if code == 200 else None
    except OSError:
        return None


def depth(name):
    qi = queue_info(name)
    return None if qi is None else qi.get("messages", 0)


def compose(*args):
    subprocess.run(["docker", "compose", *args], check=True)


def compose_out(*args):
    p = subprocess.run(["docker", "compose", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    return p.stdout + p.stderr


def compose_services():
    return set(compose_out("config", "--services").split())


def monitoring_metric(name):
    """Lit une métrique Prometheus du monitoring (port 9102, à l'intérieur du conteneur)."""
    code = "import urllib.request;print(urllib.request.urlopen('http://localhost:9102/metrics',timeout=3).read().decode())"
    try:
        out = subprocess.run(["docker", "compose", "exec", "-T", "monitoring-service", "python", "-c", code],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"^" + re.escape(name) + r"(?:\{[^}]*\})?\s+([0-9.eE+-]+)\s*$", out, re.M)
    return float(m.group(1)) if m else None


def pg(sql, *params):
    """Requête PostgreSQL optionnelle : None si la base est injoignable."""
    if psycopg is None:
        return None
    try:
        with psycopg.connect(PG_DSN, connect_timeout=3) as c:
            return c.execute(sql, params).fetchall()
    except Exception:
        return None


def db_now():
    rows = pg("SELECT now()")
    return rows[0][0] if rows else None


def db_alert_count(machine, since):
    if since is None:
        return None
    rows = pg("SELECT count(*) FROM alerts WHERE machine_id=%s AND created_at>%s", machine, since)
    return rows[0][0] if rows else None


def db_last_seq():
    rows = pg("SELECT machine_id, max(seq) FROM measurements GROUP BY machine_id")
    return dict(rows) if rows else None


def db_integrity(since):
    """Perte / doublons dans measurements depuis le relevé `since` (None si pas de données)."""
    if not since:
        return None
    missing = dup = 0
    for mid, lo in since.items():
        rows = pg("SELECT count(*), count(DISTINCT seq), min(seq), max(seq) FROM measurements "
                  "WHERE machine_id=%s AND seq>%s", mid, lo)
        if rows is None:
            return None
        n, d, mn, mx = rows[0]
        if n:
            missing += (mx - mn + 1) - d
            dup += n - d
    return {"db_manquants": missing, "db_doublons": dup}


# ---------------------------------------------------------------- simulateur
def sim_mode(machine, mode):
    if mode == "normal":
        code, _ = http("POST", f"{SIM}/machines/{machine}/resume", timeout=5)
    else:
        code, _ = http("POST", f"{SIM}/machines/{machine}/mode/{mode}", timeout=5)
    if code >= 300:
        raise RuntimeError(f"simulateur : mode {mode} refusé ({code})")


# ---------------------------------------------------------------- espions RabbitMQ
class Spy:
    """Deux files durables (copie de measures.fanout et health.fanout), consultées par basic_get.
    Durables, pour survivre à l'arrêt de RabbitMQ (scénario 5) ; x-expires les supprime si le script plante."""

    def __init__(self):
        base = "q.test.spy." + uuid.uuid4().hex[:8]
        self.qm, self.qh = base + ".m", base + ".h"
        self.conn = self.ch = None
        self.connected_at = None  # dernière (re)connexion réussie à RabbitMQ
        self.measures = []       # {machine_id, seq, message_id, vib, t}
        self.events = []         # {machine_id, state, reasons, score, t}
        self.invalid = 0

    def connect(self):
        try:
            cred = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
            self.conn = pika.BlockingConnection(pika.ConnectionParameters(
                RABBIT_HOST, credentials=cred, heartbeat=30, socket_timeout=5))
            self.ch = self.conn.channel()
            for q, ex in ((self.qm, "measures.fanout"), (self.qh, "health.fanout")):
                self.ch.queue_declare(q, durable=True, arguments={"x-expires": 1_800_000})
                self.ch.queue_bind(q, ex)
            self.connected_at = time.time()
        except Exception:
            self.conn = self.ch = None
            raise

    def drain(self):
        """Lit tout ce qui attend. Retourne False si RabbitMQ est injoignable (se reconnecte au tour suivant)."""
        try:
            if self.ch is None or self.conn is None or self.conn.is_closed:
                self.connect()
            for q, handler in ((self.qm, self._on_measure), (self.qh, self._on_event)):
                while True:
                    method, _props, body = self.ch.basic_get(q, auto_ack=True)
                    if method is None:
                        break
                    handler(body)
            return True
        except (pika.exceptions.AMQPError, OSError):
            self.conn = self.ch = None
            return False

    def _on_measure(self, body):
        try:
            d = json.loads(body)
            self.measures.append({"machine_id": d["machine_id"], "seq": int(d["seq"]),
                                  "message_id": d["message_id"],
                                  "vib": float(d["values"]["vibration_mms"]), "t": time.time()})
        except (ValueError, KeyError, TypeError):
            self.invalid += 1

    def _on_event(self, body):
        try:
            d = json.loads(body)
            self.events.append({"machine_id": d["machine_id"], "state": d["state"],
                                "reasons": d.get("reasons", []), "score": d.get("health_score"),
                                "t": time.time()})
        except (ValueError, KeyError, TypeError):
            pass

    def close(self):
        try:
            if self.ch is not None and self.conn is not None and not self.conn.is_closed:
                self.ch.queue_delete(self.qm)
                self.ch.queue_delete(self.qh)
                self.conn.close()
        except Exception:
            pass


spy = Spy()


def wait_until(cond, timeout=120, step=0.5):
    """Retourne le temps écoulé (s) quand cond() devient vrai, sinon None."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        spy.drain()
        if cond():
            return time.time() - t0
        time.sleep(step)
    return None


def first_event(machine, states, after):
    if isinstance(states, str):
        states = (states,)
    for e in spy.events:
        if e["machine_id"] == machine and e["state"] in states and e["t"] >= after:
            return e
    return None


def state_sequence(machine, after):
    seq = []
    for e in spy.events:
        if e["machine_id"] == machine and e["t"] >= after and (not seq or seq[-1] != e["state"]):
            seq.append(e["state"])
    return seq


def ensure_ok(machine=MACHINE, timeout=240):
    """Remet la machine en marche normale et attend un événement OK publié APRÈS la reprise."""
    sim_mode(machine, "normal")
    t0 = time.time()
    return wait_until(lambda: first_event(machine, "OK", t0) is not None, timeout)


def analyze(msgs):
    """Perte / doublons de seq par machine sur une liste de mesures vues sur measures.fanout."""
    by = {}
    for m in msgs:
        by.setdefault(m["machine_id"], []).append(m["seq"])
    missing = dup = 0
    for seqs in by.values():
        u = set(seqs)
        dup += len(seqs) - len(u)
        missing += (max(u) - min(u) + 1) - len(u)
    return {"manquants": missing, "doublons": dup, "mesures_vues": len(msgs)}


def r1(x):
    return None if x is None else round(x, 1)


# ---------------------------------------------------------------- scénarios
def s1_overheat():
    r = Result("1. Surchauffe")
    if ensure_ok() is None:
        r.data["erreur"] = "machine pas à OK au départ"
        return r
    ts_db = db_now()
    t0 = time.time()
    sim_mode(MACHINE, "overheat")
    wait_until(lambda: first_event(MACHINE, "CRIT", t0) is not None, 180)
    warn, crit = first_event(MACHINE, "WARN", t0), first_event(MACHINE, "CRIT", t0)
    r.data["delai_warn_s"] = r1(warn["t"] - t0) if warn else None
    r.data["delai_crit_s"] = r1(crit["t"] - t0) if crit else None
    r.data["raisons_crit"] = crit["reasons"] if crit else None
    r.data["etats"] = "->".join(state_sequence(MACHINE, t0))
    r.data["alertes_en_base"] = db_alert_count(MACHINE, ts_db)    # None/0 tant que l'alert-service n'existe pas
    r.data["retour_ok_s"] = r1(ensure_ok())
    r.ok = bool(warn and crit and warn["t"] <= crit["t"])
    return r


def s2_drift():
    r = Result("2. Dérive de vibration")
    if ensure_ok() is None:
        r.data["erreur"] = "machine pas à OK au départ"
        return r
    # La fenêtre glissante (60 mesures, soit ~60 s) garde la mémoire du test précédent : sans ce délai, les
    # valeurs hautes de l'essai d'avant gonflent l'écart-type et le z-score devient insensible.
    log("attente de 70 s : la fenêtre doit se remplir de mesures normales ...")
    time.sleep(70)
    t0 = time.time()
    sim_mode(MACHINE, "vibration_drift")

    def limit_time(limit):
        for m in spy.measures:
            if m["machine_id"] == MACHINE and m["t"] >= t0 and m["vib"] >= limit:
                return m["t"]
        return None

    wait_until(lambda: first_event(MACHINE, ("WARN", "CRIT"), t0) is not None, 150)
    wait_until(lambda: limit_time(VIB_WARN_LIMIT) is not None, 120)
    ev = first_event(MACHINE, ("WARN", "CRIT"), t0)
    lw = limit_time(VIB_WARN_LIMIT)
    r.data["premier_etat"] = ev["state"] if ev else None
    r.data["raisons"] = ev["reasons"] if ev else None
    r.data["delai_detection_s"] = r1(ev["t"] - t0) if ev else None
    r.data["limite_warn_franchie_apres_s"] = r1(lw - t0) if lw else None
    r.data["avance_sur_limite_warn_s"] = r1(lw - ev["t"]) if (ev and lw) else None
    wait_until(lambda: limit_time(VIB_CRIT_LIMIT) is not None, 150)
    lc = limit_time(VIB_CRIT_LIMIT)
    r.data["limite_crit_franchie_apres_s"] = r1(lc - t0) if lc else None
    r.data["avance_sur_limite_crit_s"] = r1(lc - ev["t"]) if (ev and lc) else None
    r.data["retour_ok_s"] = r1(ensure_ok())
    r.ok = bool(ev and ev["state"] == "WARN" and lw and ev["t"] < lw)
    return r


def s3_silent():
    r = Result("3. Machine silencieuse")
    if ensure_ok() is None:
        r.data["erreur"] = "machine pas à OK au départ"
        return r
    ts_db = db_now()
    t0 = time.time()
    sim_mode(MACHINE, "stopped")
    wait_until(lambda: first_event(MACHINE, "SILENT", t0) is not None, 120)
    ev = first_event(MACHINE, "SILENT", t0)
    r.data["delai_silent_s"] = r1(ev["t"] - t0) if ev else None
    r.data["raisons"] = ev["reasons"] if ev else None
    r.data["score"] = ev["score"] if ev else None
    t1 = time.time()
    sim_mode(MACHINE, "normal")
    wait_until(lambda: first_event(MACHINE, "OK", t1) is not None, 120)
    ok_ev = first_event(MACHINE, "OK", t1)
    r.data["delai_reprise_s"] = r1(ok_ev["t"] - t1) if ok_ev else None
    r.data["alertes_en_base"] = db_alert_count(MACHINE, ts_db)
    r.ok = bool(ev and ev["score"] == 0 and ok_ev)
    return r


def s4_service_down(service, queue, duration=30):
    r = Result(f"4. Arrêt de {service}")
    if service not in compose_services():
        r.skipped = True
        r.data["note"] = f"service '{service}' absent du docker-compose (pas encore livré)"
        return r
    ensure_ok()
    spy.drain()
    mark, ev_mark = len(spy.measures), len(spy.events)
    db_before = db_last_seq()
    try:
        t_stop = time.time()
        log(f"arrêt de {service} pendant {duration} s ...")
        compose("stop", service)
        time.sleep(duration + 6)                 # +6 s : les statistiques de RabbitMQ se rafraîchissent toutes les 5 s
        spy.drain()
        r.data["file_pendant_arret"] = depth(queue)
        r.data["publiees_pendant_arret"] = sum(1 for m in spy.measures if m["t"] >= t_stop)
        compose("start", service)
        t_start = time.time()
        caught = wait_until(lambda: depth(queue) is not None and depth(queue) <= 5, 300)
        r.data["rattrapage_s"] = r1(caught)       # résolution ~5 s (rafraîchissement des statistiques)
        time.sleep(8)
        spy.drain()
    finally:
        compose("start", service)                 # ne laisse jamais le service arrêté
    r.data.update(analyze(spy.measures[mark:]))   # perte / doublons de seq à la source (vus sur measures.fanout)
    # Faux SILENT ou oscillation après le redémarrage ?
    after = [e for e in spy.events[ev_mark:] if e["t"] >= t_start]
    r.data["faux_silent_apres_redemarrage"] = sum(1 for e in after if e["state"] == "SILENT")
    changes = 0
    for mid in {e["machine_id"] for e in after}:
        seq = state_sequence(mid, t_start)
        changes += max(0, len(seq) - 1)
    r.data["changements_etat_apres_redemarrage"] = changes
    ok = caught is not None and r.data["manquants"] == 0 and r.data["faux_silent_apres_redemarrage"] == 0
    if service == "monitoring-service":
        r.data["seq_trous_vus_par_monitoring"] = monitoring_metric("monitoring_seq_gaps_total")
        r.data["doublons_ignores_par_monitoring"] = monitoring_metric("monitoring_measures_duplicates_total")
        logs = compose_out("logs", "--tail", "300", service)
        r.data["log_fenetres_reconstruites"] = "Fenêtres reconstruites" in logs
        ok = ok and r.data["seq_trous_vus_par_monitoring"] in (0, 0.0)
    else:
        integ = db_integrity(db_before)
        r.data["base"] = integ if integ is not None else "non vérifiable (base vide ou injoignable)"
        ok = ok and integ is not None and integ["db_manquants"] == 0 and integ["db_doublons"] == 0
    r.ok = ok
    return r


def s5_rabbit_and_invalid():
    r = Result("5. RabbitMQ coupé + message invalide")
    ensure_ok()
    spy.drain()
    mark = len(spy.measures)
    valid = {"message_id": str(uuid.uuid4()), "machine_id": "M-TEST", "seq": 1,
             "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "status": "running",
             "values": {"temperature_c": 70.0, "vibration_mms": 3.5, "power_kw": 22.0, "rpm": 2980}}
    try:
        t_stop = time.time()
        log("arrêt de RabbitMQ pendant 25 s ...")
        compose("stop", "rabbitmq")
        time.sleep(25)
        try:
            code, _ = http("POST", INGESTION + "/measures", body=valid, headers={"X-API-Key": API_KEY}, timeout=20)
        except OSError as exc:
            code = f"injoignable ({exc})"
        r.data["ingestion_pendant_coupure"] = code        # attendu : 503
        # Les print() du simulateur restent en mémoire tampon dans Docker (pas de PYTHONUNBUFFERED) : on compte
        # donc les refus côté ingestion (logging, non bufferisé), qui correspondent aux tentatives du simulateur.
        logs = compose_out("logs", "--since", "40s", "ingestion-service")
        r.data["refus_503_vus_par_ingestion"] = len(re.findall(r"publication impossible", logs))
        logs = compose_out("logs", "--since", "40s", "machine-simulator")
        r.data["retries_vus_dans_logs_simulateur"] = len(re.findall(r"retry", logs))
        compose("start", "rabbitmq")
        t_start = time.time()
        # Instant où RabbitMQ accepte à nouveau les connexions AMQP (l'espion se reconnecte dès que possible)
        wait_until(lambda: spy.connected_at is not None and spy.connected_at >= t_start, 180)
        if spy.connected_at is not None and spy.connected_at >= t_start:
            r.data["rabbitmq_pret_s"] = r1(spy.connected_at - t_start)
        up = wait_until(lambda: (queue_info("q.monitoring") or {}).get("consumers", 0) >= 1, 180)
        # depuis le démarrage de RabbitMQ (précision ~5 s : rafraîchissement des statistiques)
        r.data["monitoring_reconnecte_s"] = r1(time.time() - t_start) if up is not None else None
        # 1re mesure revue par l'espion après le redémarrage (on ATTEND : si aucun message n'était en file,
        # il faut que l'ingestion se reconnecte à RabbitMQ et que le simulateur renvoie une mesure)
        wait_until(lambda: any(m["t"] >= t_start for m in spy.measures), 120)
        after = [m["t"] for m in spy.measures if m["t"] >= t_start]
        flux = (min(after) - t_start) if after else None
        r.data["flux_repris_apres_s"] = r1(flux)
    finally:
        compose("start", "rabbitmq")
    # Message invalide : doit finir en q.dead sans bloquer la file
    dead0 = depth("q.dead") or 0
    http("POST", f"{MGMT}/api/exchanges/%2F/measures.fanout/publish", auth=AUTH, timeout=10,
         body={"properties": {"delivery_mode": 2}, "routing_key": "",
               "payload": "{ceci n'est pas du json", "payload_encoding": "string"})
    dlq = wait_until(lambda: (depth("q.dead") or 0) > dead0, 40)
    r.data["dlq_apres_s"] = r1(dlq)
    time.sleep(8)
    spy.drain()
    r.data.update(analyze(spy.measures[mark:]))
    r.ok = (r.data["ingestion_pendant_coupure"] == 503 and dlq is not None and flux is not None
            and r.data["manquants"] == 0)
    return r


SCENARIOS = {
    "1": s1_overheat, "2": s2_drift, "3": s3_silent,
    "4a": lambda: s4_service_down("storage-service", "q.storage"),
    "4b": lambda: s4_service_down("monitoring-service", "q.monitoring"),
    "5": s5_rabbit_and_invalid,
}


# ---------------------------------------------------------------- rapport
def summarize(results):
    """Moyenne / min / max des champs numériques d'un même scénario sur plusieurs essais."""
    keys = {k for r in results for k, v in r.data.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}
    out = {}
    for k in sorted(keys):
        vals = [r.data[k] for r in results if isinstance(r.data.get(k), (int, float))]
        if len(vals) > 1:
            out[k] = f"moy {statistics.mean(vals):.1f} (min {min(vals):.1f}, max {max(vals):.1f})"
    return out


def write_report(all_results, runs):
    os.makedirs("docs/tests", exist_ok=True)
    with open("docs/tests/scenarios_results.md", "w", encoding="utf-8") as f:
        f.write(f"# Résultats des scénarios de panne\n\nDate : {datetime.now():%Y-%m-%d %H:%M} — "
                f"{runs} essai(s) par scénario — machine de test : {MACHINE}\n\n")
        f.write("| Scénario | Essai | Résultat | Mesures |\n|---|---|---|---|\n")
        for key, results in all_results.items():
            for i, r in enumerate(results, 1):
                status = "⏭ ignoré" if r.skipped else ("✅" if r.ok else "❌")
                data = {k: v for k, v in r.data.items() if not k.startswith("_")}
                f.write(f"| {r.name} | {i} | {status} | {data} |\n")
        f.write("\n## Moyennes sur les essais\n\n")
        for key, results in all_results.items():
            s = summarize([r for r in results if not r.skipped])
            if s:
                f.write(f"- **{results[0].name}** : " + ", ".join(f"{k} = {v}" for k, v in s.items()) + "\n")


# ---------------------------------------------------------------- exécution
def preflight():
    if not spy.drain():
        sys.exit("RabbitMQ injoignable : vérifiez 'docker compose ps -a' et que dev_env.ps1 a été chargé.")
    try:
        code, _ = http("GET", f"{SIM}/machines", timeout=5)
    except OSError:
        code = None
    if code != 200:
        sys.exit(f"Simulateur injoignable sur {SIM} (docker compose up -d).")
    log("attente d'un événement de santé du monitoring ...")
    if wait_until(lambda: len(spy.events) > 0, 20) is None:
        sys.exit("Aucun événement de santé reçu : le monitoring-service tourne-t-il ?")
    log("pré-vérifications OK")


def main():
    global MACHINE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="1 2 3 4a 4b 5 (défaut : tous)")
    ap.add_argument("--runs", type=int, default=1, help="nombre d'essais par scénario (3 pour le rapport)")
    ap.add_argument("--machine", default=MACHINE)
    args = ap.parse_args()
    MACHINE = args.machine
    wanted = args.scenarios or list(SCENARIOS)
    unknown = [k for k in wanted if k not in SCENARIOS]
    if unknown:
        sys.exit(f"scénario(s) inconnu(s) : {unknown}")
    all_results = {}
    try:
        preflight()
        for key in wanted:
            all_results[key] = []
            for run in range(1, args.runs + 1):
                log(f"=== scénario {key} — essai {run}/{args.runs}")
                try:
                    res = SCENARIOS[key]()
                except Exception as exc:     # un scénario qui plante ne doit pas arrêter les autres
                    res = Result(f"scénario {key}", data={"erreur": repr(exc)})
                all_results[key].append(res)
                shown = {k: v for k, v in res.data.items() if not k.startswith("_")}
                print(("IGNORÉ" if res.skipped else "OK    " if res.ok else "ÉCHEC "), res.name, shown, flush=True)
    finally:
        try:
            sim_mode(MACHINE, "normal")
        except Exception:
            pass
        spy.close()
        if all_results:
            write_report(all_results, args.runs)
            log("rapport écrit : docs/tests/scenarios_results.md")


if __name__ == "__main__":
    main()
