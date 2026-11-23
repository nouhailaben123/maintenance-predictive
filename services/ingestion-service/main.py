import os

import aio_pika
from fastapi import FastAPI, Header, HTTPException

from models import Measure

app = FastAPI(title="Ingestion Service")

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://admin:admin123@localhost:5672/")
API_KEY = os.environ.get("API_KEY", "dev-key")

connection = None
exchange = None


async def get_exchange():
    
    global connection, exchange
    if connection is None or connection.is_closed:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel(publisher_confirms=True)
        exchange = await channel.declare_exchange(
            "measures.fanout", aio_pika.ExchangeType.FANOUT, durable=True
        )
    return exchange


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/measures", status_code=202)
async def post_measure(measure: Measure, x_api_key: str = Header(None)):
    # 1. Verifier la cle d'API
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="clé d'API invalide")

    # 2. Publier dans RabbitMQ
    try:
        ex = await get_exchange()
        message = aio_pika.Message(
            body=measure.model_dump_json().encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(measure.message_id),
        )
        await ex.publish(message, routing_key="")
    except Exception:
        raise HTTPException(status_code=503, detail="RabbitMQ indisponible")

    # 3. Repondre - accepte -
    return {"status": "accepted", "message_id": str(measure.message_id)}