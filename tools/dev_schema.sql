-- Schéma PROVISOIRE pour tester le monitoring en local.
-- Le schéma officiel est init.sql (Étudiant 2).
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
CREATE INDEX IF NOT EXISTS idx_meas_machine_ts ON measurements (machine_id, "timestamp");

CREATE TABLE IF NOT EXISTS thresholds (
    machine_type text NOT NULL,
    metric       text NOT NULL,
    warn_min     double precision,
    warn_max     double precision,
    crit_min     double precision,
    crit_max     double precision,
    PRIMARY KEY (machine_type, metric)
);

INSERT INTO machines (machine_id, type) VALUES
    ('M-01','default'),('M-02','default'),('M-03','default'),('M-04','default'),('M-05','default')
ON CONFLICT DO NOTHING;

INSERT INTO thresholds (machine_type, metric, warn_min, warn_max, crit_min, crit_max) VALUES
    ('default','temperature_c', NULL,  80, NULL,  90),
    ('default','vibration_mms', NULL,   6, NULL,   8),
    ('default','power_kw',      NULL,  30, NULL,  35),
    ('default','rpm',           2500, 3500, 2000, 4000)
ON CONFLICT DO NOTHING;