import os
import random
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException

INGESTION_URL = os.environ.get("INGESTION_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "dev-key")
MACHINES = os.environ.get("MACHINES", "M-01,M-02,M-03").split(",")
INTERVAL = float(os.environ.get("INTERVAL_S", "1.0"))

MODES = {"normal", "idle", "overheat", "vibration_drift", "stopped", "sensor_cut"}
SILENT_MODES = {"stopped", "sensor_cut"}   # on cesse d'émettre (contrat §8.3)

stop_event = threading.Event()


class Machine:
    def __init__(self, machine_id):
        self.id = machine_id
        self.seq = 0
        self.mode = "normal"
        self.ticks = 0          # nombre de mesures depuis le dernier changement de mode

    def set_mode(self, mode):
        self.mode = mode
        self.ticks = 0


machines = {m: Machine(m) for m in MACHINES}


def make_measure(m: Machine):
    m.seq += 1
    m.ticks += 1
    temp = random.gauss(70, 1.5)
    vib = random.gauss(3.5, 0.3)
    power = random.gauss(22, 1)
    rpm = random.gauss(2980, 15)

    if m.mode == "overheat":
        temp += min(m.ticks * 1.5, 45)       # montée progressive : warn puis crit
    elif m.mode == "vibration_drift":
        vib += min(m.ticks * 0.05, 6)        # dérive lente : z-score avant la limite
    elif m.mode == "idle":
        power, rpm = random.gauss(4, 0.3), 0

    return {
        "message_id": str(uuid.uuid4()),     # créé par le simulateur
        "machine_id": m.id,
        "seq": m.seq,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "idle" if m.mode == "idle" else "running",
        "values": {
            "temperature_c": round(temp, 2),
            "vibration_mms": round(max(vib, 0), 2),
            "power_kw": round(max(power, 0), 2),
            "rpm": round(max(rpm, 0)),
        },
    }


def send_with_retry(client, measure):
    """Réessaie la MÊME mesure (même message_id) avec backoff exponentiel."""
    delay = 0.5
    while not stop_event.is_set():
        try:
            r = client.post(
                f"{INGESTION_URL}/measures",
                json=measure,
                headers={"X-API-Key": API_KEY},
                timeout=3,
            )
            if r.status_code < 300:
                print(measure["machine_id"], "seq", measure["seq"], "->", r.status_code)
                return
            if r.status_code < 500:          # 401/422 : inutile de réessayer
                print(measure["machine_id"], "rejeté", r.status_code, r.text)
                return
            print(measure["machine_id"], "seq", measure["seq"], "->", r.status_code, "retry")
        except httpx.TransportError as e:
            print(measure["machine_id"], "erreur réseau:", e, "retry")
        time.sleep(delay)
        delay = min(delay * 2, 10)


def run_machine(m: Machine):
    with httpx.Client() as client:
        while not stop_event.is_set():
            if m.mode not in SILENT_MODES:   # arrêt = plus aucune émission
                send_with_retry(client, make_measure(m))
            time.sleep(INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threads = [threading.Thread(target=run_machine, args=(m,), daemon=True)
               for m in machines.values()]
    for t in threads:
        t.start()
    yield
    stop_event.set()


app = FastAPI(title="machine-simulator", lifespan=lifespan)


@app.get("/machines")
def list_machines():
    return {m.id: {"mode": m.mode, "seq": m.seq} for m in machines.values()}


@app.post("/machines/{machine_id}/mode/{mode}")
def set_mode(machine_id: str, mode: str):
    if machine_id not in machines:
        raise HTTPException(404, "machine inconnue")
    if mode not in MODES:
        raise HTTPException(400, f"mode invalide : {sorted(MODES)}")
    machines[machine_id].set_mode(mode)
    return {"machine_id": machine_id, "mode": mode}


@app.post("/machines/{machine_id}/resume")
def resume(machine_id: str):
    return set_mode(machine_id, "normal")