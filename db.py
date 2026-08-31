"""
Database module for the Movie Recommendation Agent.
Handles persistent memory for recommended movies, user feedback, and evolving taste profile.
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "movie_memory.db")


class MovieDatabase:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for tracking all recommendations and user interactions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS movie_history (
                    movie_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    release_year TEXT,
                    rating REAL,
                    genres TEXT,
                    providers TEXT,
                    summary TEXT,
                    status TEXT DEFAULT 'recommended', -- 'recommended', 'selected', 'liked', 'disliked', 'skipped'
                    recommended_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    feedback_date TIMESTAMP,
                    user_notes TEXT
                )
            """)

            # Table for storing user taste profile & evolving LLM notes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    taste_summary TEXT,
                    favorite_genres TEXT,
                    disliked_genres TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default profile if empty
            cursor.execute("SELECT COUNT(*) as cnt FROM user_profile WHERE id = 1")
            row = cursor.fetchone()
            if row["cnt"] == 0:
                cursor.execute("""
                    INSERT INTO user_profile (id, taste_summary, favorite_genres, disliked_genres)
                    VALUES (
                        1,
                        'Enjoys well-crafted movies rated 7.5+ with strong storytelling, high rewatchability, and engaging characters across diverse genres.',
                        'Drama, Sci-Fi, Thriller, Mystery, Crime',
                        'Excessive gore, low-budget slapstick'
                    )
                """)
            conn.commit()

    def get_previously_recommended_ids(self, cooldown_days: int = 14) -> List[int]:
        """
        Returns list of movie IDs to exclude from new recommendations:
        - All movies with explicit user feedback (selected, liked, disliked, skipped).
        - Movies recommended recently within cooldown_days that received no feedback yet.
        Movies recommended with no feedback older than cooldown_days are eligible again.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT movie_id FROM movie_history
                WHERE status IN ('selected', 'liked', 'disliked', 'skipped')
                   OR (status = 'recommended' AND recommended_date >= datetime('now', ?))
            """, (f"-{cooldown_days} days",))
            rows = cursor.fetchall()
            return [row["movie_id"] for row in rows]

    def record_recommendation(self, movie: Dict[str, Any], summary: str):
        """Records a new movie recommendation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            genres_str = ", ".join(movie.get("genres", [])) if isinstance(movie.get("genres"), list) else str(movie.get("genres", ""))
            providers_str = ", ".join(movie.get("streaming_providers", [])) if isinstance(movie.get("streaming_providers"), list) else str(movie.get("streaming_providers", ""))
            
            cursor.execute("""
                INSERT OR REPLACE INTO movie_history 
                (movie_id, title, release_year, rating, genres, providers, summary, status, recommended_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'recommended', CURRENT_TIMESTAMP)
            """, (
                movie["id"],
                movie["title"],
                str(movie.get("release_year", "")),
                float(movie.get("rating", 0.0)),
                genres_str,
                providers_str,
                summary
            ))
            conn.commit()

    def record_feedback(self, movie_id: int, status: str, user_notes: Optional[str] = None):
        """
        Updates the status of a recommended movie.
        status can be: 'selected', 'liked', 'disliked', 'skipped'
        """
        valid_statuses = {"recommended", "selected", "liked", "disliked", "skipped"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE movie_history
                SET status = ?, feedback_date = CURRENT_TIMESTAMP, user_notes = COALESCE(?, user_notes)
                WHERE movie_id = ?
            """, (status, user_notes, movie_id))
            conn.commit()

    def get_user_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent recommendation history and user reactions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT movie_id, title, release_year, rating, genres, providers, summary, status, recommended_date, feedback_date, user_notes
                FROM movie_history
                ORDER BY recommended_date DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_user_profile(self) -> Dict[str, Any]:
        """Retrieves current user taste profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT taste_summary, favorite_genres, disliked_genres, updated_at FROM user_profile WHERE id = 1")
            row = cursor.fetchone()
            return dict(row) if row else {}

    def update_taste_profile(self, taste_summary: str, favorite_genres: Optional[str] = None, disliked_genres: Optional[str] = None):
        """Updates the learned user taste profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_profile
                SET taste_summary = ?,
                    favorite_genres = COALESCE(?, favorite_genres),
                    disliked_genres = COALESCE(?, disliked_genres),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (taste_summary, favorite_genres, disliked_genres))
            conn.commit()
