"""Tests for auto-sourcing: query generation, pipeline, and routes."""

from unittest.mock import patch, MagicMock

from app.models import Candidate, ScoringRun


class TestGenerateSearchQueries:
    @patch("app.sourcing.query_generator._call_claude")
    def test_generates_queries_from_exemplar_cvs(self, mock_claude, app):
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"queries": [{"role_title": "Account Executive", '
                '"keyword": "SaaS startup", "past_role_title": "BDR", '
                '"current_company_name": null, '
                '"rationale": "AEs who progressed from BDR roles"}]}'
            )
        ]
        mock_claude.return_value = mock_response

        from app.sourcing.query_generator import generate_search_queries

        with app.app_context():
            queries = generate_search_queries("fake-key", "ae")
            assert len(queries) == 1
            assert queries[0]["role_title"] == "Account Executive"
            assert queries[0]["keyword"] == "SaaS startup"
            assert queries[0]["past_role_title"] == "BDR"

    @patch("app.sourcing.query_generator._call_claude")
    def test_handles_markdown_code_blocks(self, mock_claude, app):
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='```json\n{"queries": [{"role_title": "CSM", '
                '"keyword": null, "past_role_title": null, '
                '"current_company_name": null, '
                '"rationale": "Direct CSM search"}]}\n```'
            )
        ]
        mock_claude.return_value = mock_response

        from app.sourcing.query_generator import generate_search_queries

        with app.app_context():
            queries = generate_search_queries("fake-key", "csm")
            assert len(queries) == 1
            assert queries[0]["role_title"] == "CSM"

    @patch("app.sourcing.query_generator._call_claude")
    def test_fallback_on_parse_error(self, mock_claude, app):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        mock_claude.return_value = mock_response

        from app.sourcing.query_generator import generate_search_queries

        with app.app_context():
            queries = generate_search_queries("fake-key", "ae")
            assert len(queries) == 1
            assert queries[0]["role_title"] == "Account Executive"
            assert "Fallback" in queries[0]["rationale"]


class TestSerperClient:
    def test_parse_linkedin_result(self):
        from app.api.serper import _parse_linkedin_result

        result = {
            "title": "Jane Doe - Account Executive - StartupCo | LinkedIn",
            "link": "https://uk.linkedin.com/in/janedoe",
            "snippet": "Experienced AE with 5 years in B2B SaaS...",
        }
        parsed = _parse_linkedin_result(result)
        assert parsed is not None
        assert parsed["full_name"] == "Jane Doe"
        assert parsed["current_title"] == "Account Executive"
        assert parsed["current_company"] == "StartupCo"
        assert parsed["slug"] == "janedoe"
        assert parsed["linkedin_url"] == "https://uk.linkedin.com/in/janedoe"

    def test_parse_title_with_at(self):
        from app.api.serper import _parse_linkedin_result

        result = {
            "title": "Sam Champion - Senior AE at Hook | LinkedIn",
            "link": "https://linkedin.com/in/samchampion",
            "snippet": "Founding AE...",
        }
        parsed = _parse_linkedin_result(result)
        assert parsed["full_name"] == "Sam Champion"
        assert parsed["current_title"] == "Senior AE"
        assert parsed["current_company"] == "Hook"

    def test_parse_skips_non_linkedin(self):
        from app.api.serper import _parse_linkedin_result

        result = {
            "title": "Some Page",
            "link": "https://example.com/page",
            "snippet": "Not LinkedIn",
        }
        assert _parse_linkedin_result(result) is None

    def test_normalize_serper_candidate(self):
        from app.api.serper import normalize_serper_candidate

        candidate = {
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "slug": "janedoe",
            "full_name": "Jane Doe",
            "current_title": "AE",
            "current_company": "StartupCo",
            "snippet": "Experienced AE in B2B SaaS",
        }
        normalized = normalize_serper_candidate(candidate)
        assert normalized["amplemarket_id"] == "li_janedoe"
        assert normalized["full_name"] == "Jane Doe"
        assert normalized["linkedin_url"] == "https://linkedin.com/in/janedoe"
        assert normalized["raw_data"]["source"] == "serper_google"


