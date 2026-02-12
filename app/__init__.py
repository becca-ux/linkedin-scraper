from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Fix Render's postgres:// URL (SQLAlchemy requires postgresql://)
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace(
            "postgres://", "postgresql://", 1
        )

    db.init_app(app)
    migrate.init_app(app, db)

    from app.models import Candidate, ScoringRun  # noqa: F401
    from app.routes import main_bp

    app.register_blueprint(main_bp)

    # Auto-create tables for testing; production uses flask db upgrade
    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app
