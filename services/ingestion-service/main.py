import asyncio
import logging
import os
import secrets

import aio_pika
from fastapi import Depends, FastAPI, Header, HTTPException

from models import Measure, MeasureBatch

log = logging.getLogger("ingestion")
app = FastAPI(title="Ingestion Service")

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://admin:admin123@localhost:5672/")
API_KEY = os.environ.get("API_KEY", "dev-key")

connection = None
channel = None
exchange = None
_lock = asyncio.Lock()


async def get_exchange():
    global connection, channel, exchange
    async with _lock:
        if connection is None or connection.is_closed:
            connection = await asyncio.wait_for(
                aio_pika.connect_robust(RABBITMQ_URL), timeout=3
            )
            channel = None
        if channel is None or channel.is_closed:
            channel = await connection.channel(publisher_confirms=True)
            exchange = await channel.declare_exchange(
                "measures.fanout", aio_pika.ExchangeType.FANOUT, durable=True
            )
        return exchange


async def reset_connection():
    global connection, channel, exchange
    try:
        if connection is not None:
            await asyncio.wait_for(connection.close(), 2)
    except Exception:
        pass
    connection = channel = exchange = None


def check_key(x_api_key: str = Header(None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="clé d'API invalide")


async def publish(measures: list[Measure]):
    try:
        ex = await get_exchange()
        for m in measures:
            message = aio_pika.Message(
                body=m.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=str(m.message_id),
            )
            # avec publisher_confirms, publish() attend le confirm du broker
            await asyncio.wait_for(ex.publish(message, routing_key=m.machine_id), 5)
    except Exception as e:
        log.error("publication impossible: %r", e)
        await reset_connection()
        raise HTTPException(status_code=503, detail="RabbitMQ indisponible")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/measures", status_code=202, dependencies=[Depends(check_key)])
async def post_measure(measure: Measure):
    await publish([measure])
    return {"status": "accepted", "message_id": str(measure.message_id)}


@app.post("/measures/batch", status_code=202, dependencies=[Depends(check_key)])
async def post_batch(batch: MeasureBatch):
    await publish(batch.measures)
    return {"status": "accepted", "count": len(batch.measures)}