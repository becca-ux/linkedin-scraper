"""Web routes for the candidate sourcing dashboard."""

import functools
import hmac

from flask import Blueprint, current_app, jsonify, render_template, request

from app import db
from app.models import Candidate, ScoringRun
from app.pipeline import run_scoring_pipeline
from app.scheduler import schedule_scoring_run, _scheduled_jobs
from app.scoring.profiles import ROLE_PROFILES

main_bp = Blueprint("main", __name__)


def require_api_key(f):
    """Decorator that checks for a valid API key on /api/* endpoints."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        configured_key = current_app.config.get("API_KEY")
        if not configured_key:
            # No key configured = auth disabled (dev mode)
            return f(*args, **kwargs)

        provided = request.headers.get("X-API-Key", "")
        if not provided or not hmac.compare_digest(provided, configured_key):
            return jsonify({"error": "Invalid or missing API key"}), 401

        return f(*args, **kwargs)

    return decorated


# ---------- Health check ----------


@main_bp.route("/health")
def health():
    """Health check for load balancers / uptime monitors."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "ok"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 503


# ---------- Web UI ----------


@main_bp.route("/")
def index():
    """Dashboard showing scored candidates."""
    role_filter = request.args.get("role")
    min_score = request.args.get("min_score", type=float)

    query = Candidate.query.filter(Candidate.score.isnot(None))

    if role_filter:
        query = query.filter(Candidate.target_role == role_filter)
    if min_score:
        query = query.filter(Candidate.score >= min_score)

    candidates = query.order_by(Candidate.score.desc()).all()

    roles = list(ROLE_PROFILES.values())
    recent_runs = (
        ScoringRun.query.order_by(ScoringRun.started_at.desc()).limit(10).all()
    )

    return render_template(
        "index.html",
        candidates=candidates,
        roles=roles,
        recent_runs=recent_runs,
        current_role=role_filter,
        current_min_score=min_score,
    )


@main_bp.route("/candidate/<int:candidate_id>")
def candidate_detail(candidate_id):
    """Detail view for a single candidate."""
    candidate = db.get_or_404(Candidate, candidate_id)
    return render_template("candidate.html", candidate=candidate)


# ---------- API ----------


@main_bp.route("/api/run", methods=["POST"])
@require_api_key
def trigger_run():
    """Trigger a scoring run via API."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    list_id = data.get("list_id")
    role_key = data.get("role_key")
    example_cvs = data.get("example_cvs")

    if not list_id or not role_key:
        return jsonify({"error": "list_id and role_key are required"}), 400

    if role_key not in ROLE_PROFILES:
        return (
            jsonify(
                {"error": f"Invalid role_key. Valid: {list(ROLE_PROFILES.keys())}"}
            ),
            400,
        )

    config = current_app.config
    try:
        run = run_scoring_pipeline(
            amplemarket_api_key=config["AMPLEMARKET_API_KEY"],
            anthropic_api_key=config["ANTHROPIC_API_KEY"],
            list_id=list_id,
            role_key=role_key,
            example_cvs=example_cvs,
        )
        return jsonify(
            {
                "status": "completed",
                "run_id": run.id,
                "candidates_scored": run.candidates_scored,
                "avg_score": run.avg_score,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/schedule", methods=["POST"])
@require_api_key
def schedule_run():
    """Schedule a recurring scoring run."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    list_id = data.get("list_id")
    role_key = data.get("role_key")
    schedule = data.get("schedule", "daily")

    if not list_id or not role_key:
        return jsonify({"error": "list_id and role_key are required"}), 400
    if role_key not in ROLE_PROFILES:
        return jsonify({"error": f"Invalid role_key. Valid: {list(ROLE_PROFILES.keys())}"}), 400
    if schedule not in ("daily", "weekly"):
        return jsonify({"error": "schedule must be 'daily' or 'weekly'"}), 400

    schedule_scoring_run(
        app=current_app._get_current_object(),
        list_id=list_id,
        role_key=role_key,
        schedule=schedule,
        example_cvs=data.get("example_cvs"),
    )
    return jsonify({"status": "scheduled", "schedule": schedule})


@main_bp.route("/api/schedules")
@require_api_key
def list_schedules():
    """List all scheduled scoring runs."""
    return jsonify(_scheduled_jobs)


@main_bp.route("/api/candidates")
@require_api_key
def api_candidates():
    """JSON API for candidates."""
    role = request.args.get("role")
    min_score = request.args.get("min_score", type=float, default=0)

    query = Candidate.query.filter(
        Candidate.score.isnot(None), Candidate.score >= min_score
    )
    if role:
        query = query.filter(Candidate.target_role == role)

    candidates = query.order_by(Candidate.score.desc()).all()

    return jsonify(
        [
            {
                "id": c.id,
                "name": c.full_name,
                "title": c.current_title,
                "company": c.current_company,
                "score": c.score,
                "reasoning": c.score_reasoning,
                "target_role": c.target_role,
                "outreach_message": c.outreach_message,
                "linkedin_url": c.linkedin_url,
            }
            for c in candidates
        ]
    )
