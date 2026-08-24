"""
TMDb API client for fetching high-rated movies available on base subscription streaming platforms.
"""

import os
import requests
from typing import List, Dict, Any, Optional

# Standard base subscription provider IDs in TMDb
KNOWN_PROVIDERS = {
    8: "Netflix",
    9: "Amazon Prime Video",
    350: "Apple TV+",
    386: "Peacock",
    15: "Hulu",
    337: "Disney+",
    1899: "Max"
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
        region: str = "US",
        min_rating: float = 7.5,
        min_vote_count: int = 500,
        provider_ids: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("TMDB_API_KEY")
        if not self.api_key:
            raise ValueError("TMDb API key is missing. Set TMDB_API_KEY in your environment or .env file.")
        
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
            
            # CRITICAL: We only look at 'flatrate' (subscription included with no additional rental/buy cost)
            flatrate_providers = region_data.get("flatrate", [])
            
            active_providers = []
            allowed_provider_ids = set(int(p) for p in self.provider_ids.split("|") if p.isdigit())

            for provider in flatrate_providers:
                pid = provider.get("provider_id")
                pname = provider.get("provider_name")
                
                # Check if it matches our allowed base subscription providers
                if pid in allowed_provider_ids or pid in KNOWN_PROVIDERS:
                    clean_name = KNOWN_PROVIDERS.get(pid, pname)
                    if clean_name not in active_providers:
                        active_providers.append(clean_name)

            return active_providers
        except Exception as e:
            print(f"Warning: Could not fetch watch providers for movie {movie_id}: {e}")
            return []

    def fetch_candidate_movies(self, page_limit: int = 3) -> List[Dict[str, Any]]:
        """
        Queries TMDb /discover/movie for high-rated movies on base subscription streaming.
        Returns a list of candidate movie objects.
        """
        candidates = []
        
        for page in range(1, page_limit + 1):
            params = {
                "include_adult": "false",
                "include_video": "false",
                "language": "en-US",
                "page": page,
                "sort_by": "popularity.desc",
                "vote_average.gte": self.min_rating,
                "vote_count.gte": self.min_vote_count,
                "watch_region": self.region,
                "with_watch_providers": self.provider_ids,
                # 'flatrate' ensures it is included with the base subscription (no additional rental/purchase fee)
                "with_watch_monetization_types": "flatrate"
            }
            
            data = self._get("/discover/movie", params)
            results = data.get("results", [])
            
            for item in results:
                movie_id = item["id"]
                rating = round(item.get("vote_average", 0.0), 1)
                
                # Double-check rating meets threshold
                if rating < self.min_rating:
                    continue
                
                # Get genre names
                genre_ids = item.get("genre_ids", [])
                genres = [GENRE_MAP.get(gid, "Unknown") for gid in genre_ids if gid in GENRE_MAP]
                
                # Release year
                release_date = item.get("release_date", "")
                release_year = release_date.split("-")[0] if release_date else "Unknown"

                # Verify actual flatrate streaming providers
                providers = self.get_watch_providers_for_movie(movie_id)
                if not providers:
                    # If not currently streaming on our selected base subscription platforms, skip
                    continue
                
                candidates.append({
                    "id": movie_id,
                    "title": item.get("title"),
                    "original_title": item.get("original_title"),
                    "overview": item.get("overview"),
                    "rating": rating,
                    "vote_count": item.get("vote_count"),
                    "release_year": release_year,
                    "genres": genres,
                    "streaming_providers": providers,
                    "poster_path": f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get("poster_path") else None
                })
        
        return candidates
