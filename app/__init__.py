import logging

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_object="config.Config"):
    application = Flask(__name__)
    application.config.from_object(config_object)

    # Fix Render's postgres:// URL (SQLAlchemy requires postgresql://)
    uri = application.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        application.config["SQLALCHEMY_DATABASE_URI"] = uri.replace(
            "postgres://", "postgresql://", 1
        )

    db.init_app(application)
    migrate.init_app(application, db)

    final_uri = application.config.get("SQLALCHEMY_DATABASE_URI", "")
    if final_uri.startswith("sqlite"):
        logger.warning(
            "Using SQLite (%s). Data will be lost on Render redeploys. "
            "Set DATABASE_URL to a PostgreSQL connection string for persistence.",
            final_uri,
        )

    from app.models import Candidate, ScoringRun  # noqa: F401
    from app.routes import main_bp

    application.register_blueprint(main_bp)

    # Auto-create tables for testing; production uses flask db upgrade
    if application.config.get("TESTING"):
        with application.app_context():
            db.create_all()

    return application


# Module-level `app` so that `gunicorn app:app` works (Render's default)
app = create_app()
