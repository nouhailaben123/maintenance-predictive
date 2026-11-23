import os
import random
import time
import uuid
from datetime import datetime, timezone

import httpx

INGESTION_URL = os.environ.get("INGESTION_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "dev-key")
MACHINES = ["M-01", "M-02", "M-03"]
INTERVAL = 1.0  # secondes entre deux envois

# Un compteur seq par machine
seq_counters = {m: 0 for m in MACHINES}


def make_measure(machine_id):
    seq_counters[machine_id] += 1
    return {
        "message_id": str(uuid.uuid4()),   # créé par le simulateur
        "machine_id": machine_id,
        "seq": seq_counters[machine_id],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "running",
        "values": {
            "temperature_c": round(random.gauss(70, 1.5), 2),
            "vibration_mms": round(random.gauss(3.5, 0.3), 2),
            "power_kw": round(random.gauss(22, 1), 2),
            "rpm": round(random.gauss(2980, 15)),
        },
    }


def send(client, measure):
    r = client.post(
        f"{INGESTION_URL}/measures",
        json=measure,
        headers={"X-API-Key": API_KEY},
        timeout=3,
    )
    return r.status_code


def main():
    with httpx.Client() as client:
        while True:
            for machine_id in MACHINES:
                measure = make_measure(machine_id)
                try:
                    code = send(client, measure)
                    print(machine_id, "seq", measure["seq"], "->", code)
                except httpx.TransportError as e:
                    print(machine_id, "erreur réseau:", e)
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()