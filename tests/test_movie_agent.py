"""
Unit tests for the Movie Recommendation Agent.
"""

import os
import unittest
import tempfile
from unittest.mock import MagicMock, patch

from db import MovieDatabase
from notifier import format_markdown, format_telegram_html
from agent import FridayRecommendationResponse, MovieRecommendation


class TestMovieDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_movie_memory.db")
        self.db = MovieDatabase(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        profile = self.db.get_user_profile()
        self.assertIn("taste_summary", profile)
        self.assertIn("favorite_genres", profile)

    def test_record_and_prevent_duplicates(self):
        movie_1 = {
            "id": 101,
            "title": "Inception",
            "release_year": "2010",
            "rating": 8.8,
            "genres": ["Action", "Sci-Fi"],
            "streaming_providers": ["Netflix"]
        }
        summary = "A mind-bending heist thriller about entering dreams."
        self.db.record_recommendation(movie_1, summary)

        prev_ids = self.db.get_previously_recommended_ids()
        self.assertIn(101, prev_ids)

        history = self.db.get_user_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["title"], "Inception")
        self.assertEqual(history[0]["status"], "recommended")

    def test_record_feedback(self):
        movie_1 = {
            "id": 202,
            "title": "Interstellar",
            "release_year": "2014",
            "rating": 8.7,
            "genres": ["Adventure", "Drama", "Sci-Fi"],
            "streaming_providers": ["Amazon Prime Video"]
        }
        self.db.record_recommendation(movie_1, "A journey through a wormhole.")
        self.db.record_feedback(movie_id=202, status="liked", user_notes="Loved the soundtrack and emotional depth!")

        history = self.db.get_user_history()
        self.assertEqual(history[0]["status"], "liked")
        self.assertEqual(history[0]["user_notes"], "Loved the soundtrack and emotional depth!")

    def test_update_taste_profile(self):
        new_summary = "Loves cerebral science fiction and mystery thrillers."
        self.db.update_taste_profile(taste_summary=new_summary, favorite_genres="Sci-Fi, Mystery")
        profile = self.db.get_user_profile()
        self.assertEqual(profile["taste_summary"], new_summary)
        self.assertEqual(profile["favorite_genres"], "Sci-Fi, Mystery")


class TestNotifier(unittest.TestCase):
    def test_format_markdown_and_html(self):
        sample_response = FridayRecommendationResponse(
            thought_process="Selected a balanced mix of thriller, sci-fi, and mystery.",
            recommendations=[
                MovieRecommendation(
                    movie_id=1,
                    title="Dune",
                    release_year="2021",
                    rating=8.0,
                    streaming_providers=["Max", "Peacock"],
                    genres=["Sci-Fi", "Adventure"],
                    summary="A visual masterpiece detailing Paul Atreides journey to the desert planet Arrakis."
                ),
                MovieRecommendation(
                    movie_id=2,
                    title="Arrival",
                    release_year="2016",
                    rating=7.9,
                    streaming_providers=["Amazon Prime Video"],
                    genres=["Drama", "Sci-Fi"],
                    summary="A linguistics professor leads an elite team of investigators when gigantic spaceships touch down."
                ),
                MovieRecommendation(
                    movie_id=3,
                    title="Knives Out",
                    release_year="2019",
                    rating=7.9,
                    streaming_providers=["Netflix"],
                    genres=["Comedy", "Crime", "Drama"],
                    summary="A detective investigates the death of the patriarch of an eccentric, combative family."
                )
            ]
        )

        md = format_markdown(sample_response)
        self.assertIn("Dune", md)
        self.assertIn("Arrival", md)
        self.assertIn("Knives Out", md)
        self.assertIn("7.9/10", md)
        self.assertIn("Included in subscription", md)

        html = format_telegram_html(sample_response)
        self.assertIn("<b>1. Dune</b>", html)
        self.assertIn("Included with subscription", html)


if __name__ == "__main__":
    unittest.main()
