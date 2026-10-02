"""
FastAPI Webhook Server for Telegram Bot on Google Cloud Run.
Scales to zero when idle and responds instantly to Telegram updates.
"""

import os
import sys
import json
import requests
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from db import MovieDatabase
from agent import MovieAgent
from notifier import send_telegram_recommendations
from feedback_handler import handle_telegram_callback, poll_telegram_feedback_once, refine_taste_profile
from google import genai
from google.genai import types

app = FastAPI(title="Friday Movie Agent Webhook")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

db = MovieDatabase()


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
        print(f"[Webhook] Error sending Telegram message: {e}")


def process_telegram_update(update: Dict[str, Any]):
    """Processes incoming message or button click in background task."""
    try:
        # 1. Handle Inline Button Clicks
        if "callback_query" in update:
            handle_telegram_callback(update["callback_query"], db, BOT_TOKEN)
            return

        # 2. Handle Text Messages
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = msg.get("text", "").strip()

            if not text:
                return

            if ALLOWED_CHAT_ID and chat_id != str(ALLOWED_CHAT_ID):
                send_message(chat_id, "⛔ Unauthorized access.")
                return

            clean_text = text.lower().strip()
            is_recommend_intent = (
                clean_text.startswith("/recommend") or
                clean_text.startswith("/tonight") or
                clean_text.startswith("/movies") or
                "recommend" in clean_text or
                "what to watch" in clean_text or
                "what should i watch" in clean_text or
                "movie pick" in clean_text or
                "suggest a movie" in clean_text or
                "suggest movies" in clean_text or
                "movie tonight" in clean_text or
                "movie suggestions" in clean_text
            )

            if clean_text.startswith("/start") or clean_text.startswith("/help"):
                help_text = (
                    "🍿 <b>Welcome to Your 24/7 Movie Agent on Cloud Run!</b> 🎬\n\n"
                    "Commands & messages you can use anytime:\n"
                    "• <b>/recommend</b> or <b>recommend movies</b> — Curate 3 top-rated movies with live IMDb scores\n"
                    "• <b>/history</b> — View your past recommendations & reactions\n"
                    "• <b>/profile</b> — View your learned AI taste profile\n\n"
                    "💬 <i>Send any critique (e.g., 'Loved the twist, hated the slow pacing') and Jev System 1 will analyze it in real time!</i>"
                )
                send_message(chat_id, help_text)

            elif is_recommend_intent:
                send_message(chat_id, "🍿 <i>Curating 3 top-rated movies with verified live IMDb ratings and base streaming availability...</i>")
                try:
                    agent = MovieAgent(db=db)
                    response = agent.select_friday_recommendations()
                    send_telegram_recommendations(response, bot_token=BOT_TOKEN, chat_id=chat_id)
                except Exception as rec_err:
                    print(f"[Webhook Rec Error] {rec_err}")
                    send_message(chat_id, f"❌ <b>Error curating movies:</b>\n<code>{rec_err}</code>")

            elif clean_text in ["/history"]:
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
                    lines.append(f"{status_emoji} <b>{item['title']}</b> ({item['release_year']}) ⭐ <b>{item['rating']}/10</b> [IMDb]")
                    lines.append(f"   <i>Status:</i> {item['status'].upper()} | <i>Streaming:</i> {item['providers']}")
                    if item.get("user_notes"):
                        lines.append(f"   <i>Notes:</i> {item['user_notes']}")
                    lines.append("")
                send_message(chat_id, "\n".join(lines))

            elif clean_text in ["/profile", "/taste"]:
                profile = db.get_user_profile()
                lines = [
                    "🧠 <b>Your AI Taste Profile:</b>\n",
                    f"📌 <b>Taste Summary:</b>\n<i>{profile.get('taste_summary')}</i>\n",
                    f"❤️ <b>Favorite Genres:</b> {profile.get('favorite_genres')}",
                    f"🚫 <b>Disliked Tropes:</b> {profile.get('disliked_genres')}",
                    f"⚡ <b>Pacing Pref:</b> {profile.get('preferred_pacing', 'moderate')}",
                    f"🎭 <b>Tone Pref:</b> {profile.get('preferred_tone', 'cerebral_thoughtprovoking')}",
                    f"🕒 <b>Last Refined:</b> {profile.get('updated_at')}"
                ]
                send_message(chat_id, "\n".join(lines))

            elif text.startswith("/critique") or any(w in clean_text for w in ["watched", "loved it", "disliked", "hated it", "too slow", "too long", "dragged", "pacing was"]):
                recent = db.get_user_history(limit=1)
                if recent:
                    target_id = recent[0]["movie_id"]
                    try:
                        from feedback_handler import process_user_critique
                        parsed = process_user_critique(target_id, text, db)
                        msg_reply = (
                            f"⚡ <b>Jev System 1 Analysis:</b>\n"
                            f"• <b>Score:</b> {parsed.sentiment_score}/5.0\n"
                            f"• <b>Pacing:</b> {parsed.pacing_preference}\n"
                            f"• <b>Tone:</b> {parsed.tone_preference}\n"
                            f"• <b>Runtime:</b> {parsed.preferred_runtime_category}\n"
                            f"• <b>Disliked:</b> {parsed.disliked_genre}\n\n"
                            f"✅ <i>Critique recorded for <b>{recent[0]['title']}</b>! Taste profile refined.</i>"
                        )
                        send_message(chat_id, msg_reply)
                        return
                    except Exception as jev_err:
                        print(f"[Webhook Jev Error] {jev_err}")

            else:
                # Conversational response via Gemini using rich Jev profile
                try:
                    profile = db.get_user_profile()
                    history = db.get_user_history(limit=10)
                    system_instruction = (
                        "You are an engaging, knowledgeable personal AI film concierge for Telegram. "
                        "You know the user's movie taste, their watch history, and their streaming subscriptions. "
                        "You strictly respect their Jev-extracted preferences: preferred pacing, tone, and genres to avoid. "
                        "IMPORTANT: If recommending or discussing any movies, ALWAYS explicitly cite their IMDb rating (e.g. ⭐ 8.2/10 IMDb) "
                        "and verify they are on base subscription platforms (Netflix, Prime, Apple TV+, Peacock). "
                        "Format your responses with clean Telegram HTML (<b>bold</b>, <i>italic</i>). Keep answers punchy and fun."
                    )
                    context_prompt = f"""
User Profile & Jev Signals:
- Taste Summary: {profile.get('taste_summary')}
- Preferred Pacing: {profile.get('preferred_pacing', 'moderate')}
- Preferred Tone: {profile.get('preferred_tone', 'cerebral_thoughtprovoking')}
- Avoided Genres: {profile.get('avoid_genres', 'none')}
- Favorite Genres: {profile.get('favorite_genres')}

Recent Movie History:
{json.dumps(history, default=str)}

User Message:
{text}
"""
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
                except Exception as chat_err:
                    print(f"[Webhook Chat Error] {chat_err}")
                    send_message(chat_id, f"❌ <b>Error:</b>\n<code>{chat_err}</code>")

    except Exception as e:
        print(f"[Webhook Error] {e}")


