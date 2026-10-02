# 🎬 Friday Movie Recommendation Agent

An autonomous film curation agent that runs **every Friday** to deliver **3 exceptional movie recommendations** directly to your phone (via Telegram) or terminal.

The agent enforces 4 strict criteria:
1. **⭐ High Quality**: Rated **7.5 or higher** on IMDb with substantial vote counts.
2. **📺 Base Subscriptions Only**: Strictly available on streaming platforms (*Netflix, Amazon Prime Video, Apple TV+, Peacock, etc.*) included with your standard subscription (`flatrate`) — zero extra rentals, pay-per-view, or add-on channel purchases.
3. **📖 Tailored 1-Paragraph Summaries**: Spoiler-free, 3–4 sentence overview highlighting the premise and why you will enjoy it based on your taste.
4. **🧠 Memory & Continuous Learning**: Remembers past choices, avoids duplicate recommendations, and dynamically adapts to your feedback.

---

## 🏛️ System Architecture Evolution

This project evolved from an initial monolithic LLM implementation (**v1.0**) to a hybrid **Two-Speed Cognitive Architecture** (**v2.0**) combining **Jev (TypeSafe AI)** as a fast System-1 decision layer and **Google Gemini** as a creative System-2 storyteller.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TWO-SPEED COGNITIVE ARCHITECTURE                      │
│                                                                             │
│  [SYSTEM 1: JEV (TypeSafe AI)]              [SYSTEM 2: GEMINI]             │
│  • Non-autoregressive decision model        • Autoregressive reasoning LLM  │
│  • Microsecond latency, typed outputs       • Creative narrative generation │
│  • Fast critique & intent extraction        • Tailored 1-paragraph summary  │
│  • Diversity scoring & hard-gating          • Long-term taste synthesis     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 1. Version 1.0 — Initial Implementation

In the first implementation, the system used a straightforward pipeline centered around a single generative LLM:

```
[Cron / CLI]
     │
     ▼
[TMDb /discover/movie]  ──(Top 4 pages popularity.desc)──► Candidate Pool (~25 movies)
     │
     ▼
[SQLite Memory]         ──(Filter cooldown: 14 days)─────► Unseen Candidates
     │
     ▼
[Google Gemini]         ──(Evaluates 25 movies in prompt)► Top 3 Picks + Summaries
     │
     ▼
[Telegram / CLI]        ──(3 Binary Buttons)─────────────► [Liked] [Selected] [Skip]
```

#### v1.0 Component Architecture
* **`tmdb_client.py`**: Queried TMDb’s `/discover/movie` endpoint with `with_watch_monetization_types=flatrate` across the top 4 pages sorted strictly by `popularity.desc`. Used TMDb's internal user score (`vote_average`) as the rating.
* **`db.py`**: SQLite database storing recommendations. Evaluated unseen movies using a 14-day cooldown for unreviewed titles.
* **`agent.py`**: Passed the first 25 candidate JSON objects directly into Gemini’s context window. If the unseen pool dropped below 3, it fell back to passing previously seen movies.
* **`notifier.py`**: Formatted markdown and sent Telegram notifications with 3 inline buttons: `[ Watch ]`, `[ Liked ]`, `[ Skip ]`.
* **`feedback_handler.py`**: Recorded button presses and invoked Gemini to summarize user history.

#### Identified Limitations in v1.0
1. **Recommendation Repetition**:
   * *Shallow candidate pool*: Querying only the top 4 pages of `popularity.desc` returned the same ~25 blockbuster titles every run.
   * *14-day reset*: Unreviewed movies were re-eligible after 14 days, causing the same titles to cycle repeatedly.
   * *Aggressive fallback*: When `len(unseen_candidates) < 3`, the agent reset and reused past candidates.
2. **Inaccurate / Non-IMDb Ratings**:
   * Relied on TMDb’s internal score (`vote_average`), which represents a small subset of TMDb votes and often diverges significantly from actual, real-time IMDb scores.
3. **Coarse, Binary Feedback**:
   * Users could only tap `Liked`, `Selected`, or `Skip`. There was no way to provide nuanced feedback (*"Loved the atmosphere and twist, but the pacing was too slow and dragged on. Want something tighter under 2 hours next time"*).

---

### 2. Version 2.0 — The Jev System 1 + System 2 Architecture

