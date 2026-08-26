"""
Interactive Telegram Bot Daemon for on-demand movie recommendations and chat.
Run this script locally or host it on a free cloud server (e.g. Render, Railway, Fly.io)
to interact with @bala_film_bot 24/7.
"""

import os
import sys
import time
import json
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from db import MovieDatabase
from agent import MovieAgent
from notifier import format_telegram_html, send_telegram_recommendations
from feedback_handler import handle_telegram_callback, refine_taste_profile
from google import genai
from google.genai import types

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def send_message(chat_id: str, text: str, parse_mode: str = "HTML", reply_markup: Optional[Dict[str, Any]] = None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Bot] Error sending message: {e}")


def handle_recommend_command(chat_id: str, db: MovieDatabase):
    send_message(chat_id, "🍿 <i>Curating 3 top-rated movies for tonight using Gemini & TMDb...</i>")
    try:
        agent = MovieAgent(db=db)
        response = agent.select_friday_recommendations()
        send_telegram_recommendations(response, bot_token=BOT_TOKEN, chat_id=chat_id)
    except Exception as e:
        send_message(chat_id, f"❌ <b>Error generating recommendations:</b>\n<code>{e}</code>")


def handle_history_command(chat_id: str, db: MovieDatabase):
    history = db.get_user_history(limit=8)
    if not history:
        send_message(chat_id, "📜 <i>No recommendations recorded yet. Send /recommend to get started!</i>")
        return

    lines = ["📜 <b>Recent Recommendations History:</b>\n"]
    for item in history:
        status_emoji = {
            "recommended": "⏳",
            "selected": "🍿",
            "liked": "👍",
            "disliked": "👎",
            "skipped": "⏭️"
        }.get(item["status"], "•")
        lines.append(f"{status_emoji} <b>{item['title']}</b> ({item['release_year']}) ⭐ {item['rating']}/10")
        lines.append(f"   <i>Status:</i> {item['status'].upper()} | <i>Streaming:</i> {item['providers']}")
        if item.get("user_notes"):
            lines.append(f"   <i>Notes:</i> {item['user_notes']}")
        lines.append("")

    send_message(chat_id, "\n".join(lines))


def handle_profile_command(chat_id: str, db: MovieDatabase):
    profile = db.get_user_profile()
    lines = [
        "🧠 <b>Your AI Taste Profile:</b>\n",
        f"📌 <b>Taste Summary:</b>\n<i>{profile.get('taste_summary')}</i>\n",
        f"❤️ <b>Favorite Genres:</b> {profile.get('favorite_genres')}",
        f"🚫 <b>Disliked Tropes:</b> {profile.get('disliked_genres')}",
        f"🕒 <b>Last Refined:</b> {profile.get('updated_at')}"
    ]
    send_message(chat_id, "\n".join(lines))


def handle_conversational_chat(chat_id: str, user_text: str, db: MovieDatabase):
    """Answers custom movie questions and chats with user using Gemini."""
    if not GEMINI_API_KEY:
        send_message(chat_id, "❌ GEMINI_API_KEY is not configured.")
        return

    profile = db.get_user_profile()
    history = db.get_user_history(limit=10)

    system_instruction = (
        "You are an engaging, knowledgeable personal AI film concierge for Telegram. "
        "You know the user's movie taste, their watch history, and their streaming subscriptions (Netflix, Amazon Prime Video, Apple TV+, Peacock, etc.). "
        "Help them find movies, discuss plots (avoiding major spoilers unless asked), answer trivia, or analyze their taste. "
        "Format your responses using clean Telegram HTML (<b>bold</b>, <i>italic</i>, etc.). Keep responses punchy and fun."
    )

    context_prompt = f"""
User Profile:
- Taste Summary: {profile.get('taste_summary')}
- Favorite Genres: {profile.get('favorite_genres')}
- Disliked Tropes: {profile.get('disliked_genres')}

Recent Movie History:
{json.dumps(history, default=str)}

User Message:
{user_text}
"""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=context_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )
        send_message(chat_id, response.text)
    except Exception as e:
        send_message(chat_id, f"❌ Error: {e}")


def run_telegram_bot():
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    db = MovieDatabase()
    print("🤖 Telegram Movie Agent Bot is running... Press Ctrl+C to stop.")
    offset = None

    while True:
        try:
            params = {"timeout": 20, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            res = requests.get(url, params=params, timeout=25)
            data = res.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                # Handle button clicks
                if "callback_query" in update:
                    handle_telegram_callback(update["callback_query"], db, BOT_TOKEN)
                    continue

                # Handle text messages
                if "message" in update:
                    msg = update["message"]
                    chat_id = str(msg.get("chat", {}).get("id"))
                    text = msg.get("text", "").strip()

                    if not text:
                        continue

                    # Security check: optional match with configured chat ID if set
                    if ALLOWED_CHAT_ID and chat_id != str(ALLOWED_CHAT_ID):
                        send_message(chat_id, "⛔ Unauthorized access.")
                        continue

                    if text.startswith("/start") or text.startswith("/help"):
                        help_text = (
                            "🍿 <b>Welcome to Your Personal Movie Agent!</b> 🎬\n\n"
                            "Here is what you can do:\n"
                            "• <b>/recommend</b> or <b>/tonight</b> — Get 3 fresh movie recommendations right now\n"
                            "• <b>/history</b> — View your past recommended films and reactions\n"
                            "• <b>/profile</b> — View your learned AI taste profile\n"
                            "• 💬 <i>Or just chat with me normally! Ask for recommendations, actors, trivia, or film advice.</i>"
                        )
                        send_message(chat_id, help_text)

                    elif text in ["/recommend", "/tonight", "/movies"]:
                        handle_recommend_command(chat_id, db)

                    elif text in ["/history"]:
                        handle_history_command(chat_id, db)

                    elif text in ["/profile", "/taste"]:
                        handle_profile_command(chat_id, db)

                    else:
                        # Conversational chat with Gemini
                        handle_conversational_chat(chat_id, text, db)

        except requests.exceptions.RequestException:
            time.sleep(2)
        except Exception as e:
            print(f"[Bot Error] {e}")
            time.sleep(2)


if __name__ == "__main__":
    run_telegram_bot()
