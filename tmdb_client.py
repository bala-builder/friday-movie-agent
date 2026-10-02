"""
TMDb & OMDb API client for fetching high-rated movies available on base subscription streaming platforms.
Supports live authentic IMDb ratings via OMDb and multi-slice discovery to prevent recommendation repetition.
"""

import os
import random
import requests
from typing import List, Dict, Any, Optional

# Allowed base subscription provider IDs in TMDb
KNOWN_PROVIDERS = {
    8: "Netflix",
    9: "Amazon Prime Video",
    350: "Apple TV+",
    386: "Peacock"
}

GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}


class TMDbClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        omdb_api_key: Optional[str] = None,
        region: str = "US",
        min_rating: float = 7.5,
        min_vote_count: int = 500,
        provider_ids: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("TMDB_API_KEY")
        if not self.api_key:
            raise ValueError("TMDb API key is missing. Set TMDB_API_KEY in your environment or .env file.")
        
        self.omdb_api_key = omdb_api_key or os.getenv("OMDB_API_KEY")
        self.base_url = "https://api.themoviedb.org/3"
        self.region = region or os.getenv("WATCH_REGION", "US")
        self.min_rating = float(os.getenv("MIN_RATING", min_rating))
        self.min_vote_count = int(os.getenv("MIN_VOTE_COUNT", min_vote_count))
        # Default: Netflix (8), Amazon Prime (9), Apple TV+ (350), Peacock (386)
        self.provider_ids = provider_ids or os.getenv("DEFAULT_WATCH_PROVIDERS", "8|9|350|386")

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params["api_key"] = self.api_key
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_watch_providers_for_movie(self, movie_id: int) -> List[str]:
        """
        Retrieves streaming platforms where the movie is available strictly via BASE subscription ('flatrate').
        Excludes rental ('rent'), digital purchase ('buy'), or pay-per-view.
        """
        try:
            data = self._get(f"/movie/{movie_id}/watch/providers", {})
            results = data.get("results", {})
            region_data = results.get(self.region, {})
            
            flatrate_providers = region_data.get("flatrate", [])
            active_providers = []
            allowed_provider_ids = set(int(p) for p in self.provider_ids.split("|") if p.isdigit())

            for provider in flatrate_providers:
                pid = provider.get("provider_id")
                pname = provider.get("provider_name")
                
                if pid in allowed_provider_ids:
                    clean_name = KNOWN_PROVIDERS.get(pid, pname)
                    if clean_name not in active_providers:
                        active_providers.append(clean_name)

            return active_providers
        except Exception as e:
            print(f"Warning: Could not fetch watch providers for movie {movie_id}: {e}")
            return []

    def get_imdb_external_id(self, movie_id: int) -> Optional[str]:
        """Fetches the official IMDb ID (e.g., 'tt0137523') for a movie from TMDb."""
        try:
            data = self._get(f"/movie/{movie_id}/external_ids", {})
            return data.get("imdb_id")
        except Exception:
            return None

    def fetch_live_imdb_details(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """
        Queries OMDb API for the real-time, authentic IMDb rating, vote count, Metascore, and runtime.
        """
        if not self.omdb_api_key or not imdb_id:
            return None

        try:
            url = "https://www.omdbapi.com/"
            params = {
                "apikey": self.omdb_api_key,
                "i": imdb_id
            }
            res = requests.get(url, params=params, timeout=8)
            res.raise_for_status()
            data = res.json()
            if data.get("Response") == "True":
                imdb_rating_str = data.get("imdbRating", "0.0")
                try:
                    rating = float(imdb_rating_str)
                except ValueError:
                    rating = 0.0

                return {
                    "live_imdb_rating": rating,
                    "imdb_votes": data.get("imdbVotes", "N/A"),
                    "metascore": data.get("Metascore", "N/A"),
                    "runtime": data.get("Runtime", "N/A"),
                    "rated": data.get("Rated", "N/A")
                }
        except Exception as e:
            print(f"Warning: OMDb lookup failed for {imdb_id}: {e}")
        return None

    def fetch_candidate_movies(self, target_count: int = 40, page_limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Performs multi-slice discovery across decades, popularity, and critically acclaimed tiers
        to avoid recommendation repetition and provide a diverse candidate pool.
        """
        candidates_map = {}
        
        # Slices to ensure diverse, non-repeating discoveries
        slices = [
            # Slice 1: Acclaimed modern releases (2015-present)
            {
                "sort_by": "vote_count.desc",
                "primary_release_date.gte": "2015-01-01",
                "page": random.choice([1, 2, 3])
            },
            # Slice 2: 2000s & 2010s modern classics
            {
                "sort_by": "vote_count.desc",
                "primary_release_date.gte": "2000-01-01",
                "primary_release_date.lte": "2014-12-31",
                "page": random.choice([1, 2, 3])
            },
            # Slice 3: Trending high-rated popular films
            {
                "sort_by": "popularity.desc",
                "page": random.choice([1, 2, 3, 4])
            },
            # Slice 4: All-time top-rated masterpieces
            {
                "sort_by": "vote_average.desc",
                "vote_count.gte": 1500,
                "page": random.choice([1, 2, 3])
            }
        ]

        for s in slices:
            params = {
                "include_adult": "false",
                "include_video": "false",
                "language": "en-US",
                "vote_average.gte": self.min_rating,
                "vote_count.gte": self.min_vote_count,
                "watch_region": self.region,
                "with_watch_providers": self.provider_ids,
                "with_watch_monetization_types": "flatrate",
                **s
            }

            try:
                data = self._get("/discover/movie", params)
                results = data.get("results", [])
            except Exception as e:
                print(f"Warning: Failed to fetch TMDb slice {s}: {e}")
                continue

            for item in results:
                movie_id = item["id"]
                if movie_id in candidates_map:
                    continue

                # Preliminary rating check on TMDb score
                tmdb_rating = round(item.get("vote_average", 0.0), 1)

                # Check base streaming availability strictly
                providers = self.get_watch_providers_for_movie(movie_id)
                if not providers:
                    continue

                # Fetch authentic IMDb ID and real-time IMDb rating via OMDb
                imdb_id = self.get_imdb_external_id(movie_id)
                live_imdb = self.fetch_live_imdb_details(imdb_id) if imdb_id else None

                if live_imdb and live_imdb.get("live_imdb_rating"):
                    effective_rating = live_imdb["live_imdb_rating"]
                    rating_source = "Live IMDb"
                    runtime = live_imdb.get("runtime", "N/A")
                    imdb_votes = live_imdb.get("imdb_votes", str(item.get("vote_count", "")))
                else:
                    effective_rating = tmdb_rating
                    rating_source = "TMDb (OMDb unset)"
                    runtime = "N/A"
                    imdb_votes = str(item.get("vote_count", ""))

                # Strict rating gate: Must be >= min_rating on the authentic rating
                if effective_rating < self.min_rating:
                    continue

                genre_ids = item.get("genre_ids", [])
                genres = [GENRE_MAP.get(gid, "Unknown") for gid in genre_ids if gid in GENRE_MAP]
                release_date = item.get("release_date", "")
                release_year = release_date.split("-")[0] if release_date else "Unknown"

                candidates_map[movie_id] = {
                    "id": movie_id,
                    "imdb_id": imdb_id,
                    "title": item.get("title"),
                    "original_title": item.get("original_title"),
                    "overview": item.get("overview"),
                    "rating": effective_rating,
                    "rating_source": rating_source,
                    "imdb_votes": imdb_votes,
                    "runtime": runtime,
                    "release_year": release_year,
                    "genres": genres,
                    "streaming_providers": providers,
                    "poster_path": f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get("poster_path") else None
                }

                if len(candidates_map) >= target_count:
                    break

            if len(candidates_map) >= target_count:
                break

        return list(candidates_map.values())
