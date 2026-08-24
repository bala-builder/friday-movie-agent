"""
Main entry point for the Friday Movie Recommendation Agent.
Run by GitHub Actions or local scheduler every Friday.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from db import MovieDatabase
from tmdb_client import TMDbClient
from agent import MovieAgent
from notifier import send_telegram_recommendations, format_markdown
from feedback_handler import poll_telegram_feedback_once, refine_taste_profile


def run_friday_workflow():
    print("=" * 60)
    print("🎬 Starting Friday Movie Recommendation Agent Workflow...")
    print("=" * 60)

    db = MovieDatabase()

    # Step 1: Check for any pending Telegram feedback from previous weeks
    print("\n[1/4] Checking for recent feedback...")
    poll_telegram_feedback_once(db=db)
    refine_taste_profile(db)

    # Step 2: Initialize TMDb & Agent
    print("\n[2/4] Initializing Agent & Fetching base-subscription movies (Rating >= 7.5)...")
    try:
        agent = MovieAgent(db=db)
    except Exception as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # Step 3: Run selection logic
    print("\n[3/4] Curating top 3 movies and generating 1-paragraph summaries with Gemini...")
    try:
        response = agent.select_friday_recommendations()
    except Exception as e:
        print(f"Error during recommendation generation: {e}")
        sys.exit(1)

    # Step 4: Display and Notify
    print("\n[4/4] Delivering recommendations...")
    markdown_output = format_markdown(response)
    print("\n" + markdown_output + "\n")

    # Send to Telegram if configured
    send_telegram_recommendations(response)
    print("\n✅ Friday workflow completed successfully!")


if __name__ == "__main__":
    run_friday_workflow()
