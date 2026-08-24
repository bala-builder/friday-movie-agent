"""
Feedback Handler module.
Processes user feedback (Telegram button clicks or CLI input) and refines the user's taste profile using Gemini.
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

from db import MovieDatabase


def refine_taste_profile(db: MovieDatabase, gemini_api_key: Optional[str] = None):
    """
    Analyzes user feedback and watch history to update the taste profile summary.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Feedback] Skipping profile evolution: GEMINI_API_KEY missing.")
        return

    history = db.get_user_history(limit=25)
    current_profile = db.get_user_profile()

    # If not enough feedback yet, keep current
    feedback_items = [h for h in history if h.get("status") in {"selected", "liked", "disliked", "skipped"}]
    if len(feedback_items) < 2:
        return

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an AI taste-profiling assistant. Analyze the user's past movie choices, ratings, and feedback below:

Current Profile:
{json.dumps(current_profile, indent=2)}

Interaction History:
{json.dumps(feedback_items, indent=2, default=str)}

Based on what they watched, liked, selected, or skipped, update their profile with:
1. An insightful 2-3 sentence summary of their evolving cinematic tastes, preferred pacing, and directors/themes.
2. A comma-separated list of top favorite genres/tropes.
3. A comma-separated list of genres/tropes they tend to avoid or skip.

Respond in JSON format with keys: "taste_summary", "favorite_genres", "disliked_genres".
"""

    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = json.loads(response.text)
        db.update_taste_profile(
            taste_summary=data.get("taste_summary", current_profile.get("taste_summary", "")),
            favorite_genres=data.get("favorite_genres", current_profile.get("favorite_genres", "")),
            disliked_genres=data.get("disliked_genres", current_profile.get("disliked_genres", ""))
        )
        print("[Feedback] User taste profile successfully updated and refined!")
    except Exception as e:
        print(f"[Feedback] Failed to refine taste profile: {e}")


def handle_telegram_callback(callback_query: Dict[str, Any], db: MovieDatabase, bot_token: str):
    """Handles an inline button callback from Telegram."""
    data = callback_query.get("data", "")
    callback_id = callback_query.get("id")

    if ":" not in data:
        return

    action, movie_id_str = data.split(":", 1)
    movie_id = int(movie_id_str)

    status_map = {
        "select": "selected",
        "liked": "liked",
        "skip": "skipped"
    }
    status = status_map.get(action, "selected")
    
    db.record_feedback(movie_id=movie_id, status=status)
    
    # Acknowledge callback in Telegram
    ack_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    ack_text = f"Saved: Marked as {status.capitalize()}!"
    try:
        requests.post(ack_url, json={"callback_query_id": callback_id, "text": ack_text}, timeout=5)
    except Exception as e:
        print(f"[Feedback] Error acknowledging Telegram callback: {e}")

    # Trigger profile refinement
    refine_taste_profile(db)


def poll_telegram_feedback_once(bot_token: Optional[str] = None, db: Optional[MovieDatabase] = None):
    """
    Checks for any pending button clicks from Telegram.
    Can be run as part of the scheduled job or standalone.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    db_instance = db or MovieDatabase()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        res = requests.get(url, params={"timeout": 2, "allowed_updates": ["callback_query"]}, timeout=10)
        updates = res.json().get("result", [])
        
        for update in updates:
            if "callback_query" in update:
                handle_telegram_callback(update["callback_query"], db_instance, token)
                # Confirm update offset to prevent reprocessing
                update_id = update["update_id"]
                requests.get(url, params={"offset": update_id + 1})
    except Exception as e:
        print(f"[Feedback] Telegram polling check: {e}")
