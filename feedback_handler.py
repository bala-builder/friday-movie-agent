"""
Feedback Handler module with Jev (TypeSafe AI) System 1 Decision Layer.
Processes user feedback (Telegram button clicks, text messages, or CLI input)
and refines the user's taste profile using Jev structured signals + Gemini synthesis.
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

from db import MovieDatabase
from jev_client import JevClient, ParsedFeedback


def process_user_critique(
    movie_id: int,
    feedback_text: str,
    db: MovieDatabase,
    status: Optional[str] = None,
    jev_client: Optional[JevClient] = None
) -> ParsedFeedback:
    """
    Parses a user's natural language critique of a movie using Jev System 1,
    extracts typed preferences, records rich feedback in SQLite, and updates taste profile.
    """
    jev = jev_client or JevClient()
    
    # Get movie title for context
    history = db.get_user_history(limit=50)
    movie_title = "Unknown Movie"
    for item in history:
        if item["movie_id"] == movie_id:
            movie_title = f"{item['title']} ({item.get('release_year', '')})"
            break

    # 1. Parse feedback via Jev System 1
    parsed: ParsedFeedback = jev.parse_user_feedback(feedback_text, movie_context=movie_title)

    # 2. Determine status from Jev sentiment score if not explicitly set
    if not status:
        if parsed.sentiment_score >= 4.0:
            status = "liked"
        elif parsed.sentiment_score <= 2.0:
            status = "disliked"
        else:
            status = "selected"

    # 3. Store rich multi-dimensional feedback
    db.record_rich_feedback(
        movie_id=movie_id,
        status=status,
        feedback_text=feedback_text,
        sentiment_score=parsed.sentiment_score,
        pacing_pref=parsed.pacing_preference,
        tone_pref=parsed.tone_preference,
        user_notes=f"Jev Rating: {parsed.sentiment_score}/5 | Pacing: {parsed.pacing_preference} | Tone: {parsed.tone_preference}"
    )

    # 4. Update profile with Jev structured signals
    profile = db.get_user_profile()
    new_pacing = parsed.pacing_preference if parsed.pacing_preference != "unspecified" else profile.get("preferred_pacing", "moderate")
    new_tone = parsed.tone_preference if parsed.tone_preference != "unspecified" else profile.get("preferred_tone", "cerebral_thoughtprovoking")
    
    avoid_genre = profile.get("avoid_genres", "none")
    if parsed.disliked_genre != "none":
        if avoid_genre == "none" or not avoid_genre:
            avoid_genre = parsed.disliked_genre
        elif parsed.disliked_genre not in avoid_genre:
            avoid_genre = f"{avoid_genre}, {parsed.disliked_genre}"

    db.update_taste_profile(
        taste_summary=profile.get("taste_summary", ""),
        preferred_pacing=new_pacing,
        preferred_tone=new_tone,
        avoid_genres=avoid_genre
    )

    # 5. Synthesize evolving narrative taste summary
    refine_taste_profile(db)

    return parsed


def refine_taste_profile(db: MovieDatabase, gemini_api_key: Optional[str] = None):
    """
    Analyzes user feedback and watch history to update the narrative taste profile summary.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return

    history = db.get_user_history(limit=25)
    current_profile = db.get_user_profile()

    feedback_items = [h for h in history if h.get("status") in {"selected", "liked", "disliked", "skipped"}]
    if len(feedback_items) < 1:
        return

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an AI taste-profiling assistant. Analyze the user's past movie choices, ratings, and Jev-extracted feedback below:

Current Profile:
{json.dumps(current_profile, indent=2)}

Interaction History & Jev Signals:
{json.dumps(feedback_items, indent=2, default=str)}

Based on what they watched, liked, selected, or critiqued, update their profile with:
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
        print(f"[Feedback] Notice: Taste profile synthesis deferred: {e}")


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
    
    ack_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    ack_text = f"Saved: Marked as {status.capitalize()}!"
    try:
        requests.post(ack_url, json={"callback_query_id": callback_id, "text": ack_text}, timeout=5)
    except Exception as e:
        print(f"[Feedback] Error acknowledging Telegram callback: {e}")

    refine_taste_profile(db)


def poll_telegram_feedback_once(bot_token: Optional[str] = None, db: Optional[MovieDatabase] = None):
    """
    Checks for pending button clicks and text replies from Telegram.
    Can be run as part of the scheduled job or standalone.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    db_instance = db or MovieDatabase()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        res = requests.get(url, params={"timeout": 2, "allowed_updates": ["callback_query", "message"]}, timeout=10)
        updates = res.json().get("result", [])
        
        for update in updates:
            if "callback_query" in update:
                handle_telegram_callback(update["callback_query"], db_instance, token)
            elif "message" in update and "text" in update["message"]:
                # If user replies with text feedback, process the critique on their most recent recommendation
                text = update["message"]["text"]
                if not text.startswith("/"):
                    recent = db_instance.get_user_history(limit=1)
                    if recent:
                        target_id = recent[0]["movie_id"]
                        process_user_critique(target_id, text, db_instance)

            update_id = update["update_id"]
            requests.get(url, params={"offset": update_id + 1})
    except Exception as e:
        print(f"[Feedback] Telegram polling check: {e}")
