"""Amplemarket API client for pulling candidate lists."""

import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.amplemarket.com/api/v1"


class AmplemarketClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def get_lists(self) -> list[dict]:
        """Fetch all saved candidate lists."""
        resp = self._get("/lists")
        return resp.get("data", [])

    def get_list_candidates(
        self, list_id: str, page: int = 1, per_page: int = 50
    ) -> dict:
        """Fetch candidates from a specific list.

        Returns dict with 'candidates' list and 'pagination' info.
        """
        resp = self._get(
            f"/lists/{list_id}/people",
            params={"page": page, "per_page": per_page},
        )
        return resp

    def get_all_list_candidates(self, list_id: str) -> list[dict]:
        """Fetch all candidates from a list, handling pagination."""
        all_candidates = []
        page = 1

        while True:
            resp = self.get_list_candidates(list_id, page=page)
            candidates = resp.get("data", [])
            if not candidates:
                break
            all_candidates.extend(candidates)
            pagination = resp.get("pagination", {})
            if page >= pagination.get("total_pages", 1):
                break
            page += 1

        logger.info(
            "Fetched %d candidates from list %s", len(all_candidates), list_id
        )
        return all_candidates

    def get_person(self, person_id: str) -> dict:
        """Fetch detailed info for a single person."""
        resp = self._get(f"/people/{person_id}")
        return resp.get("data", {})

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()


def normalize_candidate(raw: dict) -> dict:
    """Normalize Amplemarket candidate data into our standard format."""
    return {
        "amplemarket_id": str(raw.get("id", "")),
        "full_name": _full_name(raw),
        "email": raw.get("email") or raw.get("work_email"),
        "linkedin_url": raw.get("linkedin_url"),
        "current_title": raw.get("title"),
        "current_company": raw.get("company", {}).get("name")
        if isinstance(raw.get("company"), dict)
        else raw.get("company_name"),
        "location": raw.get("location"),
        "experience_summary": _build_experience_summary(raw),
        "raw_data": raw,
    }


def _full_name(raw: dict) -> str:
    first = raw.get("first_name", "")
    last = raw.get("last_name", "")
    if first and last:
        return f"{first} {last}"
    return raw.get("name", "Unknown")


def _build_experience_summary(raw: dict) -> str:
    """Build a text summary of experience from raw Amplemarket data."""
    parts = []

    title = raw.get("title")
    company = (
        raw.get("company", {}).get("name")
        if isinstance(raw.get("company"), dict)
        else raw.get("company_name")
    )
    if title and company:
        parts.append(f"Current: {title} at {company}")

    experiences = raw.get("experiences", [])
    for exp in experiences[:5]:
        exp_title = exp.get("title", "")
        exp_company = exp.get("company_name", "")
        exp_duration = exp.get("duration", "")
        if exp_title:
            line = exp_title
            if exp_company:
                line += f" at {exp_company}"
            if exp_duration:
                line += f" ({exp_duration})"
            parts.append(line)

    return "\n".join(parts) if parts else ""
