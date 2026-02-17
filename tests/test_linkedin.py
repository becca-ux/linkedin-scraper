"""Tests for LinkedIn search module."""

from unittest.mock import MagicMock, patch

from app.api.linkedin import LinkedInClient, normalize_linkedin_candidate


class TestNormalizeLinkedInCandidate:
    def test_basic_normalization(self):
        profile = {
            "full_name": "Jane Doe",
            "headline": "Account Executive at Acme",
            "city": "London",
            "country_full_name": "United Kingdom",
            "summary": "Sales leader with 5 years experience",
            "skills": ["Salesforce", "SaaS", "Negotiation"],
            "experiences": [
                {
                    "title": "Account Executive",
                    "company": "Acme Corp",
                    "starts_at": {"month": 1, "year": 2023},
                    "ends_at": None,
                    "description": "Closing enterprise deals",
                },
                {
                    "title": "BDR",
                    "company": "StartupCo",
                    "starts_at": {"month": 6, "year": 2021},
                    "ends_at": {"month": 12, "year": 2022},
                    "description": "Outbound prospecting",
                },
            ],
            "education": [
                {
                    "school": "UCL",
                    "degree_name": "BSc",
                    "field_of_study": "Economics",
                }
            ],
        }
        result = normalize_linkedin_candidate(profile, "https://linkedin.com/in/janedoe")

        assert result["amplemarket_id"] == "li_janedoe"
        assert result["full_name"] == "Jane Doe"
        assert result["linkedin_url"] == "https://linkedin.com/in/janedoe"
        assert result["current_title"] == "Account Executive"
        assert result["current_company"] == "Acme Corp"
        assert result["location"] == "London"
        assert "Account Executive at Acme Corp" in result["experience_summary"]
        assert "BDR at StartupCo" in result["experience_summary"]
        assert result["raw_data"]["source"] == "linkedin"
        assert "Salesforce" in result["raw_data"]["skills"]

    def test_missing_experiences(self):
        profile = {
            "full_name": "Minimal Person",
            "headline": "Looking for work",
            "experiences": [],
        }
        result = normalize_linkedin_candidate(profile, "https://linkedin.com/in/minimal")
        assert result["full_name"] == "Minimal Person"
        assert result["current_title"] == "Looking for work"
        assert result["experience_summary"] == ""

    def test_slug_extraction(self):
        result = normalize_linkedin_candidate(
            {"full_name": "Test"},
            "https://www.linkedin.com/in/john-smith-123/",
        )
        assert result["amplemarket_id"] == "li_john-smith-123"


class TestLinkedInClient:
    @patch("app.api.linkedin.LinkedInClient._get")
    def test_search_people(self, mock_get):
        mock_get.return_value = {
            "results": [
                {
                    "linkedin_profile_url": "https://linkedin.com/in/test",
                    "profile": {"full_name": "Test Person"},
                }
            ]
        }
        client = LinkedInClient("fake-key")
        results = client.search_people(role_title="Account Executive")
        assert len(results) == 1
        assert results[0]["linkedin_profile_url"] == "https://linkedin.com/in/test"

    @patch("app.api.linkedin.LinkedInClient._get")
    def test_get_profile(self, mock_get):
        mock_get.return_value = {"full_name": "Jane Doe", "headline": "AE"}
        client = LinkedInClient("fake-key")
        profile = client.get_profile("https://linkedin.com/in/janedoe")
        assert profile["full_name"] == "Jane Doe"


class TestLinkedInSearchRoute:
    def test_search_page_get(self, client):
        resp = client.get("/search")
        assert resp.status_code == 200
        assert b"LinkedIn Candidate Search" in resp.data

    def test_search_page_missing_proxycurl_key(self, client):
        resp = client.post("/search", data={
            "role_key": "ae",
            "role_title": "Account Executive",
        })
        assert resp.status_code == 200
        assert b"PROXYCURL_API_KEY not configured" in resp.data
