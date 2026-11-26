-- init.sql : schéma officiel (Étudiant 2)
-- Remplace tools/dev_schema.sql

CREATE TABLE IF NOT EXISTS machines (
    machine_id text PRIMARY KEY,
    type       text NOT NULL DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS measurements (
    id            bigserial PRIMARY KEY,
    message_id    text UNIQUE NOT NULL,
    machine_id    text NOT NULL,
    seq           bigint NOT NULL,
    "timestamp"   timestamptz NOT NULL,
    status        text NOT NULL,
    temperature_c double precision,
    vibration_mms double precision,
    power_kw      double precision,
    rpm           double precision
);
CREATE INDEX IF NOT EXISTS idx_meas_machine_ts
    ON measurements (machine_id, "timestamp");

CREATE TABLE IF NOT EXISTS thresholds (
    machine_type text NOT NULL,
    metric       text NOT NULL,
    warn_min     double precision,
    warn_max     double precision,
    crit_min     double precision,
    crit_max     double precision,
    PRIMARY KEY (machine_type, metric)
);

CREATE TABLE IF NOT EXISTS health_scores (
    id           bigserial PRIMARY KEY,
    event_id     text UNIQUE NOT NULL,
    machine_id   text NOT NULL,
    state        text NOT NULL,
    health_score integer NOT NULL,
    reasons      jsonb,
    samples      integer,
    window_end   timestamptz NOT NULL,
    received_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_health_machine_end
    ON health_scores (machine_id, window_end);

CREATE TABLE IF NOT EXISTS alerts (
    id          bigserial PRIMARY KEY,
    machine_id  text NOT NULL,
    type        text NOT NULL,
    state       text NOT NULL DEFAULT 'active',  -- active | resolved
    created_at  timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);
-- une seule alerte active par machine et par type
CREATE UNIQUE INDEX IF NOT EXISTS one_active_alert
    ON alerts (machine_id, type) WHERE state = 'active';

-- Données de départ
INSERT INTO machines (machine_id, type) VALUES
    ('M-01','default'),('M-02','default'),('M-03','default'),
    ('M-04','default'),('M-05','default')
ON CONFLICT DO NOTHING;

INSERT INTO thresholds (machine_type, metric, warn_min, warn_max, crit_min, crit_max) VALUES
    ('default','temperature_c', NULL,  80, NULL,  90),
    ('default','vibration_mms', NULL,   6, NULL,   8),
    ('default','power_kw',      NULL,  30, NULL,  35),
    ('default','rpm',           2500, 3500, 2000, 4000)
ON CONFLICT DO NOTHING;

-- Rôle en lecture seule pour le monitoring
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'monitoring_ro') THEN
        CREATE ROLE monitoring_ro LOGIN PASSWORD 'change_me';
    END IF;
END
$$;
GRANT SELECT ON measurements, machines, thresholds TO monitoring_ro;