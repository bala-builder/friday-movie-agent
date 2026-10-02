"""
Unit tests for JevClient feedback parsing and fallback behavior.
"""

import unittest
from unittest.mock import MagicMock, patch
from jev_client import JevClient, ParsedFeedback


class TestJevClient(unittest.TestCase):
    def test_fallback_heuristic_positive(self):
        client = JevClient(api_key=None)
        feedback = "Loved this dark gritty thriller, but it dragged on and was too long."
        parsed = client.parse_user_feedback(feedback)

        self.assertGreaterEqual(parsed.sentiment_score, 4.0)
        self.assertEqual(parsed.tone_preference, "dark_gritty")
        self.assertEqual(parsed.pacing_preference, "slow_burn")
        self.assertGreater(parsed.complained_about_runtime, 0.5)

    def test_fallback_heuristic_negative_fast(self):
        client = JevClient(api_key=None)
        feedback = "Hated it. Fast paced nonsense with terrible acting. No horror please."
        parsed = client.parse_user_feedback(feedback)

        self.assertLessEqual(parsed.sentiment_score, 2.0)
        self.assertEqual(parsed.pacing_preference, "fast_paced")
        self.assertEqual(parsed.disliked_genre, "horror")

    @patch("jev_client.TypeSafeClient")
    def test_jev_system_one_mocked(self, mock_typesafe_cls):
        mock_instance = MagicMock()
        mock_response = MagicMock()

        # Mock answers
        sentiment_ans = MagicMock()
        sentiment_ans.score = 4.5
        pacing_ans = MagicMock()
        pacing_ans.choice = "slow_burn"
        tone_ans = MagicMock()
        tone_ans.choice = "cerebral_thoughtprovoking"
        wants_ans = MagicMock()
        wants_ans.noul = 0.95
        runtime_ans = MagicMock()
        runtime_ans.noul = 0.1
        cat_ans = MagicMock()
        cat_ans.choice = "under_2h"
        genre_ans = MagicMock()
        genre_ans.choice = "none"

        mock_response.answers = {
            "sentiment": sentiment_ans,
            "pacing": pacing_ans,
            "tone": tone_ans,
            "wants_similar": wants_ans,
            "runtime_complaint": runtime_ans,
            "runtime_category": cat_ans,
            "disliked_genre": genre_ans
        }
        mock_instance.system_one.return_value = mock_response
        mock_typesafe_cls.return_value = mock_instance

        client = JevClient(api_key="mock_key")
        client.client = mock_instance  # ensure assigned

        parsed = client.parse_user_feedback("Amazing philosophical mystery!")
        self.assertEqual(parsed.sentiment_score, 4.5)
        self.assertEqual(parsed.pacing_preference, "slow_burn")
        self.assertEqual(parsed.tone_preference, "cerebral_thoughtprovoking")
        self.assertAlmostEqual(parsed.wants_more_like_this, 0.95)


if __name__ == "__main__":
    unittest.main()
