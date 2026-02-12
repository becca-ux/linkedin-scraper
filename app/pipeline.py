"""Main pipeline: pull candidates -> score -> store -> generate outreach."""

import logging
from datetime import datetime, timezone

from app import db
from app.api.amplemarket import AmplemarketClient, normalize_candidate
from app.models import Candidate, ScoringRun
from app.outreach.generator import generate_outreach
from app.scoring.scorer import format_candidate_for_scoring, score_candidate

logger = logging.getLogger(__name__)


def run_scoring_pipeline(
    amplemarket_api_key: str,
    anthropic_api_key: str,
    list_id: str,
    role_key: str,
    example_cvs: str | None = None,
    outreach_min_score: float = 7.0,
) -> ScoringRun:
    """Run the full scoring pipeline for a candidate list.

    1. Pull candidates from Amplemarket list
    2. Score each with Claude
    3. Store in database
    4. Generate outreach for top scorers

    Returns the ScoringRun record.
    """
    from app.scoring.profiles import get_profile

    profile = get_profile(role_key)

    run = ScoringRun(target_role=role_key, status="running")
    db.session.add(run)
    db.session.commit()

    try:
        # 1. Pull candidates
        client = AmplemarketClient(amplemarket_api_key)
        raw_candidates = client.get_all_list_candidates(list_id)
        logger.info("Pulled %d candidates from list %s", len(raw_candidates), list_id)

        scored_count = 0
        total_score = 0.0

        for raw in raw_candidates:
            normalized = normalize_candidate(raw)

            # Check if already exists
            existing = Candidate.query.filter_by(
                amplemarket_id=normalized["amplemarket_id"]
            ).first()

            if existing:
                candidate = existing
                # Update fields
                for key, value in normalized.items():
                    if key != "raw_data" and value:
                        setattr(candidate, key, value)
                candidate.raw_data = normalized["raw_data"]
            else:
                candidate = Candidate(**normalized)
                db.session.add(candidate)

            # 2. Score
            candidate_text = format_candidate_for_scoring(normalized)
            result = score_candidate(
                anthropic_api_key, candidate_text, role_key, example_cvs
            )

            candidate.score = result.get("score", 0)
            candidate.score_reasoning = result.get("reasoning", "")
            candidate.target_role = profile["title"]
            candidate.scored_at = datetime.now(timezone.utc)
            candidate.source_list = list_id

            scored_count += 1
            total_score += candidate.score

            # 3. Generate outreach for top candidates
            if candidate.score >= outreach_min_score:
                try:
                    message = generate_outreach(
                        api_key=anthropic_api_key,
                        candidate_name=candidate.full_name,
                        candidate_info=candidate_text,
                        role_title=profile["title"],
                        score_reasoning=candidate.score_reasoning,
                        outreach_angle=result.get("outreach_angle", ""),
                    )
                    candidate.outreach_message = message
                    candidate.outreach_generated_at = datetime.now(timezone.utc)
                except Exception:
                    logger.exception(
                        "Failed to generate outreach for %s", candidate.full_name
                    )

            db.session.commit()

        # Update run
        run.candidates_scored = scored_count
        run.avg_score = total_score / scored_count if scored_count > 0 else 0
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed"
        db.session.commit()

        logger.info(
            "Scoring run complete: %d candidates, avg score %.1f",
            scored_count,
            run.avg_score,
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.exception("Scoring pipeline failed")
        raise

    return run
