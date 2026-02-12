"""Generate personalized outreach messages for top candidates."""

import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

OUTREACH_SYSTEM_PROMPT = """\
You are a recruiting outreach specialist for Hook, a B2B SaaS startup \
(Series A, ~45 people). You write short, personalized LinkedIn/email messages \
that feel human and genuine — never generic or spammy.

Guidelines:
- Keep messages under 150 words
- Lead with something specific about the candidate (their work, background)
- Be direct about why you're reaching out
- Sound like a real person, not a template
- Don't oversell — be honest about the stage and opportunity
- End with a low-pressure ask (quick chat, not "apply now")
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
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )


def generate_outreach(
    api_key: str,
    candidate_name: str,
    candidate_info: str,
    role_title: str,
    score_reasoning: str,
    outreach_angle: str,
) -> str:
    """Generate a personalized outreach message for a candidate.

    Args:
        api_key: Anthropic API key.
        candidate_name: Candidate's full name.
        candidate_info: Text summary of the candidate.
        role_title: The role being hired for.
        score_reasoning: Why this candidate scored well.
        outreach_angle: Suggested angle from scoring.

    Returns:
        The outreach message text.
    """
    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Write a personalized outreach message for this candidate.

## Candidate
Name: {candidate_name}
{candidate_info}

## Role
{role_title} at Hook (B2B SaaS, Series A, ~45 people)

## Why They're a Good Fit
{score_reasoning}

## Suggested Angle
{outreach_angle}

Write the outreach message. Return just the message text, nothing else.
"""

    response = _call_claude(client, OUTREACH_SYSTEM_PROMPT, user_message)
    return response.content[0].text.strip()
