"""
Core Movie Recommendation Agent using Google Gemini and SQLite Memory.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from db import MovieDatabase
from tmdb_client import TMDbClient


class MovieRecommendation(BaseModel):
    movie_id: int = Field(description="The ID of the movie matching TMDb candidate list")
    title: str = Field(description="Title of the movie")
    release_year: str = Field(description="Release year of the movie")
    rating: float = Field(description="IMDb/TMDb rating (>= 7.5)")
    streaming_providers: List[str] = Field(description="List of base subscription platforms streaming the movie")
    genres: List[str] = Field(description="List of genres")
    summary: str = Field(
        description="A compelling 1-paragraph summary (3-4 sentences) explaining the plot premise and why this movie is recommended based on the user's taste profile, with no spoilers."
    )


class FridayRecommendationResponse(BaseModel):
    thought_process: str = Field(description="Brief reasoning on why these 3 movies were selected based on the user's taste profile and past feedback")
    recommendations: List[MovieRecommendation] = Field(
        description="List of exactly 3 distinct, high-rated movie recommendations available on base subscriptions",
        min_length=3,
        max_length=3
    )


class MovieAgent:
    def __init__(self, db: Optional[MovieDatabase] = None, tmdb: Optional[TMDbClient] = None, gemini_api_key: Optional[str] = None):
        self.db = db or MovieDatabase()
        self.tmdb = tmdb or TMDbClient()
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing. Set it in your environment or .env file.")
        
        self.client = genai.Client(api_key=self.api_key)

    def select_friday_recommendations(self) -> FridayRecommendationResponse:
        """
        Main agent workflow:
        1. Query candidate pool from TMDb (Rating >= 7.5, Base Subscription Streaming)
        2. Filter out already recommended/watched movies
        3. Load user's taste profile & recent feedback history from SQLite
        4. Use Gemini with structured output to curate top 3 movies with 1-paragraph summaries
        5. Save recommendations to memory
        """
        # 1. Fetch fresh candidates
        candidates = self.tmdb.fetch_candidate_movies(page_limit=4)
        if not candidates:
            raise RuntimeError("No candidate movies found meeting criteria (Rating >= 7.5 on base subscriptions).")

        # 2. Filter previously recommended
        previous_ids = set(self.db.get_previously_recommended_ids())
        unseen_candidates = [c for c in candidates if c["id"] not in previous_ids]
        
        # If candidate pool is too small, fallback to all candidates that weren't disliked
        if len(unseen_candidates) < 3:
            unseen_candidates = candidates

        # 3. Load user memory
        profile = self.db.get_user_profile()
        history = self.db.get_user_history(limit=15)

        # 4. Construct prompt for Gemini
        system_instruction = (
            "You are an expert personal film curator. Every Friday, you recommend exactly 3 exceptional movies "
            "rated 7.5 or higher that are available on the user's specific base subscription streaming platforms "
            "(Apple TV+, Netflix, Peacock, and Amazon Prime Video) without additional rental/purchase fees. "
            "You personalize recommendations by learning from the user's taste profile and past reactions (liked, disliked, selected). "
            "For each movie, provide an engaging, spoiler-free 1-paragraph summary (3-4 sentences) that highlights the core premise "
            "and explains why they will enjoy it."
        )

        user_prompt = f"""
### User Profile & Preferences:
- **Taste Summary**: {profile.get('taste_summary', 'Diverse tastes, prefers high-quality storytelling')}
- **Favorite Genres**: {profile.get('favorite_genres', 'Any high rated')}
- **Disliked Tropes/Genres**: {profile.get('disliked_genres', 'None specified')}

### Past Feedback & Watch History:
{json.dumps(history, indent=2, default=str) if history else "No previous feedback yet (First run)."}

### Candidate Movies Available This Week (All rated >= 7.5 & in base subscription):
{json.dumps(unseen_candidates[:25], indent=2)}

### Task:
Select the 3 best, most diverse, and exciting movies from the candidate list for this Friday evening.
Ensure you strictly adhere to the candidate's exact ID, title, rating, streaming providers, and genres.
Write a custom 1-paragraph summary for each recommendation.
"""

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        response = self.client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=FridayRecommendationResponse,
                temperature=0.7
            )
        )

        result: FridayRecommendationResponse = response.parsed

        # 5. Save to database
        for rec in result.recommendations:
            movie_dict = {
                "id": rec.movie_id,
                "title": rec.title,
                "release_year": rec.release_year,
                "rating": rec.rating,
                "genres": rec.genres,
                "streaming_providers": rec.streaming_providers
            }
            self.db.record_recommendation(movie_dict, rec.summary)

        return result
