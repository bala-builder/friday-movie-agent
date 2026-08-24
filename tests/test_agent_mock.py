"""
Unit tests for TMDbClient and MovieAgent with mocked network and LLM calls.
"""

import os
import unittest
import tempfile
from unittest.mock import MagicMock, patch

from db import MovieDatabase
from tmdb_client import TMDbClient
from agent import MovieAgent, FridayRecommendationResponse, MovieRecommendation
from feedback_handler import refine_taste_profile


class TestTMDbClient(unittest.TestCase):
    @patch("requests.get")
    def test_flatrate_filtering(self, mock_get):
        # Mock watch providers response containing both flatrate (Netflix) and rent/buy (Apple TV purchase)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "US": {
                    "flatrate": [
                        {"provider_id": 8, "provider_name": "Netflix"},
                        {"provider_id": 9, "provider_name": "Amazon Prime Video"}
                    ],
                    "rent": [
                        {"provider_id": 2, "provider_name": "Apple TV"}
                    ],
                    "buy": [
                        {"provider_id": 3, "provider_name": "Google Play Movies"}
                    ]
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = TMDbClient(api_key="mock_key", region="US")
        providers = client.get_watch_providers_for_movie(123)

        # Should only include Netflix and Amazon Prime Video (flatrate), not Apple TV (rent) or Google Play (buy)
        self.assertEqual(len(providers), 2)
        self.assertIn("Netflix", providers)
        self.assertIn("Amazon Prime Video", providers)
        self.assertNotIn("Google Play Movies", providers)

    @patch("requests.get")
    def test_candidate_discovery(self, mock_get):
        # 1st call for /discover/movie, 2nd call for /watch/providers
        discover_res = MagicMock()
        discover_res.json.return_value = {
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "vote_average": 8.4,
                    "vote_count": 28000,
                    "release_date": "1999-10-15",
                    "genre_ids": [18, 53],
                    "overview": "An insomniac office worker..."
                },
                {
                    "id": 551,
                    "title": "Low Rated Movie",
                    "vote_average": 6.2,
                    "vote_count": 1200,
                    "release_date": "2020-01-01",
                    "genre_ids": [28],
                    "overview": "Low score movie..."
                }
            ]
        }
        discover_res.raise_for_status = MagicMock()

        providers_res = MagicMock()
        providers_res.json.return_value = {
            "results": {
                "US": {
                    "flatrate": [{"provider_id": 8, "provider_name": "Netflix"}]
                }
            }
        }
        providers_res.raise_for_status = MagicMock()

        mock_get.side_effect = [discover_res, providers_res]

        client = TMDbClient(api_key="mock_key", region="US", min_rating=7.5)
        candidates = client.fetch_candidate_movies(page_limit=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], 550)
        self.assertEqual(candidates[0]["title"], "Fight Club")
        self.assertEqual(candidates[0]["streaming_providers"], ["Netflix"])


class TestMovieAgentWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_agent_memory.db")
        self.db = MovieDatabase(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("agent.genai.Client")
    def test_agent_select_recommendations(self, mock_genai_client_class):
        mock_tmdb = MagicMock()
        mock_tmdb.fetch_candidate_movies.return_value = [
            {
                "id": 1,
                "title": "The Dark Knight",
                "release_year": "2008",
                "rating": 9.0,
                "genres": ["Action", "Crime", "Drama"],
                "streaming_providers": ["Peacock"]
            },
            {
                "id": 2,
                "title": "Spirited Away",
                "release_year": "2001",
                "rating": 8.5,
                "genres": ["Animation", "Fantasy"],
                "streaming_providers": ["Netflix"]
            },
            {
                "id": 3,
                "title": "Parasite",
                "release_year": "2019",
                "rating": 8.5,
                "genres": ["Drama", "Thriller"],
                "streaming_providers": ["Amazon Prime Video"]
            }
        ]

        # Mock Gemini response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed = FridayRecommendationResponse(
            thought_process="Curated a top-rated trio across superhero crime, animation, and dark thriller.",
            recommendations=[
                MovieRecommendation(
                    movie_id=1,
                    title="The Dark Knight",
                    release_year="2008",
                    rating=9.0,
                    streaming_providers=["Peacock"],
                    genres=["Action", "Crime", "Drama"],
                    summary="Batman faces the anarchic Joker in Gotham City."
                ),
                MovieRecommendation(
                    movie_id=2,
                    title="Spirited Away",
                    release_year="2001",
                    rating=8.5,
                    streaming_providers=["Netflix"],
                    genres=["Animation", "Fantasy"],
                    summary="A young girl wanders into a world ruled by gods and spirits."
                ),
                MovieRecommendation(
                    movie_id=3,
                    title="Parasite",
                    release_year="2019",
                    rating=8.5,
                    streaming_providers=["Amazon Prime Video"],
                    genres=["Drama", "Thriller"],
                    summary="A poor family schemes to become employed by a wealthy household."
                )
            ]
        )
        mock_client.models.generate_content.return_value = mock_response
        mock_genai_client_class.return_value = mock_client

        agent = MovieAgent(db=self.db, tmdb=mock_tmdb, gemini_api_key="mock_key")
        result = agent.select_friday_recommendations()

        self.assertEqual(len(result.recommendations), 3)
        self.assertEqual(result.recommendations[0].title, "The Dark Knight")

        # Verify recorded in DB
        prev_ids = self.db.get_previously_recommended_ids()
        self.assertEqual(set(prev_ids), {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
