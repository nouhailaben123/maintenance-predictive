"""Publie des mesures factices dans measures.fanout (test sans ingestion).
Exemples :
  python tools/fake_measures.py --mode normal --count 120
  python tools/fake_measures.py --mode overheat
  python tools/fake_measures.py --mode drift --metric vibration_mms
  python tools/fake_measures.py --mode normal --stop-after 60      # puis silence -> SILENT
"""
import argparse, json, os, random, time, uuid
from datetime import datetime, timezone
import pika

BASE = {"temperature_c": 70.0, "vibration_mms": 3.8, "power_kw": 22.0, "rpm": 2980.0}
NOISE = {"temperature_c": 0.5, "vibration_mms": 0.15, "power_kw": 0.4, "rpm": 8.0}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["normal", "overheat", "drift"], default="normal")
    ap.add_argument("--machine", default="M-01")
    ap.add_argument("--metric", default="vibration_mms")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=60, help="mesures normales avant la panne")
    ap.add_argument("--stop-after", type=int, default=0, help="arrête d'émettre après N mesures")
    ap.add_argument("--drift-step", type=float, default=0.05)
    a = ap.parse_args()

    creds = pika.PlainCredentials(os.getenv("RABBITMQ_USER", "guest"), os.getenv("RABBITMQ_PASSWORD", "guest"))
    conn = pika.BlockingConnection(pika.ConnectionParameters(os.getenv("RABBITMQ_HOST", "localhost"), 5672, credentials=creds))
    ch = conn.channel()
    ch.confirm_delivery()
    random.seed(42)
    for seq in range(1, a.count + 1):
        if a.stop_after and seq > a.stop_after:
            break
        vals = {k: random.gauss(v, NOISE[k]) for k, v in BASE.items()}
        if a.mode == "overheat" and seq > a.warmup:
            vals["temperature_c"] += 1.5 * (seq - a.warmup)       # monte vite
        if a.mode == "drift" and seq > a.warmup:
            vals[a.metric] += a.drift_step * (seq - a.warmup) * (1 if a.metric != "rpm" else 10)
        msg = {"message_id": str(uuid.uuid4()), "machine_id": a.machine, "seq": seq,
               "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
               "status": "running", "values": {k: round(v, 2) for k, v in vals.items()}}
        ch.basic_publish("measures.fanout", "", json.dumps(msg).encode(),
                         pika.BasicProperties(content_type="application/json", delivery_mode=2,
                                              message_id=msg["message_id"]), mandatory=True)
        time.sleep(a.interval)
    conn.close()

if __name__ == "__main__":
    main()