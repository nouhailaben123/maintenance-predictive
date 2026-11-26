import logging
import time

import pika
from pika.exceptions import AMQPError, NackError, UnroutableError

from . import config as cfg, metrics
from .db import refresh_reference
from .engine import Engine
from .models import MeasureMsg
from .window import Sample

log = logging.getLogger("runner")

def _connect():
    delay = 1
    while True:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(
                host=cfg.RABBITMQ_HOST, port=cfg.RABBITMQ_PORT, heartbeat=30,
                credentials=pika.PlainCredentials(cfg.RABBITMQ_USER, cfg.RABBITMQ_PASSWORD)))
        except (AMQPError, OSError) as exc:    # OSError : nom d'hôte introuvable (DNS), connexion refusée...
            log.warning("RabbitMQ indisponible (%s), nouvel essai dans %ss", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 5)           # backoff exponentiel plafonné à 5 s

def _flush(engine: Engine, ch):
    """Publie les événements en attente. Une erreur de connexion remonte (-> reconnexion)."""
    while engine.pending:
        ev = engine.pending[0]
        try:
            ch.basic_publish(cfg.HEALTH_EXCHANGE, "", __import__("json").dumps(ev).encode(),
                             pika.BasicProperties(content_type="application/json", delivery_mode=2,
                                                  message_id=ev["event_id"]), mandatory=True)
        except (UnroutableError, NackError) as exc:
            log.warning("Publication refusée par le broker (%s) : on réessaiera", exc)
            return
        engine.pending.popleft()
        metrics.EVENTS.labels(ev["state"]).inc()
    metrics.PENDING.set(0)

def _handle(engine: Engine, ch, method, body: bytes):
    # 1) ERREUR DÉFINITIVE : message illisible -> DLQ, sans remise en file
    try:
        msg = MeasureMsg.model_validate_json(body)
    except ValueError as exc:
        log.error("Message invalide -> DLQ : %s", str(exc)[:200])
        metrics.REJECTED.inc()
        ch.basic_nack(method.delivery_tag, requeue=False)
        return
    # 2) Traitement (en mémoire). Une exception inattendue (bug) sur CE message ne doit pas
    #    faire planter le service en boucle (message redélivré, re-plantage...) : DLQ.
    try:
        with metrics.PROCESS_SECONDS.time():
            engine.process(Sample(msg.message_id, msg.machine_id, msg.seq, msg.timestamp,
                                  msg.status, msg.values.model_dump()))
    except Exception:
        log.exception("Erreur inattendue sur %s -> DLQ", msg.message_id)
        metrics.REJECTED.inc()
        ch.basic_nack(method.delivery_tag, requeue=False)
        return
    # 3) Publication confirmée AVANT l'ack de la mesure
    _flush(engine, ch)
    ch.basic_ack(method.delivery_tag)

def run(engine: Engine):
    last_tick = last_refresh = 0.0
    while True:
        try:
            conn = _connect()
            ch = conn.channel()
            ch.confirm_delivery()                       # publisher confirms
            ch.basic_qos(prefetch_count=cfg.PREFETCH)
            log.info("En écoute sur %s", cfg.QUEUE)
            for method, _props, body in ch.consume(cfg.QUEUE, inactivity_timeout=1.0):
                now = time.monotonic()
                if method is not None:
                    _handle(engine, ch, method, body)
                if now - last_tick >= 1.0:             # horloge indépendante des messages
                    engine.tick(now)
                    _flush(engine, ch)
                    last_tick = now
                if now - last_refresh >= cfg.THRESHOLD_REFRESH_SEC:
                    refresh_reference(engine)
                    last_refresh = now
        except (AMQPError, OSError) as exc:             # ERREUR TRANSITOIRE : broker coupé, réseau
            log.warning("Connexion RabbitMQ perdue (%s) : reconnexion", exc)
            time.sleep(2)