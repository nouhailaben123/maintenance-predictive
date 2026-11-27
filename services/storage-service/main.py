import json
import os
import time

import pika
import psycopg
from psycopg.types.json import Jsonb

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "admin123")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "admin123")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "maintenance")

QUEUE_MEASURES = "q.storage"
QUEUE_HEALTH = "q.health.store"

MEASURE_SQL = """
INSERT INTO measurements
    (message_id, machine_id, seq, "timestamp", status,
     temperature_c, vibration_mms, power_kw, rpm)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (message_id) DO NOTHING
"""

HEALTH_SQL = """
INSERT INTO health_scores
    (event_id, machine_id, state, health_score, reasons, samples, window_end)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO NOTHING
"""

db = None


def connect_db():
    """Connect to PostgreSQL, retry until it works."""
    while True:
        try:
            conn = psycopg.connect(
                host=POSTGRES_HOST,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
                autocommit=True,
            )
            print("[storage] connected to PostgreSQL", flush=True)
            return conn
        except psycopg.OperationalError as exc:
            print(f"[storage] database not ready: {exc}", flush=True)
            time.sleep(3)


def parse_measure(msg):
    values = msg["values"]
    return (
        msg["message_id"],
        msg["machine_id"],
        msg["seq"],
        msg["timestamp"],
        msg["status"],
        values.get("temperature_c"),
        values.get("vibration_mms"),
        values.get("power_kw"),
        values.get("rpm"),
    )


def parse_health(msg):
    return (
        msg["event_id"],
        msg["machine_id"],
        msg["state"],
        int(msg["health_score"]),
        Jsonb(msg.get("reasons", [])),
        msg.get("samples"),
        msg["window_end"],
    )


def make_handler(name, parse, sql):
    """Build the callback of one queue: parse, insert, then ack."""

    def handler(channel, method, properties, body):
        global db

        # 1. Parse the message. If it is invalid, send it to the dead letter queue.
        try:
            row = parse(json.loads(body))
        except (ValueError, KeyError, TypeError, AttributeError):
            print(f"[storage] {name}: invalid message -> dead letter queue", flush=True)
            channel.basic_nack(method.delivery_tag, requeue=False)
            return

        # 2. Insert into the database.
        try:
            db.execute(sql, row)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            # Database down: do NOT ack, the message goes back to the queue.
            print(f"[storage] {name}: database down, message kept in queue", flush=True)
            channel.basic_nack(method.delivery_tag, requeue=True)
            time.sleep(3)
            db = connect_db()
            return
        except psycopg.Error as exc:
            # Data the database refuses (bad value): send to the dead letter queue.
            print(f"[storage] {name}: bad data -> dead letter queue: {exc}", flush=True)
            channel.basic_nack(method.delivery_tag, requeue=False)
            return

        # 3. Everything worked: confirm to RabbitMQ.
        channel.basic_ack(method.delivery_tag)

    return handler


def main():
    global db
    db = connect_db()

    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD),
                    heartbeat=60,
                )
            )
            channel = connection.channel()
            channel.basic_qos(prefetch_count=50)
            channel.basic_consume(
                queue=QUEUE_MEASURES,
                on_message_callback=make_handler("measures", parse_measure, MEASURE_SQL),
            )
            channel.basic_consume(
                queue=QUEUE_HEALTH,
                on_message_callback=make_handler("health", parse_health, HEALTH_SQL),
            )
            print(f"[storage] waiting for messages on {QUEUE_MEASURES} and {QUEUE_HEALTH}", flush=True)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as exc:
            print(f"[storage] RabbitMQ not reachable: {exc}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
