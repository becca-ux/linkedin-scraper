"""Application entry point."""

import logging
import atexit

from app import app as application
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

# Start the background scheduler for recurring scoring runs
start_scheduler()
atexit.register(stop_scheduler)

if __name__ == "__main__":
    application.run(debug=True, port=5000)
