from datetime import datetime, timezone

from app import db


class Candidate(db.Model):
    __tablename__ = "candidates"

    id = db.Column(db.Integer, primary_key=True)
    amplemarket_id = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    linkedin_url = db.Column(db.String(500))
    current_title = db.Column(db.String(255))
    current_company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    experience_summary = db.Column(db.Text)
    raw_data = db.Column(db.JSON)

    # Scoring
    score = db.Column(db.Float)
    score_reasoning = db.Column(db.Text)
    target_role = db.Column(db.String(100))  # AM, SC, Enterprise AE
    scored_at = db.Column(db.DateTime)

    # Outreach
    outreach_message = db.Column(db.Text)
    outreach_generated_at = db.Column(db.DateTime)

    # Metadata
    source_list = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Candidate {self.full_name} score={self.score}>"


class ScoringRun(db.Model):
    __tablename__ = "scoring_runs"

    id = db.Column(db.Integer, primary_key=True)
    target_role = db.Column(db.String(100), nullable=False)
    candidates_scored = db.Column(db.Integer, default=0)
    avg_score = db.Column(db.Float)
    started_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), default="running")  # running, completed, failed
    error_message = db.Column(db.Text)
