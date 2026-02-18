"""Google search for LinkedIn profiles via Serper.dev API."""

import logging
import re

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(
        exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    )


class SerperClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _search(self, query: str, num: int = 10) -> dict:
        resp = requests.post(
            SERPER_URL,
            json={"q": query, "num": num},
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def search_linkedin_profiles(
        self,
        role_title: str,
        city: str = "London",
        keyword: str | None = None,
        past_role_title: str | None = None,
        current_company_name: str | None = None,
        num_results: int = 10,
    ) -> list[dict]:
        """Search Google for LinkedIn profiles matching criteria.

        Returns list of dicts with: linkedin_url, full_name, headline, snippet
        """
        # Build Google search query
        parts = ['site:linkedin.com/in/', f'"{role_title}"']
        if keyword:
            parts.append(f'"{keyword}"')
        if past_role_title:
            parts.append(f'"{past_role_title}"')
        if current_company_name:
            parts.append(f'"{current_company_name}"')
        if city:
            parts.append(city)

        query = " ".join(parts)
        logger.info("Serper search: %s", query)

        data = self._search(query, num=num_results)
        organic = data.get("organic", [])

        candidates = []
        for result in organic:
            link = result.get("link", "")
            if "linkedin.com/in/" not in link:
                continue

            parsed = _parse_linkedin_result(result)
            if parsed:
                candidates.append(parsed)

        logger.info(
            "Serper found %d LinkedIn profiles for '%s'",
            len(candidates),
            role_title,
        )
        return candidates


def _parse_linkedin_result(result: dict) -> dict | None:
    """Extract candidate info from a Google search result for a LinkedIn profile."""
    link = result.get("link", "")
    title = result.get("title", "")
    snippet = result.get("snippet", "")

    if not link or "linkedin.com/in/" not in link:
        return None

    # Extract slug for unique ID
    slug = link.rstrip("/").split("/in/")[-1].split("?")[0]
    if not slug:
        return None

    # Parse title: typically "Name - Title - Company | LinkedIn"
    # or "Name - Title at Company | LinkedIn"
    clean_title = title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()

    full_name = "Unknown"
    current_title = ""
    current_company = ""

    # Split by " - " which LinkedIn uses as separator
    parts = [p.strip() for p in clean_title.split(" - ")]
    if len(parts) >= 1:
        full_name = parts[0]
    if len(parts) >= 2:
        # Second part could be "Title at Company" or just "Title"
        title_part = parts[1]
        at_match = re.match(r"^(.+?)\s+at\s+(.+)$", title_part, re.IGNORECASE)
        if at_match:
            current_title = at_match.group(1).strip()
            current_company = at_match.group(2).strip()
        else:
            current_title = title_part
    if len(parts) >= 3 and not current_company:
        current_company = parts[2]

    return {
        "linkedin_url": link,
        "slug": slug,
        "full_name": full_name,
        "current_title": current_title,
        "current_company": current_company,
        "snippet": snippet,
    }


def normalize_serper_candidate(candidate: dict) -> dict:
    """Normalize a Serper search result into our standard Candidate format."""
    slug = candidate["slug"]

    return {
        "amplemarket_id": f"li_{slug}",
        "full_name": candidate["full_name"],
        "email": None,
        "linkedin_url": candidate["linkedin_url"],
        "current_title": candidate.get("current_title"),
        "current_company": candidate.get("current_company"),
        "location": "",
        "experience_summary": candidate.get("snippet", ""),
        "raw_data": {
            "headline": candidate.get("current_title", ""),
            "summary": candidate.get("snippet", ""),
            "skills": [],
            "education": [],
            "source": "serper_google",
        },
    }
