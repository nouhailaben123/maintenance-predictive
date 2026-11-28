import os

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "admin123")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "maintenance")

app = FastAPI(title="query-api", description="Lecture seule : machines, mesures, scores, alertes")

# CORS : le dashboard (port 8080) appelle cette API (port 8002)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def query(sql, params=()):
    """Run one read-only SQL query and return the rows as dicts."""
    try:
        with psycopg.connect(
            host=POSTGRES_HOST,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB,
            row_factory=dict_row,
            # the session itself refuses any write (INSERT, UPDATE, DELETE...)
            options="-c default_transaction_read_only=on",
        ) as conn:
            return conn.execute(sql, params).fetchall()
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")


def check_machine(machine_id):
    rows = query("SELECT 1 FROM machines WHERE machine_id = %s", (machine_id,))
    if not rows:
        raise HTTPException(status_code=404, detail=f"unknown machine {machine_id}")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


MACHINES_SQL = """
SELECT m.machine_id, m.type,
       lm.status, lm."timestamp" AS m_timestamp,
       lm.temperature_c, lm.vibration_mms, lm.power_kw, lm.rpm,
       h.state, h.health_score, h.reasons, h.window_end
FROM machines m
LEFT JOIN LATERAL (
    SELECT status, "timestamp", temperature_c, vibration_mms, power_kw, rpm
    FROM measurements
    WHERE machine_id = m.machine_id
    ORDER BY "timestamp" DESC
    LIMIT 1
) lm ON true
LEFT JOIN LATERAL (
    SELECT state, health_score, reasons, window_end
    FROM health_scores
    WHERE machine_id = m.machine_id
    ORDER BY window_end DESC
    LIMIT 1
) h ON true
ORDER BY m.machine_id
"""


@app.get("/machines")
def list_machines():
    result = []
    for r in query(MACHINES_SQL):
        latest = None
        if r["m_timestamp"] is not None:
            latest = {
                "timestamp": r["m_timestamp"],
                "temperature_c": r["temperature_c"],
                "vibration_mms": r["vibration_mms"],
                "power_kw": r["power_kw"],
                "rpm": r["rpm"],
            }
        result.append(
            {
                "machine_id": r["machine_id"],
                "type": r["type"],
                "status": r["status"],
                "state": r["state"],
                "health_score": r["health_score"],
                "reasons": r["reasons"],
                "window_end": r["window_end"],
                "latest": latest,
            }
        )
    return result


@app.get("/machines/{machine_id}/measurements")
def machine_measurements(machine_id: str, limit: int = Query(60, ge=1, le=1000)):
    check_machine(machine_id)
    rows = query(
        """
        SELECT "timestamp", temperature_c, vibration_mms, power_kw, rpm
        FROM measurements
        WHERE machine_id = %s
        ORDER BY "timestamp" DESC
        LIMIT %s
        """,
        (machine_id, limit),
    )
    rows.reverse()  # oldest first, ready for a chart
    return rows


@app.get("/machines/{machine_id}/health")
def machine_health(machine_id: str, minutes: int = Query(30, ge=1, le=1440)):
    check_machine(machine_id)
    return query(
        """
        SELECT window_end, health_score, state
        FROM health_scores
        WHERE machine_id = %s
          AND window_end >= now() - (%s * interval '1 minute')
        ORDER BY window_end
        """,
        (machine_id, minutes),
    )


@app.get("/alerts")
def list_alerts(status: str | None = None):
    sql = """
        SELECT id, machine_id, type, severity, status, created_at, resolved_at
        FROM alerts
    """
    params = ()
    if status:
        sql += " WHERE status = %s"
        params = (status,)
    sql += " ORDER BY created_at DESC LIMIT 200"
    return query(sql, params)
