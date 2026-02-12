import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///candidates.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AMPLEMARKET_API_KEY = os.environ.get("AMPLEMARKET_API_KEY")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    SCORING_SCHEDULE = os.environ.get("SCORING_SCHEDULE", "daily")
    API_KEY = os.environ.get("API_KEY")  # Protects /api/* endpoints
