"""Web routes for the candidate sourcing dashboard."""

from flask import Blueprint, current_app, jsonify, render_template, request

from app import db
from app.models import Candidate, ScoringRun
from app.pipeline import run_scoring_pipeline
from app.scoring.profiles import ROLE_PROFILES

main_bp = Blueprint("main", __name__)


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


@main_bp.route("/api/run", methods=["POST"])
def trigger_run():
    """Trigger a scoring run via API."""
    data = request.get_json()
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


@main_bp.route("/api/candidates")
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
