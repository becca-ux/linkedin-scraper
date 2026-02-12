"""Claude-powered candidate scoring."""

import json
import logging

import anthropic

from app.scoring.profiles import format_profile_for_prompt

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """\
You are an expert technical recruiter and talent evaluator for Hook, \
a B2B SaaS company (Series A, ~45 people).

Your job is to score candidates on a scale of 1-10 based on how well they \
match an ideal candidate profile. Be calibrated:
- 1-3: Poor fit, missing most requirements
- 4-5: Below average, missing key requirements but has some relevant experience
- 6-7: Good fit, meets most must-haves with some nice-to-haves
- 8-9: Strong fit, meets all must-haves and several nice-to-haves
- 10: Exceptional, perfect fit across all dimensions

You must respond with valid JSON only, in this exact format:
{
  "score": <number 1-10>,
  "reasoning": "<2-3 sentence explanation of the score>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "outreach_angle": "<one sentence suggesting the best hook for outreach>"
}
"""


def score_candidate(
    api_key: str,
    candidate_info: str,
    role_key: str,
    example_cvs: str | None = None,
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

    user_message += f"""
## Candidate to Evaluate
{candidate_info}

Score this candidate against the profile above. Return JSON only.
"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=SCORING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

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

    return "\n".join(parts)