class TestAutoSourcingPipeline:
    @patch("app.pipeline.generate_outreach")
    @patch("app.pipeline.score_candidate")
    @patch("app.pipeline.SerperClient")
    @patch("app.pipeline.generate_search_queries")
    def test_full_auto_sourcing(
        self, mock_gen_queries, MockSerper, mock_score, mock_outreach, app, db
    ):
        # Setup query generation
        mock_gen_queries.return_value = [
            {
                "role_title": "Account Executive",
                "keyword": "SaaS",
                "past_role_title": None,
                "current_company_name": None,
                "rationale": "Direct AE search",
            }
        ]

        # Setup Serper search
        mock_serper = MagicMock()
        MockSerper.return_value = mock_serper
        mock_serper.search_linkedin_profiles.return_value = [
            {
                "linkedin_url": "https://linkedin.com/in/janedoe",
                "slug": "janedoe",
                "full_name": "Jane Doe",
                "current_title": "AE",
                "current_company": "StartupCo",
                "snippet": "Full cycle AE at StartupCo",
            }
        ]

        mock_score.return_value = {
            "score": 8.0,
            "reasoning": "Strong SaaS AE",
            "strengths": ["Full cycle"],
            "concerns": [],
            "outreach_angle": "Mention startup experience",
        }
        mock_outreach.return_value = "Hi Jane, your startup journey is impressive..."

        from app.pipeline import run_auto_sourcing_pipeline

        with app.app_context():
            run = run_auto_sourcing_pipeline(
                serper_api_key="fake",
                anthropic_api_key="fake",
                role_key="ae",
            )

            assert run.status == "completed"
            assert run.candidates_scored == 1
            assert run.avg_score == 8.0

            candidate = Candidate.query.filter_by(amplemarket_id="li_janedoe").first()
            assert candidate is not None
            assert candidate.score == 8.0
            assert candidate.source_list == "auto_sourced"
            assert candidate.outreach_message is not None

    @patch("app.pipeline.score_candidate")
    @patch("app.pipeline.SerperClient")
    @patch("app.pipeline.generate_search_queries")
    def test_deduplicates_across_queries(
        self, mock_gen_queries, MockSerper, mock_score, app, db
    ):
        mock_gen_queries.return_value = [
            {"role_title": "AE", "keyword": None, "past_role_title": None,
             "current_company_name": None, "rationale": "Query 1"},
            {"role_title": "Account Executive", "keyword": None, "past_role_title": None,
             "current_company_name": None, "rationale": "Query 2"},
        ]

        mock_serper = MagicMock()
        MockSerper.return_value = mock_serper

        # Both queries return the same person
        mock_serper.search_linkedin_profiles.return_value = [
            {
                "linkedin_url": "https://linkedin.com/in/janedoe",
                "slug": "janedoe",
                "full_name": "Jane Doe",
                "current_title": "AE",
                "current_company": "Co",
                "snippet": "AE at Co",
            }
        ]

        mock_score.return_value = {
            "score": 7.0, "reasoning": "Good", "strengths": [],
            "concerns": [], "outreach_angle": "",
        }

        from app.pipeline import run_auto_sourcing_pipeline

        with app.app_context():
            run = run_auto_sourcing_pipeline(
                serper_api_key="fake",
                anthropic_api_key="fake",
                role_key="ae",
            )

            # Should only score once despite appearing in both queries
            assert run.candidates_scored == 1

    @patch("app.pipeline.generate_search_queries")
    def test_handles_query_generation_failure(self, mock_gen_queries, app, db):
        mock_gen_queries.side_effect = Exception("Claude API down")

        from app.pipeline import run_auto_sourcing_pipeline

        with app.app_context():
            try:
                run_auto_sourcing_pipeline(
                    serper_api_key="fake",
                    anthropic_api_key="fake",
                    role_key="ae",
                )
                assert False, "Should have raised"
            except Exception:
                pass

            run = ScoringRun.query.first()
            assert run.status == "failed"

    @patch("app.pipeline.SerperClient")
    @patch("app.pipeline.generate_search_queries")
    def test_skips_failed_search_queries(
        self, mock_gen_queries, MockSerper, app, db
    ):
        mock_gen_queries.return_value = [
            {"role_title": "AE", "keyword": None, "past_role_title": None,
             "current_company_name": None, "rationale": "Will fail"},
        ]

        mock_serper = MagicMock()
        MockSerper.return_value = mock_serper
        mock_serper.search_linkedin_profiles.side_effect = Exception("Rate limited")

        from app.pipeline import run_auto_sourcing_pipeline

        with app.app_context():
            run = run_auto_sourcing_pipeline(
                serper_api_key="fake",
                anthropic_api_key="fake",
                role_key="ae",
            )

            assert run.status == "completed"
            assert run.candidates_scored == 0


class TestAutoSourceRoutes:
    def test_auto_source_page_loads(self, client):
        resp = client.get("/auto-source")
        assert resp.status_code == 200
        assert b"Auto Source" in resp.data

    def test_auto_source_page_shows_roles(self, client):
        resp = client.get("/auto-source")
        assert b"Account Executive" in resp.data
        assert b"Customer Success Manager" in resp.data

    @patch("app.routes.generate_search_queries")
    def test_preview_queries(self, mock_gen, client, app):
        mock_gen.return_value = [
            {"role_title": "AE", "keyword": "SaaS", "past_role_title": "BDR",
             "current_company_name": None, "rationale": "BDR to AE progression"}
        ]

        resp = client.post(
            "/auto-source",
            data={"role_key": "ae", "action": "preview"},
        )
        assert resp.status_code == 200
        assert b"BDR to AE progression" in resp.data

    def test_api_auto_source_requires_auth(self, client):
        resp = client.post("/api/auto-source", json={"role_key": "ae"})
        assert resp.status_code == 401

    def test_api_auto_source_validates_role(self, client, api_headers):
        resp = client.post(
            "/api/auto-source",
            headers=api_headers,
            json={"role_key": "invalid"},
        )
        assert resp.status_code == 400
        assert "Invalid role_key" in resp.get_json()["error"]

    @patch("app.routes.run_auto_sourcing_pipeline")
    def test_api_auto_source_success(self, mock_pipeline, client, db, api_headers):
        mock_run = ScoringRun(target_role="ae", status="completed")
        mock_run.candidates_scored = 15
        mock_run.avg_score = 6.8
        db.session.add(mock_run)
        db.session.commit()
        mock_pipeline.return_value = mock_run

        resp = client.post(
            "/api/auto-source",
            headers=api_headers,
            json={"role_key": "ae"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["candidates_scored"] == 15
