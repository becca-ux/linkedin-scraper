"""Claude-powered candidate scoring."""

import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.scoring.profiles import format_profile_for_prompt

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """\
You are an expert technical recruiter and talent evaluator for Hook, \
a B2B SaaS company (Series A, ~45 people).

Your job is to score candidates on a scale of 1-10 based on how well they \
match an ideal candidate profile.

IMPORTANT SCORING GUIDANCE:
- You may receive LIMITED data (e.g. from Google search snippets rather than \
full CVs). Score based on the STRENGTH OF AVAILABLE SIGNALS, not on data \
completeness.
- Use your knowledge of companies, industries, and career paths to INFER fit. \
For example, if someone is "Senior CSM at a known B2B SaaS scaleup", that's a \
strong positive signal even without seeing their specific metrics.
- Missing data is NEUTRAL, not negative. A candidate whose snippet strongly \
suggests relevant experience should score 6-7+, not 4-5.
- Only score LOW (1-4) when available signals actively indicate POOR fit \
(wrong industry, wrong seniority, red flags visible in the data).

Calibration:
- 1-3: Poor fit — available signals indicate misalignment (wrong industry, \
wrong level, visible red flags)
- 4-5: Weak signals — title or background only loosely related, or signals \
point to missing key requirements
- 6-7: Promising — title, company type, and available context suggest a good \
match for most must-haves
- 8-9: Strong — multiple signals clearly align with must-haves AND nice-to-haves \
(right title + right company type + relevant keywords/experience visible)
- 10: Exceptional — overwhelming evidence of perfect fit across all dimensions

You must respond with valid JSON only, in this exact format:
{
  "score": <number 1-10>,
  "reasoning": "<2-3 sentence explanation of the score>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "outreach_angle": "<one sentence suggesting the best hook for outreach>"
}
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((anthropic.APIStatusError, anthropic.APIConnectionError)),
    reraise=True,
)
def _call_claude(client, system: str, user_message: str):
    """Call Claude with automatic retry on transient errors."""
    return client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )


def score_candidate(
    api_key: str,
    candidate_info: str,
    role_key: str,
    example_cvs: str | None = None,
    feedback_history: str | None = None,
) -> dict:
    """Score a single candidate against a role profile using Claude.

    Args:
        api_key: Anthropic API key.
        candidate_info: Text summary of the candidate.
        role_key: One of account_manager, solutions_consultant, enterprise_ae.
        example_cvs: Optional text of example ideal CVs for calibration.

    Returns:
        Dict with score, reasoning, strengths, concerns, outreach_angle.
    """
    client = anthropic.Anthropic(api_key=api_key)

    profile_text = format_profile_for_prompt(role_key)

    user_message = f"""## Ideal Candidate Profile
{profile_text}
"""

    if example_cvs:
        user_message += f"""
## Example CVs of Strong Candidates (for calibration)
{example_cvs}
"""

    if feedback_history:
        user_message += f"""
## Hiring Manager Feedback on Past Candidates
The hiring manager has reviewed previous candidates and given this feedback.
Use it to calibrate your scoring — penalise patterns they've rejected and
reward patterns they've approved.

{feedback_history}
"""

    user_message += f"""
## Candidate to Evaluate
{candidate_info}

Score this candidate against the profile above. Return JSON only.
"""

    response = _call_claude(client, SCORING_SYSTEM_PROMPT, user_message)

    response_text = response.content[0].text.strip()

    # Handle markdown code blocks in response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.startswith("```")]
        response_text = "\n".join(lines)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response: %s", response_text)
        result = {
            "score": 0,
            "reasoning": f"Parsing error. Raw response: {response_text[:500]}",
            "strengths": [],
            "concerns": ["Could not parse scoring response"],
            "outreach_angle": "",
        }

    return result


def build_feedback_history(role_key: str) -> str | None:
    """Query past feedback for a role and format it for the scoring prompt.

    Returns None if no feedback exists yet.
    """
    from app.models import Candidate
    from app.scoring.profiles import get_profile

    profile = get_profile(role_key)
    role_title = profile["title"]

    reviewed = (
        Candidate.query
        .filter(
            Candidate.target_role == role_title,
            Candidate.feedback.isnot(None),
        )
        .order_by(Candidate.feedback_at.desc())
        .limit(20)
        .all()
    )

    if not reviewed:
        return None

    lines = []
    for c in reviewed:
        status = c.feedback.upper()
        detail = f"{c.full_name} — {c.current_title or '?'} at {c.current_company or '?'}"
        reason_parts = []
        if c.feedback_reason:
            reason_parts.append(c.feedback_reason)
        if c.feedback_note:
            reason_parts.append(c.feedback_note)
        reason_str = f" (Reason: {'; '.join(reason_parts)})" if reason_parts else ""
        lines.append(f"- {status}: {detail}{reason_str}")

    return "\n".join(lines)


def format_candidate_for_scoring(candidate: dict) -> str:
    """Format candidate data into a text block for scoring."""
    parts = [f"Name: {candidate.get('full_name', 'Unknown')}"]

    if candidate.get("current_title"):
        parts.append(f"Current Title: {candidate['current_title']}")
    if candidate.get("current_company"):
        parts.append(f"Current Company: {candidate['current_company']}")
    if candidate.get("location"):
        parts.append(f"Location: {candidate['location']}")
    if candidate.get("experience_summary"):
        parts.append(f"\nExperience:\n{candidate['experience_summary']}")

    # Include any extra fields from raw data that might be useful
    raw = candidate.get("raw_data", {})
    if raw.get("headline"):
        parts.append(f"Headline: {raw['headline']}")
    if raw.get("summary"):
        parts.append(f"Summary: {raw['summary']}")
    if raw.get("skills"):
        skills = raw["skills"]
        if isinstance(skills, list):
            parts.append(f"Skills: {', '.join(skills[:15])}")
    if raw.get("education"):
        edu = raw["education"]
        if isinstance(edu, list):
            for e in edu[:3]:
                school = e.get("school_name", "")
                degree = e.get("degree", "")
                if school:
                    parts.append(f"Education: {degree} - {school}")
    if raw.get("research"):
        parts.append(f"\nPublic information found online:\n{raw['research']}")

    return "\n".join(parts)