@app.get("/")
def root():
    return {"status": "ok", "service": "Friday Movie Agent with Jev System 1 on Cloud Run"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives webhook events from Telegram and processes them asynchronously."""
    update = await request.json()
    background_tasks.add_task(process_telegram_update, update)
    return JSONResponse(content={"ok": True})


@app.api_route("/cron/friday", methods=["GET", "POST"])
def trigger_friday_cron(background_tasks: BackgroundTasks):
    """
    Scheduled Friday trigger invoked by Cloud Scheduler at 5:00 PM EST.
    Runs feedback checks, curates recommendations, and delivers to Telegram.
    """
    def _run_workflow():
        try:
            print("[Cron] Starting Friday scheduled recommendation workflow...")
            poll_telegram_feedback_once(bot_token=BOT_TOKEN, db=db)
            refine_taste_profile(db=db)
            agent = MovieAgent(db=db)
            response = agent.select_friday_recommendations()
            send_telegram_recommendations(response, bot_token=BOT_TOKEN, chat_id=ALLOWED_CHAT_ID)
            print("[Cron] Friday scheduled recommendation workflow completed successfully!")
        except Exception as e:
            print(f"[Cron Error] Failed to execute Friday workflow: {e}")
            if ALLOWED_CHAT_ID:
                send_message(str(ALLOWED_CHAT_ID), f"❌ <b>Friday Cron Error:</b>\n<code>{e}</code>")

    background_tasks.add_task(_run_workflow)
    return {"status": "accepted", "message": "Friday movie curation workflow started"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("webhook:app", host="0.0.0.0", port=port)
