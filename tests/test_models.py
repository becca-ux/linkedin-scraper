"""Tests for database models."""

from datetime import datetime, timezone

from app.models import Candidate, ScoringRun


class TestCandidate:
    def test_create_candidate(self, db):
        c = Candidate(amplemarket_id="abc123", full_name="Jane Doe")
        db.session.add(c)
        db.session.commit()

        assert c.id is not None
        assert c.full_name == "Jane Doe"
        assert c.created_at is not None

    def test_unique_amplemarket_id(self, db):
        c1 = Candidate(amplemarket_id="same", full_name="One")
        c2 = Candidate(amplemarket_id="same", full_name="Two")
        db.session.add(c1)
        db.session.commit()

        db.session.add(c2)
        try:
            db.session.commit()
            assert False, "Should have raised IntegrityError"
        except Exception:
            db.session.rollback()

    def test_repr(self, db):
        c = Candidate(amplemarket_id="x", full_name="Test User", score=7.5)
        assert "Test User" in repr(c)
        assert "7.5" in repr(c)


class TestScoringRun:
    def test_create_run(self, db):
        run = ScoringRun(target_role="account_manager")
        db.session.add(run)
        db.session.commit()

        assert run.id is not None
        assert run.status == "running"
        assert run.candidates_scored == 0
        assert run.started_at is not None

    def test_complete_run(self, db):
        run = ScoringRun(target_role="enterprise_ae")
        db.session.add(run)
        db.session.commit()

        run.status = "completed"
        run.candidates_scored = 10
        run.avg_score = 6.5
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        fetched = db.session.get(ScoringRun, run.id)
        assert fetched.status == "completed"
        assert fetched.avg_score == 6.5
