"""LinkedIn search and profile enrichment via Proxycurl API."""

import logging
from urllib.parse import quote

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

BASE_URL = "https://nubela.co/proxycurl"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))


class LinkedInClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def search_people(
        self,
        role_title: str,
        country: str = "GB",
        city: str = "London",
        keyword: str | None = None,
        past_role_title: str | None = None,
        current_company_name: str | None = None,
        page_size: int = 10,
    ) -> list[dict]:
        """Search LinkedIn for people matching criteria.

        Returns list of dicts with 'linkedin_profile_url' and 'profile' data.
        """
        params = {
            "country": country,
            "city": city,
            "current_role_title": role_title,
            "page_size": str(page_size),
            "enrich_profiles": "enrich",
        }
        if keyword:
            params["keyword"] = keyword
        if past_role_title:
            params["past_role_title"] = past_role_title
        if current_company_name:
            params["current_company_name"] = current_company_name

        data = self._get("/api/search/person/", params=params)
        results = data.get("results", [])
        logger.info("LinkedIn search returned %d results for '%s'", len(results), role_title)
        return results

    def get_profile(self, linkedin_url: str) -> dict:
        """Enrich a LinkedIn profile URL with full data."""
        data = self._get(
            "/api/v2/linkedin",
            params={"url": linkedin_url, "skills": "include"},
        )
        return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()


def normalize_linkedin_candidate(profile: dict, linkedin_url: str) -> dict:
    """Normalize Proxycurl profile data into our standard Candidate format."""
    full_name = profile.get("full_name") or "Unknown"
    slug = linkedin_url.rstrip("/").split("/")[-1]

    # Build experience summary from experiences list
    experiences = profile.get("experiences") or []
    exp_lines = []
    for exp in experiences[:6]:
        title = exp.get("title", "")
        company = exp.get("company", "")
        start = exp.get("starts_at")
        end = exp.get("ends_at")
        duration = ""
        if start:
            start_str = f"{start.get('month', '?')}/{start.get('year', '?')}"
            if end:
                end_str = f"{end.get('month', '?')}/{end.get('year', '?')}"
            else:
                end_str = "Present"
            duration = f" ({start_str} - {end_str})"
        desc = exp.get("description", "")
        line = f"{title} at {company}{duration}"
        if desc:
            # Truncate long descriptions
            line += f"\n  {desc[:300]}"
        exp_lines.append(line)

    experience_summary = "\n".join(exp_lines)

    # Current role
    current_title = None
    current_company = None
    if experiences:
        current = experiences[0]
        current_title = current.get("title")
        current_company = current.get("company")

    # Fallback to headline
    if not current_title:
        current_title = profile.get("headline", "")

    return {
        "amplemarket_id": f"li_{slug}",
        "full_name": full_name,
        "email": None,  # Proxycurl doesn't give email on basic enrichment
        "linkedin_url": linkedin_url,
        "current_title": current_title,
        "current_company": current_company,
        "location": profile.get("city") or profile.get("country_full_name") or "",
        "experience_summary": experience_summary,
        "raw_data": {
            "headline": profile.get("headline"),
            "summary": profile.get("summary"),
            "skills": [s for s in (profile.get("skills") or [])],
            "education": [
                {
                    "school_name": e.get("school", ""),
                    "degree": e.get("degree_name", ""),
                    "field": e.get("field_of_study", ""),
                }
                for e in (profile.get("education") or [])[:3]
            ],
            "source": "linkedin",
        },
    }
