"""Application entry point."""

import logging
import atexit

from app import create_app
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

application = create_app()

# Start the background scheduler for recurring scoring runs
start_scheduler()
atexit.register(stop_scheduler)

if __name__ == "__main__":
    application.run(debug=True, port=5000)
