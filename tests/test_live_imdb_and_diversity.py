"""
Unit tests for live IMDb ratings (via OMDb) and multi-slice discovery in tmdb_client.py.
"""

import unittest
from unittest.mock import MagicMock, patch
from tmdb_client import TMDbClient


class TestLiveIMDbAndDiversity(unittest.TestCase):
    @patch("requests.get")
    def test_live_imdb_rating_fetch(self, mock_get):
        mock_res = MagicMock()
        mock_res.json.return_value = {
            "Response": "True",
            "Title": "Interstellar",
            "imdbRating": "8.7",
            "imdbVotes": "2,100,000",
            "Metascore": "74",
            "Runtime": "169 min",
            "Rated": "PG-13"
        }
        mock_res.raise_for_status = MagicMock()
        mock_get.return_value = mock_res

        client = TMDbClient(api_key="mock_tmdb", omdb_api_key="mock_omdb")
        details = client.fetch_live_imdb_details("tt0816692")

        self.assertIsNotNone(details)
        self.assertEqual(details["live_imdb_rating"], 8.7)
        self.assertEqual(details["imdb_votes"], "2,100,000")
        self.assertEqual(details["runtime"], "169 min")

    @patch("requests.get")
    def test_external_imdb_id_lookup(self, mock_get):
        mock_res = MagicMock()
        mock_res.json.return_value = {
            "id": 157336,
            "imdb_id": "tt0816692"
        }
        mock_res.raise_for_status = MagicMock()
        mock_get.return_value = mock_res

        client = TMDbClient(api_key="mock_tmdb")
        imdb_id = client.get_imdb_external_id(157336)
        self.assertEqual(imdb_id, "tt0816692")

    @patch.object(TMDbClient, "_get")
    @patch.object(TMDbClient, "get_watch_providers_for_movie")
    @patch.object(TMDbClient, "get_imdb_external_id")
    @patch.object(TMDbClient, "fetch_live_imdb_details")
    def test_multi_slice_candidate_discovery(
        self,
        mock_fetch_imdb,
        mock_get_imdb_id,
        mock_get_providers,
        mock_get_tmdb
    ):
        mock_get_tmdb.return_value = {
            "results": [
                {
                    "id": 1001,
                    "title": "High Rated Film",
                    "vote_average": 7.8,
                    "vote_count": 2500,
                    "genre_ids": [18, 53],
                    "release_date": "2018-05-10"
                },
                {
                    "id": 1002,
                    "title": "Low Rated Film",
                    "vote_average": 6.8,
                    "vote_count": 1200,
                    "genre_ids": [28],
                    "release_date": "2020-01-01"
                }
            ]
        }
        mock_get_providers.return_value = ["Netflix", "Amazon Prime Video"]
        mock_get_imdb_id.return_value = "tt1001"
        mock_fetch_imdb.return_value = {
            "live_imdb_rating": 8.1,
            "imdb_votes": "350,000",
            "runtime": "118 min"
        }

        client = TMDbClient(api_key="mock_tmdb", omdb_api_key="mock_omdb", min_rating=7.5)
        candidates = client.fetch_candidate_movies(target_count=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], 1001)
        self.assertEqual(candidates[0]["rating"], 8.1)
        self.assertEqual(candidates[0]["rating_source"], "Live IMDb")
        self.assertEqual(candidates[0]["runtime"], "118 min")


if __name__ == "__main__":
    unittest.main()
