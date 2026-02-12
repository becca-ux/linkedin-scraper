"""Application entry point."""

import logging

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

application = create_app()

if __name__ == "__main__":
    application.run(debug=True, port=5000)
