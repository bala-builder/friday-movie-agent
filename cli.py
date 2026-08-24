"""
Interactive CLI for testing, viewing recommendations, and recording feedback locally.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from db import MovieDatabase
from tmdb_client import TMDbClient
from agent import MovieAgent
from notifier import format_markdown
from feedback_handler import refine_taste_profile


def print_menu():
    print("\n🎬 --- Movie Recommendation Agent CLI ---")
    print("1. 🍿 Run Agent & Get 3 Friday Recommendations")
    print("2. 📋 View Recent Recommendations & History")
    print("3. ⭐ Give Feedback on a Movie (Watched / Liked / Disliked)")
    print("4. 🧠 View & Refine AI Taste Profile")
    print("5. 🚪 Exit")
    print("------------------------------------------")


def handle_run_agent(db: MovieDatabase):
    print("\nCurating 3 top movies (IMDb >= 7.5 on Netflix, Prime, Peacock, Apple TV+)...")
    try:
        agent = MovieAgent(db=db)
        response = agent.select_friday_recommendations()
        print("\n" + format_markdown(response))
    except Exception as e:
        print(f"\n❌ Error: {e}")


def handle_view_history(db: MovieDatabase):
    history = db.get_user_history(limit=20)
    if not history:
        print("\nNo recommendations recorded yet.")
        return

    print("\n📜 --- Recent Recommendations History ---")
    for item in history:
        status_emoji = {
            "recommended": "⏳",
            "selected": "🍿",
            "liked": "👍",
            "disliked": "👎",
            "skipped": "⏭️"
        }.get(item["status"], "•")
        
        print(f"[{item['movie_id']}] {status_emoji} {item['title']} ({item['release_year']}) - ⭐ {item['rating']}/10")
        print(f"    Streaming: {item['providers']} | Status: {item['status'].upper()}")
        if item.get("user_notes"):
            print(f"    Notes: {item['user_notes']}")
        print()


def handle_give_feedback(db: MovieDatabase):
    history = db.get_user_history(limit=10)
    if not history:
        print("\nNo movies to give feedback on. Run recommendations first.")
        return

    print("\nSelect a movie to provide feedback on:")
    for idx, item in enumerate(history, 1):
        print(f"{idx}. {item['title']} (ID: {item['movie_id']}) - Current Status: {item['status']}")

    choice = input("\nEnter number (or 'cancel'): ").strip()
    if choice.lower() == "cancel" or not choice.isdigit():
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(history):
        print("Invalid selection.")
        return

    selected_movie = history[idx]
    print(f"\nSelected: '{selected_movie['title']}'")
    print("What action would you like to record?")
    print("1. 🍿 Watching Tonight (Selected)")
    print("2. 👍 Watched & Loved it")
    print("3. 👎 Watched & Disliked it")
    print("4. ⏭️ Skip / Not Interested")

    act_choice = input("Enter choice (1-4): ").strip()
    status_map = {
        "1": "selected",
        "2": "liked",
        "3": "disliked",
        "4": "skipped"
    }

    status = status_map.get(act_choice)
    if not status:
        print("Invalid choice.")
        return

    notes = input("Any optional notes or thoughts? (Press Enter to skip): ").strip()
    db.record_feedback(movie_id=selected_movie["movie_id"], status=status, user_notes=notes if notes else None)
    print(f"✅ Feedback saved! Movie marked as '{status.upper()}'.")

    # Update taste profile
    print("🧠 Updating AI taste profile based on your feedback...")
    refine_taste_profile(db)


def handle_view_profile(db: MovieDatabase):
    profile = db.get_user_profile()
    print("\n🧠 --- Current AI Taste Profile ---")
    print(f"📌 Taste Summary:\n{profile.get('taste_summary')}\n")
    print(f"❤️ Favorite Genres: {profile.get('favorite_genres')}")
    print(f"🚫 Disliked Tropes: {profile.get('disliked_genres')}")
    print(f"🕒 Last Updated: {profile.get('updated_at')}")

    refine_now = input("\nWould you like to ask Gemini to re-synthesize your taste profile from history? (y/n): ").strip().lower()
    if refine_now == "y":
        refine_taste_profile(db)
        updated = db.get_user_profile()
        print("\n✅ New Taste Summary:")
        print(updated.get("taste_summary"))


def main():
    db = MovieDatabase()
    while True:
        print_menu()
        choice = input("Select an option (1-5): ").strip()
        if choice == "1":
            handle_run_agent(db)
        elif choice == "2":
            handle_view_history(db)
        elif choice == "3":
            handle_give_feedback(db)
        elif choice == "4":
            handle_view_profile(db)
        elif choice == "5":
            print("\nGoodbye! Have a great movie night! 🍿")
            break
        else:
            print("Invalid option. Please choose 1-5.")


if __name__ == "__main__":
    main()
