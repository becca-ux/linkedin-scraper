"""Tests for web routes and API endpoints."""

import json
from unittest.mock import patch

from app.models import Candidate, ScoringRun


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"


class TestDashboard:
    def test_index_empty(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_with_candidates(self, client, db):
        c = Candidate(
            amplemarket_id="123",
            full_name="Jane Doe",
            score=8.5,
            target_role="Account Manager",
        )
        db.session.add(c)
        db.session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Jane Doe" in resp.data

    def test_index_filter_by_role(self, client, db):
        c1 = Candidate(
            amplemarket_id="1", full_name="Alice", score=8.0, target_role="Account Executive"
        )
        c2 = Candidate(
            amplemarket_id="2", full_name="Bob", score=7.0, target_role="Customer Success Manager"
        )
        db.session.add_all([c1, c2])
        db.session.commit()

        resp = client.get("/?role=Account Executive")
        assert resp.status_code == 200
        assert b"Alice" in resp.data
        assert b"Bob" not in resp.data

    def test_index_filter_by_min_score(self, client, db):
        c1 = Candidate(amplemarket_id="1", full_name="High", score=9.0, target_role="AM")
        c2 = Candidate(amplemarket_id="2", full_name="Low", score=3.0, target_role="AM")
        db.session.add_all([c1, c2])
        db.session.commit()

        resp = client.get("/?min_score=7")
        assert resp.status_code == 200
        assert b"High" in resp.data
        assert b"Low" not in resp.data


class TestCandidateDetail:
    def test_detail_exists(self, client, db):
        c = Candidate(amplemarket_id="123", full_name="Jane Doe", score=8.5)
        db.session.add(c)
        db.session.commit()

        resp = client.get(f"/candidate/{c.id}")
        assert resp.status_code == 200
        assert b"Jane Doe" in resp.data

    def test_detail_not_found(self, client):
        resp = client.get("/candidate/999")
        assert resp.status_code == 404


class TestAPIAuth:
    def test_api_rejects_missing_key(self, client):
        resp = client.get("/api/candidates")
        assert resp.status_code == 401

    def test_api_rejects_wrong_key(self, client):
        resp = client.get("/api/candidates", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_api_accepts_correct_key(self, client, api_headers):
        resp = client.get("/api/candidates", headers=api_headers)
        assert resp.status_code == 200


class TestAPICandidates:
    def test_returns_scored_candidates(self, client, db, api_headers):
        c = Candidate(
            amplemarket_id="1",
            full_name="Test Person",
            current_title="AE",
            current_company="Acme",
            score=8.0,
            target_role="Account Executive",
        )
        db.session.add(c)
        db.session.commit()

        resp = client.get("/api/candidates", headers=api_headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Person"
        assert data[0]["score"] == 8.0

    def test_filters_by_min_score(self, client, db, api_headers):
        c1 = Candidate(amplemarket_id="1", full_name="High", score=9.0)
        c2 = Candidate(amplemarket_id="2", full_name="Low", score=2.0)
        db.session.add_all([c1, c2])
        db.session.commit()

        resp = client.get("/api/candidates?min_score=5", headers=api_headers)
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "High"

    def test_excludes_unscored(self, client, db, api_headers):
        c = Candidate(amplemarket_id="1", full_name="No Score")
        db.session.add(c)
        db.session.commit()

        resp = client.get("/api/candidates", headers=api_headers)
        assert resp.get_json() == []


class TestAPITriggerRun:
    def test_requires_json_body(self, client, api_headers):
        resp = client.post("/api/run", headers=api_headers)
        assert resp.status_code == 400

    def test_requires_list_id_and_role(self, client, api_headers):
        resp = client.post(
            "/api/run", headers=api_headers, json={"list_id": "abc"}
        )
        assert resp.status_code == 400
        assert "role_key" in resp.get_json()["error"]

    def test_rejects_invalid_role(self, client, api_headers):
        resp = client.post(
            "/api/run",
            headers=api_headers,
            json={"list_id": "abc", "role_key": "ceo"},
        )
        assert resp.status_code == 400
        assert "Invalid role_key" in resp.get_json()["error"]

    @patch("app.routes.run_scoring_pipeline")
    def test_successful_run(self, mock_pipeline, client, db, api_headers):
        mock_run = ScoringRun(target_role="ae", status="completed")
        mock_run.candidates_scored = 5
        mock_run.avg_score = 7.2
        db.session.add(mock_run)
        db.session.commit()

        mock_pipeline.return_value = mock_run

        resp = client.post(
            "/api/run",
            headers=api_headers,
            json={"list_id": "list123", "role_key": "ae"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["candidates_scored"] == 5
