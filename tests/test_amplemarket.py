"""Tests for Amplemarket API client and data normalization."""

from app.api.amplemarket import normalize_candidate, _full_name, _build_experience_summary


class TestNormalizeCandidate:
    def test_basic_normalization(self):
        raw = {
            "id": 42,
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "linkedin_url": "https://linkedin.com/in/janesmith",
            "title": "Account Manager",
            "company": {"name": "Acme Corp"},
            "location": "San Francisco, CA",
        }
        result = normalize_candidate(raw)

        assert result["amplemarket_id"] == "42"
        assert result["full_name"] == "Jane Smith"
        assert result["email"] == "jane@example.com"
        assert result["linkedin_url"] == "https://linkedin.com/in/janesmith"
        assert result["current_title"] == "Account Manager"
        assert result["current_company"] == "Acme Corp"
        assert result["location"] == "San Francisco, CA"
        assert result["raw_data"] == raw

    def test_company_as_string(self):
        raw = {"id": 1, "first_name": "A", "last_name": "B", "company_name": "FlatCo"}
        result = normalize_candidate(raw)
        assert result["current_company"] == "FlatCo"

    def test_work_email_fallback(self):
        raw = {"id": 1, "first_name": "A", "last_name": "B", "work_email": "a@work.com"}
        result = normalize_candidate(raw)
        assert result["email"] == "a@work.com"

    def test_missing_fields(self):
        raw = {"id": 99}
        result = normalize_candidate(raw)
        assert result["amplemarket_id"] == "99"
        assert result["full_name"] == "Unknown"
        assert result["email"] is None


class TestFullName:
    def test_first_and_last(self):
        assert _full_name({"first_name": "John", "last_name": "Doe"}) == "John Doe"

    def test_name_fallback(self):
        assert _full_name({"name": "SingleName"}) == "SingleName"

    def test_unknown_fallback(self):
        assert _full_name({}) == "Unknown"


class TestBuildExperienceSummary:
    def test_current_role(self):
        raw = {"title": "AE", "company": {"name": "BigCo"}}
        result = _build_experience_summary(raw)
        assert "Current: AE at BigCo" in result

    def test_with_experiences(self):
        raw = {
            "experiences": [
                {"title": "SDR", "company_name": "StartupX", "duration": "2 years"},
                {"title": "BDR", "company_name": "StartupY"},
            ]
        }
        result = _build_experience_summary(raw)
        assert "SDR at StartupX (2 years)" in result
        assert "BDR at StartupY" in result

    def test_empty_data(self):
        assert _build_experience_summary({}) == ""

    def test_limits_to_five_experiences(self):
        raw = {
            "experiences": [
                {"title": f"Role {i}", "company_name": f"Co {i}"} for i in range(10)
            ]
        }
        result = _build_experience_summary(raw)
        assert "Role 4" in result
        assert "Role 5" not in result
