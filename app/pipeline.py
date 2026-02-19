"""Main pipeline: pull candidates -> score -> store -> generate outreach."""

import logging
from datetime import datetime, timezone

from app import db
from app.api.amplemarket import AmplemarketClient, normalize_candidate
from app.api.linkedin import LinkedInClient, normalize_linkedin_candidate
from app.api.serper import SerperClient, normalize_serper_candidate
from app.models import Candidate, ScoringRun
from app.outreach.generator import generate_outreach
from app.scoring.profiles import get_example_cvs
from app.scoring.scorer import format_candidate_for_scoring, score_candidate
from app.sourcing.query_generator import generate_search_queries

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

    # Auto-include exemplar CVs for calibration if not explicitly provided
    if not example_cvs:
        example_cvs = get_example_cvs(role_key)

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


def run_linkedin_search_pipeline(
    proxycurl_api_key: str,
    anthropic_api_key: str,
    role_key: str,
    role_title_search: str,
    country: str = "GB",
    city: str = "London",
    keyword: str | None = None,
    past_role_title: str | None = None,
    current_company_name: str | None = None,
    page_size: int = 10,
    outreach_min_score: float = 7.0,
) -> ScoringRun:
    """Search LinkedIn for candidates, score them, and store results.

    1. Search LinkedIn via Proxycurl
    2. Score each candidate with Claude
    3. Store in database
    4. Generate outreach for top scorers

    Returns the ScoringRun record.
    """
    from app.scoring.profiles import get_profile

    profile = get_profile(role_key)
    example_cvs = get_example_cvs(role_key)

    run = ScoringRun(target_role=role_key, status="running")
    db.session.add(run)
    db.session.commit()

    try:
        # 1. Search LinkedIn
        li_client = LinkedInClient(proxycurl_api_key)
        results = li_client.search_people(
            role_title=role_title_search,
            country=country,
            city=city,
            keyword=keyword,
            past_role_title=past_role_title,
            current_company_name=current_company_name,
            page_size=page_size,
        )

        scored_count = 0
        total_score = 0.0

        for result in results:
            linkedin_url = result.get("linkedin_profile_url", "")
            if not linkedin_url:
                continue

            # Use enriched profile data if available from search, otherwise fetch
            profile_data = result.get("profile") or {}
            if not profile_data or not profile_data.get("full_name"):
                try:
                    profile_data = li_client.get_profile(linkedin_url)
                except Exception:
                    logger.warning("Failed to enrich %s, skipping", linkedin_url)
                    continue

            normalized = normalize_linkedin_candidate(profile_data, linkedin_url)

            # Deduplicate by amplemarket_id (which is li_<slug> for LinkedIn)
            existing = Candidate.query.filter_by(
                amplemarket_id=normalized["amplemarket_id"]
            ).first()

            if existing:
                candidate = existing
                for key, value in normalized.items():
                    if key != "raw_data" and value:
                        setattr(candidate, key, value)
                candidate.raw_data = normalized["raw_data"]
            else:
                candidate = Candidate(**normalized)
                db.session.add(candidate)

            # 2. Score
            candidate_text = format_candidate_for_scoring(normalized)
            score_result = score_candidate(
                anthropic_api_key, candidate_text, role_key, example_cvs
            )

            candidate.score = score_result.get("score", 0)
            candidate.score_reasoning = score_result.get("reasoning", "")
            candidate.target_role = profile["title"]
            candidate.scored_at = datetime.now(timezone.utc)
            candidate.source_list = "linkedin_search"

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
                        outreach_angle=score_result.get("outreach_angle", ""),
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
            "LinkedIn search pipeline complete: %d candidates, avg score %.1f",
            scored_count,
            run.avg_score,
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.exception("LinkedIn search pipeline failed")
        raise

    return run


