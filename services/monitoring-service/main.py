import logging
import sys

from app import config as cfg, metrics
from app.db import rebuild_windows, refresh_reference
from app.engine import Engine
from app.runner import run

def main():
    logging.basicConfig(level=cfg.LOG_LEVEL, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s [monitoring] %(message)s")
    metrics.start(cfg.METRICS_PORT)
    engine = Engine()
    refresh_reference(engine)       # seuils (échec toléré : sera retenté)
    rebuild_windows(engine)         # AVANT de consommer q.monitoring
    run(engine)

if __name__ == "__main__":
    main()