To resolve the root causes of repetition, inaccurate ratings, and coarse feedback, v2.0 introduces a **hybrid decision and generative architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEEKLY RECOMMENDATION PIPELINE                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. MULTI-SLICE DISCOVERY & LIVE IMDb ENRICHMENT (tmdb_client.py)            │
│    • Slice A: Acclaimed modern releases (2015-present, randomized pages)    │
│    • Slice B: Modern classics (2000-2014, vote_count sorted)                │
│    • Slice C: All-time top-rated masterpieces (1500+ votes)                 │
│    • Slice D: Trending popular hits                                         │
│    • TMDb ID ──► Fetch External IMDb ID (e.g. tt0816692)                    │
│    • OMDb API ──► Real-time IMDb Rating, IMDb Votes, Runtime, Metascore     │
│    • Strict Gate: Live IMDb Rating >= 7.5 & Base Subscription flatrate      │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. PERMANENT ANTI-REPETITION FILTER (db.py)                                 │
│    • Queries ALL movie IDs ever recommended or reviewed in SQLite           │
│    • Zero-repetition guarantee: previously recommended movies are NEVER     │
│      recycled, eliminating recommendation fatigue entirely                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. SYSTEM 1: JEV DIVERSITY & TASTE PRE-SCORING (jev_client.py)              │
│    • Evaluates candidate diversity against recent recommendation themes     │
│    • Hard-gates against user's extracted avoid_genres (e.g. horror, gore)   │
│    • Ranks candidate pool matching user's preferred pacing & tone           │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. SYSTEM 2: GEMINI NARRATIVE CURATION (agent.py)                           │
│    • Receives optimal pre-screened candidate pool + Jev preference signals  │
│    • Selects top 3 balanced movies for Friday evening                       │
│    • Writes tailored, spoiler-free 1-paragraph summaries (3-4 sentences)    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. MULTI-MODAL DELIVERY & RICH FEEDBACK LOOP (notifier.py / cli.py)         │
│    • Displays live IMDb badge, vote counts, and runtime duration            │
│    • Interactive Telegram bot & CLI critique prompt                         │
│    • Free-form user critique parsed non-autoregressively by Jev System 1:   │
│      Score (1-5), Pacing, Tone, Runtime Constraint, Avoided Genres          │
│    • SQLite memory updated; Gemini evolves long-term narrative taste profile│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Comparison Matrix: v1.0 vs. v2.0

| Capability | v1.0 (Initial Implementation) | v2.0 (Upgraded with Jev & OMDb) |
| :--- | :--- | :--- |
| **Cognitive Architecture** | Single-tier LLM (Gemini only) | Two-Speed Hybrid: **Jev (System 1)** + **Gemini (System 2)** |
| **Candidate Discovery** | Shallow single-sort (`popularity.desc`, pages 1–4) | **Multi-Slice Discovery** across decades (2015+, 2000s, classics) with randomized page seeding |
| **Candidate Pool Size** | ~25 static items | **50–100+ fresh candidates per run** |
| **Anti-Repetition Engine** | 14-day cooldown; fallback reused seen movies | **Permanent Exclusion**: Zero repeats; never recycles recommended titles |
| **Rating Accuracy** | TMDb internal `vote_average` (dated / small sample) | **Authentic Live IMDb Ratings & Votes** via OMDb API (`tt...` resolution) |
| **Rating Validation** | Soft threshold check on TMDb score | **Strict Hard Gate**: Must be $\ge 7.5$ on live IMDb |
| **Feedback Mechanism** | 3 binary buttons (`liked`, `selected`, `skip`) | **Free-Form Natural Language Critique** + Quick Buttons |
| **Feedback Extraction** | Keyword counting / slow LLM parsing | **Jev Non-Autoregressive Typed Primitives** (`Score`, `Choice`, `Noul`) |
| **Extracted Signals** | General liked/disliked genre strings | **Sentiment (1–5), Pacing, Tone, Runtime, Avoided Genres** |
| **Candidate Diversity** | Unmanaged; often recommended similar genres | **Jev Novelty Scoring** against recent watch history |
| **Metadata Badges** | Title, Year, TMDb Score, Platform | Title, Year, **Live IMDb Rating**, **Vote Count**, **Runtime**, Platform |

---

## 📂 Project Directory Structure

```
Movie Recommender Agent/
├── jev_client.py            # Jev (TypeSafe AI) System 1 decision & feedback parser
├── tmdb_client.py           # TMDb & OMDb client (live IMDb ratings & multi-slice discovery)
├── agent.py                 # Core AI agent (Gemini creative curator + Jev signal integration)
├── db.py                    # SQLite memory layer (strict de-duplication, rich feedback schema)
├── feedback_handler.py      # Multi-dimensional critique processing & taste evolution
├── notifier.py              # Telegram & Markdown formatting with live IMDb badges
├── main.py                  # Scheduled Friday execution script
├── cli.py                   # Interactive local CLI interface with Jev critique mode
├── requirements.txt         # Python dependencies (includes typesafe-sdk, google-genai)
├── .env.example             # Environment configuration template
├── tests/                   # Comprehensive unit test suite (15 passing tests)
│   ├── test_jev_feedback.py          # Jev question primitives & fallback heuristic tests
│   ├── test_live_imdb_and_diversity.py# OMDb live rating & multi-slice candidate tests
│   ├── test_movie_agent.py           # Anti-repetition database & notifier badge tests
│   └── test_agent_mock.py            # Full agent workflow integration tests
└── .github/workflows/
    └── friday_movie_agent.yml # Scheduled Friday cron automation
```