def run_auto_sourcing_pipeline(
    serper_api_key: str,
    anthropic_api_key: str,
    role_key: str,
    city: str = "London",
    num_results: int = 10,
    outreach_min_score: float = 7.0,
) -> ScoringRun:
    """Fully automated sourcing: analyze CVs -> generate queries -> search -> score -> outreach.

    1. Use Claude to analyze exemplar CVs and generate LinkedIn search queries
    2. Run each query via Serper.dev (Google search for LinkedIn profiles)
    3. Deduplicate across queries
    4. Score every candidate with Claude
    5. Generate outreach for top scorers

    Returns the ScoringRun record.
    """
    from app.scoring.profiles import get_profile

    profile = get_profile(role_key)
    example_cvs = get_example_cvs(role_key)

    run = ScoringRun(target_role=role_key, status="running")
    db.session.add(run)
    db.session.commit()

    try:
        # 1. Generate search queries from exemplar CVs
        queries = generate_search_queries(anthropic_api_key, role_key)
        logger.info(
            "Auto-sourcing: generated %d queries for %s", len(queries), role_key
        )

        # 2. Run each query via Serper and collect unique candidates
        serper_client = SerperClient(serper_api_key)
        seen_urls = set()
        all_candidates = []
        query_failures = []

        for query in queries:
            role_title = query.get("role_title", profile["title"])
            keyword = query.get("keyword")
            past_role_title = query.get("past_role_title")
            current_company_name = query.get("current_company_name")

            logger.info(
                "Auto-sourcing query: title='%s' keyword='%s' past='%s' company='%s'",
                role_title,
                keyword,
                past_role_title,
                current_company_name,
            )

            try:
                results = serper_client.search_linkedin_profiles(
                    role_title=role_title,
                    city=city,
                    keyword=keyword,
                    past_role_title=past_role_title,
                    current_company_name=current_company_name,
                    num_results=num_results,
                )
            except Exception as e:
                logger.exception(
                    "Search query failed for title='%s', skipping", role_title
                )
                query_failures.append(f"{role_title}: {e}")
                continue

            for result in results:
                linkedin_url = result.get("linkedin_url", "")
                if not linkedin_url or linkedin_url in seen_urls:
                    continue
                seen_urls.add(linkedin_url)

                normalized = normalize_serper_candidate(result)
                all_candidates.append(normalized)

        logger.info(
            "Auto-sourcing: found %d unique candidates across %d queries (%d failed)",
            len(all_candidates),
            len(queries),
            len(query_failures),
        )

        # If ALL queries failed, mark the run as failed with details
        if not all_candidates and query_failures:
            error_detail = "; ".join(query_failures[:3])
            raise RuntimeError(
                f"All {len(query_failures)} search queries failed. "
                f"Check your Serper API key / credits. First error: {error_detail}"
            )

        # 3. Enrich candidates with secondary Google search
        for normalized in all_candidates:
            name = normalized.get("full_name", "")
            company = normalized.get("current_company", "")
            title = normalized.get("current_title", "")
            if name and name != "Unknown":
                try:
                    research = serper_client.research_person(
                        full_name=name,
                        current_company=company or None,
                        current_title=title or None,
                        num_results=3,
                    )
                    if research:
                        # Append research to experience summary and raw data
                        existing_summary = normalized.get("experience_summary", "")
                        normalized["experience_summary"] = (
                            f"{existing_summary}\n\nAdditional public info:\n{research}"
                            if existing_summary
                            else research
                        )
                        normalized["raw_data"]["research"] = research
                except Exception:
                    logger.warning("Research enrichment failed for %s", name)

        # 4. Score and store each candidate
        scored_count = 0
        total_score = 0.0

        for normalized in all_candidates:
            existing = Candidate.query.filter_by(
                amplemarket_id=normalized["amplemarket_id"]
            ).first()

            if existing:
                candidate = existing
                for key, value in normalized.items():
                    if key != "raw_data" and value:
                        setattr(candidate, key, value)
                candidate.raw_data = normalized["raw_data"]
            else:
                candidate = Candidate(**normalized)
                db.session.add(candidate)

            candidate_text = format_candidate_for_scoring(normalized)
            score_result = score_candidate(
                anthropic_api_key, candidate_text, role_key, example_cvs
            )

            candidate.score = score_result.get("score", 0)
            candidate.score_reasoning = score_result.get("reasoning", "")
            candidate.target_role = profile["title"]
            candidate.scored_at = datetime.now(timezone.utc)
            candidate.source_list = "auto_sourced"

            scored_count += 1
            total_score += candidate.score

            # 5. Generate outreach for top candidates
            if candidate.score >= outreach_min_score:
                try:
                    message = generate_outreach(
                        api_key=anthropic_api_key,
                        candidate_name=candidate.full_name,
                        candidate_info=candidate_text,
                        role_title=profile["title"],
                        score_reasoning=candidate.score_reasoning,
                        outreach_angle=score_result.get("outreach_angle", ""),
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
            "Auto-sourcing complete: %d candidates scored, avg %.1f",
            scored_count,
            run.avg_score,
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.exception("Auto-sourcing pipeline failed")
        raise

    return run
