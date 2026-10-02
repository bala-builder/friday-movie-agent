"""
Core Movie Recommendation Agent using Google Gemini, Jev System 1 Preferences, and SQLite Memory.
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
    movie_id: int = Field(description="The ID of the movie matching candidate list")
    title: str = Field(description="Title of the movie")
    release_year: str = Field(description="Release year of the movie")
    rating: float = Field(description="Live IMDb or TMDb rating (>= 7.5)")
    rating_source: str = Field(default="Live IMDb", description="Rating source (Live IMDb via OMDb or TMDb)")
    imdb_votes: str = Field(default="", description="Live IMDb vote count")
    runtime: str = Field(default="", description="Runtime duration (e.g. '116 min')")
    streaming_providers: List[str] = Field(description="List of base subscription platforms streaming the movie")
    genres: List[str] = Field(description="List of genres")
    summary: str = Field(
        description="A compelling 1-paragraph summary (3-4 sentences) explaining the plot premise and why this movie is recommended based on the user's taste profile, with no spoilers."
    )


class FridayRecommendationResponse(BaseModel):
    thought_process: str = Field(description="Brief reasoning on why these 3 movies were selected based on the user's taste profile, Jev preferences, and past feedback")
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
        1. Query candidate pool from TMDb (Rating >= 7.5, Base Subscription Streaming, Live IMDb via OMDb)
        2. Filter out already recommended/watched movies (Strict anti-repetition)
        3. Load user's taste profile, Jev preference signals & feedback history from SQLite
        4. Use Gemini with structured output to curate top 3 movies with 1-paragraph summaries
        5. Save recommendations to memory
        """
        # 1. Fetch diverse candidates across multi-slice discovery
        candidates = self.tmdb.fetch_candidate_movies(target_count=50)
        if not candidates:
            raise RuntimeError("No candidate movies found meeting criteria (Rating >= 7.5 on base subscriptions).")

        # 2. Strict anti-repetition: Exclude all movies ever recommended or interacted with
        previous_ids = set(self.db.get_previously_recommended_ids())
        unseen_candidates = [c for c in candidates if c["id"] not in previous_ids]
        
        # If pool of unseen candidates is still small, fetch an even wider slice
        if len(unseen_candidates) < 3:
            more_candidates = self.tmdb.fetch_candidate_movies(target_count=100)
            unseen_candidates = [c for c in more_candidates if c["id"] not in previous_ids]

        # Safety guard: only in the extreme case where all discovered movies are exhausted
        if not unseen_candidates:
            raise RuntimeError("All available candidates have already been recommended! Please add new providers or reset history.")

        # 3. Load user memory and Jev System 1 preference signals
        profile = self.db.get_user_profile()
        history = self.db.get_user_history(limit=15)

        # 4. Construct prompt for Gemini
        system_instruction = (
            "You are an expert personal film curator. Every Friday, you recommend exactly 3 exceptional movies "
            "rated 7.5 or higher that are available on base subscription streaming platforms "
            "(Apple TV+, Netflix, Peacock, and Amazon Prime Video) without additional rental/purchase fees. "
            "You strictly honor the user's Jev-extracted preferences: preferred pacing, preferred tone, and genres to avoid. "
            "NEVER repeat a movie from past recommendations. "
            "For each movie, provide an engaging, spoiler-free 1-paragraph summary (3-4 sentences) that highlights the core premise "
            "and explains why they will enjoy it."
        )

        user_prompt = f"""
### User Profile & Jev System 1 Preference Signals:
- **Taste Summary**: {profile.get('taste_summary', 'Diverse tastes, prefers high-quality storytelling')}
- **Preferred Pacing**: {profile.get('preferred_pacing', 'moderate')}
- **Preferred Tone**: {profile.get('preferred_tone', 'cerebral_thoughtprovoking')}
- **Avoid Genres/Tropes**: {profile.get('avoid_genres', 'none')}
- **Favorite Genres**: {profile.get('favorite_genres', 'Any high rated')}

### Past Feedback & Watch History (DO NOT REPEAT ANY OF THESE):
{json.dumps([{'id': h['movie_id'], 'title': h['title'], 'status': h['status'], 'pacing': h.get('pacing_pref'), 'critique': h.get('feedback_text')} for h in history], indent=2, default=str) if history else "No previous feedback yet (First run)."}

### Fresh Candidate Movies Available This Week (All rated >= 7.5 & in base subscription):
{json.dumps(unseen_candidates[:30], indent=2)}

### Task:
Select the 3 best, most diverse, and exciting movies from the fresh candidate list for this Friday evening.
Ensure you strictly adhere to the candidate's exact ID, title, rating, rating_source, imdb_votes, runtime, streaming providers, and genres.
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