---

## 🧠 How Jev (System 1) Works in the Agent

**Jev** (developed by TypeSafe AI) is a non-autoregressive decision model designed for fast, structured outputs rather than generating conversational prose.

In this agent, Jev is invoked via `typesafe-sdk` using three decision primitives:

1. **`Score`**: Evaluates overall user sentiment and enjoyment on an ordered 1.0–5.0 rubric.
2. **`Choice`**: Categorizes user critique into typed decision variables with confidence metrics:
   * **Pacing**: `fast_paced`, `slow_burn`, `moderate`, `unspecified`
   * **Tone / Mood**: `dark_gritty`, `cerebral_thoughtprovoking`, `uplifting_feelgood`, `tense_suspenseful`, `fun_humorous`
   * **Runtime Preference**: `under_90m`, `under_2h`, `epic_over_2h`
   * **Disliked Genre**: `horror`, `romance`, `action`, `sci_fi`, `comedy`, `drama`, `none`
3. **`Noul`**: Outputs exact yes/no probabilities (0.0 to 1.0) for statements such as:
   * *wants_more_like_this*: Does the user want more movies similar in style or director?
   * *complained_about_runtime*: Did the user feel the movie was too long or dragged?
   * *is_novel*: Is a candidate movie sufficiently distinct from recent recommendations?

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Installation

Ensure you have Python 3.10+ installed:

```bash
cd "/Users/Bala/Desktop/Building/Movie Recommender Agent"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)

Copy the template:
```bash
cp .env.example .env
```

Configure your API keys in `.env`:
```env
# 1. TMDb API Key (Free at https://www.themoviedb.org/settings/api)
TMDB_API_KEY=your_tmdb_api_key

# 2. Google Gemini API Key (Free at https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key

# 3. Jev / TypeSafe AI Key (For System 1 fast decision & feedback parsing)
TYPESAFE_API_KEY=your_jev_api_key
# Alternative alias: JEV_API_KEY=your_jev_api_key

# 4. OMDb API Key (For real-time live IMDb ratings & votes; Free at https://www.omdbapi.com/apikey.aspx)
OMDB_API_KEY=your_omdb_api_key

# 5. Telegram Notifications (Optional, for mobile delivery)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# 6. Regional & Provider Preferences
WATCH_REGION=US
DEFAULT_WATCH_PROVIDERS=8|9|350|386  # 8=Netflix, 9=Prime, 350=AppleTV+, 386=Peacock
MIN_RATING=7.5
MIN_VOTE_COUNT=500
```

---

## 🕹️ Usage & Testing

### A. Run Interactive CLI
The CLI provides an interface to generate recommendations, inspect SQLite memory, and test natural language critiques:

```bash
python cli.py
```

Menu options:
* **`1`**: **Run Agent & Get 3 Friday Recommendations** — Fetches live IMDb-verified candidates, checks anti-repetition memory, and generates Gemini summaries.
* **`2`**: **View Recent Recommendations & History** — Inspect past picks, status flags, Jev ratings, and saved critiques.
* **`3`**: **Give Feedback / Critique on a Movie** — 
  * Choose **Mode 1** (*Tell the agent in your own words*): Enter any critique (*e.g., "Loved the dark atmosphere and twist, but pacing was too slow and dragged on. Want something tighter"*).
  * Watch **Jev System 1** break down your critique into typed preference scores in real time!
* **`4`**: **View & Refine AI Taste Profile** — Inspect current preference vectors and synthesize updated taste profiles.

### B. Run Friday Scheduled Workflow
Runs the complete Friday job (checks feedback -> queries multi-slice TMDb & OMDb -> prompts Gemini -> updates SQLite memory -> delivers via Telegram):

```bash
python main.py
```

### C. Run Unit Test Suite
Run the 15 automated unit tests verifying Jev parsing, live IMDb resolution, database deduplication, and notification formatting:

```bash
python -m unittest discover tests
```

---

## ⏰ Automated Friday Deployment (GitHub Actions)

The repository includes a ready-to-use GitHub Actions workflow configured in [`.github/workflows/friday_movie_agent.yml`](file:///Users/Bala/Desktop/Building/Movie%20Recommender%20Agent/.github/workflows/friday_movie_agent.yml):

1. Push this repository to GitHub.
2. Navigate to **Settings > Secrets and variables > Actions > Secrets**.
3. Add the following repository secrets:
   * `TMDB_API_KEY`
   * `GEMINI_API_KEY`
   * `TYPESAFE_API_KEY`
   * `OMDB_API_KEY`
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`
4. The workflow runs automatically every **Friday at 5:00 PM EST (21:00 UTC)**, sends the recommendations to your Telegram, and commits the updated `movie_memory.db` back to the repository to preserve recommendation memory across runs.
