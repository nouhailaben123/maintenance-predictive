import logging
import os
import re
import time
from typing import Literal
from uuid import UUID

import pika
import psycopg2
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("alert-service")

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://admin:admin123@localhost:5672/")
QUEUE = "q.alerts"
COOLDOWN_SEC = int(os.environ.get("COOLDOWN_SEC", "10"))
PG = dict(
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    user=os.environ.get("POSTGRES_USER", "admin"),
    password=os.environ.get("POSTGRES_PASSWORD", "admin123"),
    dbname=os.environ.get("POSTGRES_DB", "maintenance"),
    connect_timeout=5,
)
SEVERITY = {"WARN": "warning", "CRIT": "critical", "SILENT": "critical"}

# Provisoire : la table officielle viendra de init.sql (étudiant 2).
SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id            BIGSERIAL PRIMARY KEY,
    machine_id    TEXT NOT NULL,
    type          TEXT NOT NULL,
    severity      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved')),
    last_event_id UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_alerts_one_active
    ON alerts (machine_id, type) WHERE status = 'active';
"""


class HealthEvent(BaseModel):
    event_id: UUID
    machine_id: str = Field(min_length=1)
    window_end: AwareDatetime
    health_score: int = Field(ge=0, le=100)
    state: Literal["OK", "WARN", "CRIT", "SILENT"]
    reasons: list[str] = []
    samples: int = Field(ge=0)


_conn = None
last_state: dict[str, str] = {}   # dernier état vu par machine (anti-répétition)


def db():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(**PG)
        with _conn, _conn.cursor() as cur:
            cur.execute(SCHEMA)
    return _conn


def reset_db():
    global _conn
    try:
        if _conn is not None:
            _conn.close()
    except Exception:
        pass
    _conn = None


def alert_type(reasons: list[str]) -> str:
    """Type déduit du préfixe de reasons[0] (contrat §8.5)."""
    if not reasons:
        return "unknown"
    r = reasons[0]
    return "no_data" if r.startswith("no_data") else re.split(r"[_>]", r)[0]


def notify(kind: str, machine_id: str, atype: str, severity: str):
    """Notification simulée (email/SMS) : un simple log."""
    log.warning("NOTIFICATION [%s] machine=%s type=%s severity=%s", kind, machine_id, atype, severity)


def resolve(cur, machine_id: str, only_type: str | None = None):
    sql = ("UPDATE alerts SET status='resolved', resolved_at=now() "
           "WHERE machine_id=%s AND status='active'")
    params = [machine_id]
    if only_type:
        sql += " AND type=%s"
        params.append(only_type)
    cur.execute(sql + " RETURNING type, severity", params)
    for atype, sev in cur.fetchall():
        notify("RESOLUE", machine_id, atype, sev)


def open_or_escalate(cur, ev: HealthEvent):
    atype, sev = alert_type(ev.reasons), SEVERITY[ev.state]
    cur.execute("SELECT id, severity FROM alerts "
                "WHERE machine_id=%s AND type=%s AND status='active'", (ev.machine_id, atype))
    row = cur.fetchone()
    if row:                                    # alerte déjà active : escalade ou désescalade
        if row[1] != sev:
            cur.execute("UPDATE alerts SET severity=%s, last_event_id=%s WHERE id=%s",
                        (sev, str(ev.event_id), row[0]))
            notify("CHANGEMENT", ev.machine_id, atype, sev)
        return
    cur.execute("SELECT 1 FROM alerts WHERE machine_id=%s AND type=%s AND status='resolved' "
                "AND resolved_at > now() - %s * interval '1 second'",
                (ev.machine_id, atype, COOLDOWN_SEC))
    if cur.fetchone():                         # cooldown anti-oscillation
        log.info("cooldown: %s/%s ignorée", ev.machine_id, atype)
        return
    cur.execute("INSERT INTO alerts (machine_id, type, severity, last_event_id) "
                "VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (machine_id, type) WHERE status='active' DO NOTHING",
                (ev.machine_id, atype, sev, str(ev.event_id)))
    if cur.rowcount:
        notify("NOUVELLE", ev.machine_id, atype, sev)


def process(ev: HealthEvent):
    if last_state.get(ev.machine_id) == ev.state:
        return                                 # battement répété : on ignore (contrat §9.1)
    with db() as conn, conn.cursor() as cur:
        if ev.state == "OK":
            resolve(cur, ev.machine_id)
        else:
            if ev.state != "SILENT":           # la machine a repris : fin de l'alerte no_data
                resolve(cur, ev.machine_id, "no_data")
            open_or_escalate(cur, ev)
    last_state[ev.machine_id] = ev.state       # mémorisé seulement après le commit


def on_message(ch, method, props, body):
    try:
        ev = HealthEvent.model_validate_json(body)
    except ValidationError as e:               # erreur définitive : nack sans remise -> q.dead
        log.error("événement invalide -> q.dead: %s", e.errors()[0]["msg"])
        ch.basic_nack(method.delivery_tag, requeue=False)
        return
    try:
        process(ev)
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        log.error("base indisponible, message remis en file: %s", e)   # erreur transitoire
        reset_db()
        time.sleep(2)
        ch.basic_nack(method.delivery_tag, requeue=True)
        return
    except Exception:
        log.exception("échec définitif -> q.dead")
        ch.basic_nack(method.delivery_tag, requeue=False)
        return
    ch.basic_ack(method.delivery_tag)          # ack seulement après traitement réussi


def main():
    while True:                                # reconnexion automatique
        try:
            conn = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            ch = conn.channel()
            ch.basic_qos(prefetch_count=10)
            ch.basic_consume(queue=QUEUE, on_message_callback=on_message)
            log.info("alert-service en écoute sur %s", QUEUE)
            ch.start_consuming()
        except pika.exceptions.AMQPError as e:
            log.error("RabbitMQ indisponible (%r), nouvelle tentative dans 3 s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()