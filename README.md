# 🎬 Friday Movie Recommendation Agent

An intelligent, autonomous film curation agent that runs **every Friday** to deliver **3 top-tier movie recommendations** directly to your phone or terminal.

---

## 🌟 Key Features

1. **⭐ High Quality Guarantee**: Strictly filters for movies rated **7.5 or higher** on IMDb / TMDb with significant vote counts.
2. **📺 Included in Base Subscriptions Only**: Strictly filters for titles available on streaming platforms (*Netflix, Amazon Prime Video, Apple TV+, Peacock, Max, etc.*) that are **included in your standard subscription (`flatrate`)** — zero extra rentals, pay-per-view, or add-on channel purchases.
3. **📖 Tailored 1-Paragraph Summaries**: For each recommendation, Google Gemini writes a spoiler-free, 3–4 sentence overview highlighting the premise and why you will enjoy it based on your taste.
4. **🧠 Memory & Adaptive Learning**:
   - Stores all recommended and watched titles in SQLite (`movie_memory.db`) to ensure **no repeated recommendations**.
   - Tracks your reactions (*"Watched & Loved"*, *"Watching Tonight"*, *"Not for me"*).
   - Gemini dynamically evolves your taste profile over time based on your feedback.
5. **📲 Delivery Options**:
   - **Telegram Bot** with 1-click inline buttons for instant mobile feedback.
   - **Interactive CLI** for local testing, feedback management, and taste review.
6. **⏰ Automated Friday Runs**: Ready-to-go GitHub Actions workflow (`friday_movie_agent.yml`) scheduled to execute every Friday at 5:00 PM EST.

---

## 📂 Project Structure

```
movie_agent/
├── agent.py                 # Core AI agent (Gemini 2.5 structured output & prompt logic)
├── db.py                    # SQLite memory layer (tracks history, statuses & taste profile)
├── tmdb_client.py           # TMDb API client (strict >=7.5 rating & flatrate streaming filter)
├── notifier.py              # Telegram & Markdown formatting with interactive buttons
├── feedback_handler.py      # Taste refinement engine & Telegram callback listener
├── main.py                  # Scheduled Friday execution script
├── cli.py                   # Interactive local CLI interface
├── requirements.txt         # Python dependencies
├── .env.example             # Environment configuration template
├── tests/                   # Comprehensive unit test suite
└── .github/workflows/
    └── friday_movie_agent.yml # Scheduled Friday cron automation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Installation

```bash
cd "/Users/Bala/Desktop/Building/Movie Recommender Agent"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys (`.env`)

Copy the example file:
```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:
```env
# 1. TMDb API Key (Free: https://www.themoviedb.org/settings/api)
TMDB_API_KEY=your_tmdb_api_key

# 2. Gemini API Key (Free: https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key

# 3. Telegram Notifications (Optional, for mobile delivery)
# Create a bot via @BotFather and get your user ID via @userinfobot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# 4. Regional & Provider Preferences
WATCH_REGION=US
DEFAULT_WATCH_PROVIDERS=8|9|350|386  # 8=Netflix, 9=Prime, 350=AppleTV+, 386=Peacock
MIN_RATING=7.5
```

---

## 🕹️ Usage

### A. Run Interactive CLI
Use the interactive terminal menu to test recommendations, view history, or give feedback:
```bash
python cli.py
```
Menu options:
- `1`: Run Agent & Get 3 Friday Recommendations
- `2`: View Recent Recommendations & History
- `3`: Give Feedback on a Movie (*"Loved it"*, *"Skipped"*, etc.)
- `4`: View & Refine AI Taste Profile

### B. Run Friday Workflow
Runs the complete Friday job (checks feedback -> queries TMDb -> prompts Gemini -> updates DB -> delivers to Telegram):
```bash
python main.py
```

### C. Run Unit Tests
```bash
python -m unittest discover tests
```

---

## ⏰ Deploying Automated Friday Runs (GitHub Actions)

1. Push this repository to GitHub.
2. In your repository, go to **Settings > Secrets and variables > Actions > Secrets**.
3. Add the following repository secrets:
   - `TMDB_API_KEY`
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. The workflow in `.github/workflows/friday_movie_agent.yml` will automatically run every **Friday at 5:00 PM EST (21:00 UTC)**, deliver the recommendations, and commit the updated `movie_memory.db` back to the repository.
