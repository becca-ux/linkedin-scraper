"""Tests for scoring module."""

import json
from unittest.mock import MagicMock, patch

from app.scoring.scorer import score_candidate, format_candidate_for_scoring
from app.scoring.profiles import get_profile, format_profile_for_prompt, ROLE_PROFILES


class TestRoleProfiles:
    def test_get_valid_profile(self):
        profile = get_profile("account_manager")
        assert profile["title"] == "Account Manager"
        assert len(profile["must_haves"]) > 0

    def test_get_invalid_profile(self):
        try:
            get_profile("ceo")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown role" in str(e)

    def test_all_profiles_have_required_keys(self):
        for key, profile in ROLE_PROFILES.items():
            assert "title" in profile
            assert "description" in profile
            assert "must_haves" in profile
            assert "nice_to_haves" in profile
            assert "red_flags" in profile

    def test_format_profile_for_prompt(self):
        text = format_profile_for_prompt("solutions_consultant")
        assert "Solutions Consultant" in text
        assert "Must-Haves:" in text
        assert "Nice-to-Haves:" in text
        assert "Red Flags:" in text


class TestFormatCandidate:
    def test_basic_formatting(self):
        candidate = {
            "full_name": "Jane Doe",
            "current_title": "Account Executive",
            "current_company": "SaaS Corp",
            "location": "NYC",
        }
        result = format_candidate_for_scoring(candidate)
        assert "Jane Doe" in result
        assert "Account Executive" in result
        assert "SaaS Corp" in result
        assert "NYC" in result

    def test_with_raw_data(self):
        candidate = {
            "full_name": "Test",
            "raw_data": {
                "headline": "Sales Leader",
                "skills": ["Salesforce", "Negotiation", "CRM"],
                "education": [{"school_name": "MIT", "degree": "BS"}],
            },
        }
        result = format_candidate_for_scoring(candidate)
        assert "Sales Leader" in result
        assert "Salesforce" in result
        assert "MIT" in result

    def test_handles_missing_fields(self):
        candidate = {"full_name": "Minimal"}
        result = format_candidate_for_scoring(candidate)
        assert "Minimal" in result


class TestScoreCandidate:
    @patch("app.scoring.scorer._call_claude")
    def test_successful_scoring(self, mock_call):
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "score": 8,
                        "reasoning": "Strong fit.",
                        "strengths": ["SaaS experience"],
                        "concerns": ["Short tenure"],
                        "outreach_angle": "Mention their SaaS background",
                    }
                )
            )
        ]
        mock_call.return_value = mock_response

        result = score_candidate("fake-key", "Jane Doe, AE at Acme", "account_manager")

        assert result["score"] == 8
        assert "Strong fit" in result["reasoning"]
        assert len(result["strengths"]) == 1

    @patch("app.scoring.scorer._call_claude")
    def test_handles_markdown_json(self, mock_call):
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='```json\n{"score": 6, "reasoning": "OK", "strengths": [], "concerns": [], "outreach_angle": ""}\n```'
            )
        ]
        mock_call.return_value = mock_response

        result = score_candidate("fake-key", "Candidate info", "enterprise_ae")
        assert result["score"] == 6

    @patch("app.scoring.scorer._call_claude")
    def test_handles_unparseable_response(self, mock_call):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON at all")]
        mock_call.return_value = mock_response

        result = score_candidate("fake-key", "Candidate info", "enterprise_ae")
        assert result["score"] == 0
        assert "Parsing error" in result["reasoning"]
