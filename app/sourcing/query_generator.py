"""Use Claude to analyze exemplar CVs and generate LinkedIn search queries."""

import json
import logging

import anthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.scoring.profiles import get_example_cvs, get_profile

logger = logging.getLogger(__name__)

QUERY_GEN_SYSTEM_PROMPT = """\
You are an expert technical recruiter who finds hidden-gem candidates on LinkedIn.

Given a set of exemplar CVs (people who are ideal for a role), you reverse-engineer \
the LinkedIn search queries that would surface more people like them.

Think about:
- What job titles do these people currently hold or have held?
- What kinds of companies (stage, industry, size) do they come from?
- What keywords appear across multiple exemplars?
- What career trajectories do they share (e.g. BDR -> AE)?

Generate MULTIPLE diverse search queries to cast a wide net. Each query should \
target a different angle or candidate archetype visible in the exemplars.

You must respond with valid JSON only, in this exact format:
{
  "queries": [
    {
      "role_title": "current job title to search for",
      "keyword": "optional keyword to narrow results, or null",
      "past_role_title": "optional past role title, or null",
      "current_company_name": "optional company name, or null",
      "rationale": "one sentence explaining why this query finds similar people"
    }
  ]
}

Generate between 3 and 6 queries. Focus on titles and keywords that would find \
people with SIMILAR backgrounds — not the exact same people.
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(
        (anthropic.APIStatusError, anthropic.APIConnectionError)
    ),
    reraise=True,
)
def _call_claude(client, system: str, user_message: str):
    return client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )


def generate_search_queries(api_key: str, role_key: str) -> list[dict]:
    """Analyze exemplar CVs for a role and generate LinkedIn search queries.

    Returns list of query dicts with keys:
        role_title, keyword, past_role_title, current_company_name, rationale
    """
    client = anthropic.Anthropic(api_key=api_key)
    profile = get_profile(role_key)
    example_cvs = get_example_cvs(role_key)

    user_message = f"""## Role We're Hiring For
{profile['title']} at Hook (B2B SaaS, Series A, ~45 people, London)

## Must-Haves
{chr(10).join('- ' + m for m in profile['must_haves'])}

## Exemplar CVs (people who are perfect for this role)
{example_cvs}

Analyze these exemplars and generate LinkedIn search queries that would find \
more people like them. Return JSON only.
"""

    response = _call_claude(client, QUERY_GEN_SYSTEM_PROMPT, user_message)
    response_text = response.content[0].text.strip()

    # Handle markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        response_text = "\n".join(lines)

    try:
        result = json.loads(response_text)
        queries = result.get("queries", [])
    except json.JSONDecodeError:
        logger.error("Failed to parse query generation response: %s", response_text)
        # Fallback: use the role title directly
        queries = [
            {
                "role_title": profile["title"],
                "keyword": "SaaS startup",
                "past_role_title": None,
                "current_company_name": None,
                "rationale": "Fallback: direct title search",
            }
        ]

    logger.info(
        "Generated %d search queries for role '%s': %s",
        len(queries),
        role_key,
        [q["role_title"] for q in queries],
    )
    return queries
