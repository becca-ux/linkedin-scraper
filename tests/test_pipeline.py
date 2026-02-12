"""Tests for the scoring pipeline."""

from unittest.mock import patch, MagicMock

from app.models import Candidate, ScoringRun


class TestRunScoringPipeline:
    @patch("app.pipeline.generate_outreach")
    @patch("app.pipeline.score_candidate")
    @patch("app.pipeline.AmplemarketClient")
    def test_full_pipeline(self, MockClient, mock_score, mock_outreach, app, db):
        # Setup mocks
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.get_all_list_candidates.return_value = [
            {
                "id": "c1",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@test.com",
                "title": "AE",
                "company": {"name": "Acme"},
                "location": "SF",
            }
        ]

        mock_score.return_value = {
            "score": 8.5,
            "reasoning": "Great fit",
            "strengths": ["SaaS exp"],
            "concerns": [],
            "outreach_angle": "Mention SaaS",
        }

        mock_outreach.return_value = "Hi Jane, love your work at Acme..."

        from app.pipeline import run_scoring_pipeline

        with app.app_context():
            run = run_scoring_pipeline(
                amplemarket_api_key="fake",
                anthropic_api_key="fake",
                list_id="list1",
                role_key="account_manager",
            )

            assert run.status == "completed"
            assert run.candidates_scored == 1
            assert run.avg_score == 8.5

            candidate = Candidate.query.filter_by(amplemarket_id="c1").first()
            assert candidate is not None
            assert candidate.score == 8.5
            assert candidate.outreach_message == "Hi Jane, love your work at Acme..."

    @patch("app.pipeline.score_candidate")
    @patch("app.pipeline.AmplemarketClient")
    def test_no_outreach_for_low_scores(self, MockClient, mock_score, app, db):
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.get_all_list_candidates.return_value = [
            {"id": "c2", "first_name": "Low", "last_name": "Scorer"}
        ]

        mock_score.return_value = {
            "score": 3.0,
            "reasoning": "Poor fit",
            "strengths": [],
            "concerns": ["No SaaS"],
            "outreach_angle": "",
        }

        from app.pipeline import run_scoring_pipeline

        with app.app_context():
            run = run_scoring_pipeline(
                amplemarket_api_key="fake",
                anthropic_api_key="fake",
                list_id="list2",
                role_key="account_manager",
            )

            assert run.status == "completed"
            candidate = Candidate.query.filter_by(amplemarket_id="c2").first()
            assert candidate.outreach_message is None

    @patch("app.pipeline.AmplemarketClient")
    def test_pipeline_handles_api_failure(self, MockClient, app, db):
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.get_all_list_candidates.side_effect = Exception("API down")

        from app.pipeline import run_scoring_pipeline

        with app.app_context():
            try:
                run_scoring_pipeline(
                    amplemarket_api_key="fake",
                    anthropic_api_key="fake",
                    list_id="list3",
                    role_key="account_manager",
                )
                assert False, "Should have raised"
            except Exception:
                pass

            run = ScoringRun.query.first()
            assert run.status == "failed"
            assert "API down" in run.error_message

    @patch("app.pipeline.score_candidate")
    @patch("app.pipeline.AmplemarketClient")
    def test_updates_existing_candidate(self, MockClient, mock_score, app, db):
        # Pre-insert a candidate
        existing = Candidate(
            amplemarket_id="c3", full_name="Old Name", current_title="Old Title"
        )
        db.session.add(existing)
        db.session.commit()

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        mock_client_instance.get_all_list_candidates.return_value = [
            {"id": "c3", "first_name": "New", "last_name": "Name", "title": "New Title"}
        ]

        mock_score.return_value = {
            "score": 7.0,
            "reasoning": "Good",
            "strengths": [],
            "concerns": [],
            "outreach_angle": "",
        }

        from app.pipeline import run_scoring_pipeline

        with app.app_context():
            run_scoring_pipeline(
                amplemarket_api_key="fake",
                anthropic_api_key="fake",
                list_id="list4",
                role_key="account_manager",
            )

            candidates = Candidate.query.filter_by(amplemarket_id="c3").all()
            assert len(candidates) == 1
            assert candidates[0].full_name == "New Name"
            assert candidates[0].current_title == "New Title"
