"""Shared test fixtures."""

import pytest

from app import create_app, db as _db


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"  # in-memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret"
    AMPLEMARKET_API_KEY = "test-amplemarket-key"
    ANTHROPIC_API_KEY = "test-anthropic-key"
    PROXYCURL_API_KEY = "test-proxycurl-key"
    API_KEY = "test-api-key"


@pytest.fixture()
def app():
    app = create_app(config_object=TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def api_headers():
    """Headers with valid API key."""
    return {"X-API-Key": "test-api-key", "Content-Type": "application/json"}
