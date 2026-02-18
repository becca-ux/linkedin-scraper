"""Web routes for the candidate sourcing dashboard."""

import functools
import hmac

from flask import Blueprint, current_app, jsonify, render_template, request

from app import db
from app.models import Candidate, ScoringRun
from app.outreach.generator import generate_outreach
from app.pipeline import (
    run_scoring_pipeline,
    run_linkedin_search_pipeline,
    run_auto_sourcing_pipeline,
)
from app.scheduler import schedule_scoring_run, _scheduled_jobs
from app.scoring.profiles import ROLE_PROFILES, get_profile, get_example_cvs
from app.scoring.scorer import score_candidate
from app.sourcing.query_generator import generate_search_queries

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

    try:
        query = Candidate.query.filter(Candidate.score.isnot(None))

        if role_filter:
            query = query.filter(Candidate.target_role == role_filter)
        if min_score:
            query = query.filter(Candidate.score >= min_score)

        candidates = query.order_by(Candidate.score.desc()).all()
        recent_runs = (
            ScoringRun.query.order_by(ScoringRun.started_at.desc()).limit(10).all()
        )
    except Exception:
        candidates = []
        recent_runs = []

    roles = list(ROLE_PROFILES.values())

    return render_template(
        "index.html",
        candidates=candidates,
        roles=roles,
        recent_runs=recent_runs,
        current_role=role_filter,
        current_min_score=min_score,
        role_keys=ROLE_PROFILES,
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


@main_bp.route("/api/search", methods=["POST"])
@require_api_key
def linkedin_search():
    """Search LinkedIn for candidates, score, and store them."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    role_key = data.get("role_key")
    role_title_search = data.get("role_title")

    if not role_key or not role_title_search:
        return jsonify({"error": "role_key and role_title are required"}), 400

    if role_key not in ROLE_PROFILES:
        return jsonify(
            {"error": f"Invalid role_key. Valid: {list(ROLE_PROFILES.keys())}"}
        ), 400

    config = current_app.config
    if not config.get("PROXYCURL_API_KEY"):
        return jsonify({"error": "PROXYCURL_API_KEY not configured"}), 500

    try:
        run = run_linkedin_search_pipeline(
            proxycurl_api_key=config["PROXYCURL_API_KEY"],
            anthropic_api_key=config["ANTHROPIC_API_KEY"],
            role_key=role_key,
            role_title_search=role_title_search,
            country=data.get("country", "GB"),
            city=data.get("city", "London"),
            keyword=data.get("keyword"),
            past_role_title=data.get("past_role_title"),
            current_company_name=data.get("current_company"),
            page_size=min(data.get("page_size", 10), 25),
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


@main_bp.route("/search", methods=["GET", "POST"])
def search_page():
    """Paste a CV / profile text, score it, and generate outreach."""
    from datetime import datetime, timezone
    import hashlib

    result = None
    error = None

    if request.method == "POST":
        role_key = request.form.get("role_key")
        candidate_name = request.form.get("candidate_name", "").strip()
        candidate_text = request.form.get("candidate_text", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip() or None

        config = current_app.config
        anthropic_key = config.get("ANTHROPIC_API_KEY") or ""
        if not anthropic_key or anthropic_key.startswith("your_"):
            error = "ANTHROPIC_API_KEY not configured. Set a real API key in your environment variables."
        elif not role_key or not candidate_name or not candidate_text:
            error = "Role, candidate name, and profile text are all required."
        else:
            try:
                profile = get_profile(role_key)
                example_cvs = get_example_cvs(role_key)

                # Score with Claude
                score_result = score_candidate(
                    config["ANTHROPIC_API_KEY"],
                    f"Name: {candidate_name}\n\n{candidate_text}",
                    role_key,
                    example_cvs,
                )

                # Generate unique ID from name + text
                text_hash = hashlib.md5(
                    f"{candidate_name}{candidate_text[:200]}".encode()
                ).hexdigest()[:12]
                candidate_id = f"paste_{text_hash}"

                # Store in DB
                existing = Candidate.query.filter_by(amplemarket_id=candidate_id).first()
                if existing:
                    candidate = existing
                else:
                    candidate = Candidate(
                        amplemarket_id=candidate_id,
                        full_name=candidate_name,
                    )
                    db.session.add(candidate)

                candidate.linkedin_url = linkedin_url
                candidate.experience_summary = candidate_text
                candidate.score = score_result.get("score", 0)
                candidate.score_reasoning = score_result.get("reasoning", "")
                candidate.target_role = profile["title"]
                candidate.scored_at = datetime.now(timezone.utc)
                candidate.source_list = "manual_paste"
                candidate.raw_data = {"source": "manual_paste"}

                # Generate outreach for good candidates
                outreach = None
                if candidate.score >= 7.0:
                    outreach = generate_outreach(
                        api_key=config["ANTHROPIC_API_KEY"],
                        candidate_name=candidate_name,
                        candidate_info=candidate_text,
                        role_title=profile["title"],
                        score_reasoning=candidate.score_reasoning,
                        outreach_angle=score_result.get("outreach_angle", ""),
                    )
                    candidate.outreach_message = outreach
                    candidate.outreach_generated_at = datetime.now(timezone.utc)

                db.session.commit()

                result = {
                    "name": candidate_name,
                    "score": candidate.score,
                    "reasoning": score_result.get("reasoning", ""),
                    "strengths": score_result.get("strengths", []),
                    "concerns": score_result.get("concerns", []),
                    "outreach": outreach,
                    "candidate_id": candidate.id,
                }
            except Exception as e:
                error = str(e)

    return render_template(
        "search.html",
        role_keys=ROLE_PROFILES,
        result=result,
        error=error,
    )


@main_bp.route("/auto-source", methods=["GET", "POST"])
def auto_source_page():
    """One-click automated candidate sourcing from exemplar CVs."""
    result = None
    error = None
    queries = None

    if request.method == "POST":
        role_key = request.form.get("role_key")
        country = request.form.get("country", "GB").strip() or "GB"
        city = request.form.get("city", "London").strip() or "London"
        page_size = int(request.form.get("page_size", 10))
        action = request.form.get("action", "run")

        config = current_app.config

        def _key_ok(name):
            val = config.get(name) or ""
            return val and not val.startswith("your_")

        if not _key_ok("ANTHROPIC_API_KEY"):
            error = "ANTHROPIC_API_KEY not configured. Set a real API key in your environment variables."
        elif not _key_ok("SERPER_API_KEY"):
            error = "SERPER_API_KEY not configured. Sign up at serper.dev to get a free API key, then set it in your environment variables."
        elif not role_key or role_key not in ROLE_PROFILES:
            error = "Please select a valid role."
        elif action == "preview":
            # Just generate and show the queries without running them
            try:
                queries = generate_search_queries(
                    config["ANTHROPIC_API_KEY"], role_key
                )
            except Exception as e:
                error = f"Failed to generate queries: {e}"
        else:
            # Run pipeline synchronously so errors are visible and results
            # are ready before the page renders.
            try:
                run = run_auto_sourcing_pipeline(
                    serper_api_key=config["SERPER_API_KEY"],
                    anthropic_api_key=config["ANTHROPIC_API_KEY"],
                    role_key=role_key,
                    city=city,
                    num_results=min(page_size, 25),
                )
                result = {
                    "status": run.status,
                    "message": (
                        f"Auto-sourcing complete for {ROLE_PROFILES[role_key]['title']}: "
                        f"{run.candidates_scored} candidates scored"
                        f" (avg {run.avg_score:.1f})."
                        if run.candidates_scored
                        else f"Auto-sourcing ran but found 0 candidates. Try a different role or city."
                    ),
                }
            except Exception as e:
                error = f"Auto-sourcing failed: {e}"

    return render_template(
        "auto_source.html",
        role_keys=ROLE_PROFILES,
        result=result,
        error=error,
        queries=queries,
    )


@main_bp.route("/api/auto-source", methods=["POST"])
@require_api_key
def api_auto_source():
    """API endpoint: fully automated candidate sourcing."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    role_key = data.get("role_key")
    if not role_key or role_key not in ROLE_PROFILES:
        return jsonify(
            {"error": f"Invalid role_key. Valid: {list(ROLE_PROFILES.keys())}"}
        ), 400

    config = current_app.config
    serper_key = config.get("SERPER_API_KEY") or ""
    anthropic_key = config.get("ANTHROPIC_API_KEY") or ""
    if not serper_key or serper_key.startswith("your_"):
        return jsonify({"error": "SERPER_API_KEY not configured"}), 500
    if not anthropic_key or anthropic_key.startswith("your_"):
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    try:
        run = run_auto_sourcing_pipeline(
            serper_api_key=config["SERPER_API_KEY"],
            anthropic_api_key=config["ANTHROPIC_API_KEY"],
            role_key=role_key,
            city=data.get("city", "London"),
            num_results=min(data.get("num_results", 10), 25),
            outreach_min_score=data.get("outreach_min_score", 7.0),
        )
        return jsonify(
            {
                "status": run.status,
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
