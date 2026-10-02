"""
Notification module for delivering Friday movie recommendations via Telegram or Terminal.
"""

import os
import requests
from typing import List, Optional
from agent import FridayRecommendationResponse, MovieRecommendation


def format_markdown(response: FridayRecommendationResponse) -> str:
    """Formats recommendations into clean Markdown text."""
    lines = [
        "🍿 *Your Friday Movie Night Lineup* 🎬\n",
        f"_{response.thought_process}_\n",
        "―" * 20
    ]

    for i, rec in enumerate(response.recommendations, 1):
        providers_str = ", ".join(rec.streaming_providers) if rec.streaming_providers else "Base Subscription"
        genres_str = ", ".join(rec.genres)
        rating_detail = f"⭐ *{rec.rating}/10*"
        if rec.rating_source:
            votes_str = f" ({rec.imdb_votes} votes)" if rec.imdb_votes else ""
            rating_detail += f" _[{rec.rating_source}{votes_str}]_"
        runtime_str = f" • ⏱️ {rec.runtime}" if rec.runtime and rec.runtime != "N/A" else ""
        
        lines.append(f"\n*{i}. {rec.title}* ({rec.release_year}){runtime_str} {rating_detail}")
        lines.append(f"📺 *Available on:* {providers_str} _(Included in base subscription)_")
        lines.append(f"🏷️ *Genres:* {genres_str}")
        lines.append(f"📖 *Summary:* {rec.summary}\n")

    lines.append("―" * 20)
    lines.append("💡 _Reply with your thoughts/critique or tap a button to train the Jev System 1 model!_")
    return "\n".join(lines)


def format_telegram_html(response: FridayRecommendationResponse) -> str:
    """Formats recommendations into rich HTML for Telegram."""
    lines = [
        "🍿 <b>Your Friday Movie Night Lineup</b> 🎬\n",
        f"<i>{response.thought_process}</i>\n",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    for i, rec in enumerate(response.recommendations, 1):
        providers_str = ", ".join(rec.streaming_providers) if rec.streaming_providers else "Base Subscription"
        genres_str = ", ".join(rec.genres)
        rating_detail = f"⭐ <b>{rec.rating}/10</b>"
        if rec.rating_source:
            votes_str = f" ({rec.imdb_votes} votes)" if rec.imdb_votes else ""
            rating_detail += f" <i>[{rec.rating_source}{votes_str}]</i>"
        runtime_str = f" • ⏱️ {rec.runtime}" if rec.runtime and rec.runtime != "N/A" else ""
        
        lines.append(f"\n<b>{i}. {rec.title}</b> ({rec.release_year}){runtime_str} {rating_detail}")
        lines.append(f"📺 <b>Streaming:</b> {providers_str} <i>(Included with base subscription)</i>")
        lines.append(f"🏷️ <b>Genres:</b> {genres_str}")
        lines.append(f"📖 {rec.summary}\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Reply with text critique or tap a button below to train your Jev taste model!</i>")
    return "\n".join(lines)


def send_telegram_recommendations(
    response: FridayRecommendationResponse,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None
) -> bool:
    """
    Sends recommendations to a Telegram Chat with inline action buttons for 1-click feedback.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    cid = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not cid:
        print("\n[Notifier] No Telegram Bot Token or Chat ID configured. Displaying in terminal only.")
        return False

    text = format_telegram_html(response)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Build inline keyboard buttons for each movie
    inline_keyboard = []
    for rec in response.recommendations:
        movie_title_short = rec.title[:18] + ".." if len(rec.title) > 20 else rec.title
        inline_keyboard.append([
            {
                "text": f"🍿 Watch '{movie_title_short}'",
                "callback_data": f"select:{rec.movie_id}"
            },
            {
                "text": "👍 Loved",
                "callback_data": f"liked:{rec.movie_id}"
            },
            {
                "text": "👎 Skip",
                "callback_data": f"skip:{rec.movie_id}"
            }
        ])

    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": inline_keyboard
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("[Notifier] Successfully sent Friday recommendations to Telegram!")
        return True
    except Exception as e:
        print(f"[Notifier] Failed to send Telegram message: {e}")
        return False
