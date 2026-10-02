"""
Jev (TypeSafe AI) System 1 Decision & Feedback Layer.
Provides fast, non-autoregressive structured classification, multi-dimensional feedback parsing,
and candidate decision-gating without LLM token-generation latency.
"""

import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

try:
    from typesafe_sdk import TypeSafeClient, Choice, Score, Noul
    TYPESAFE_AVAILABLE = True
except ImportError:
    TYPESAFE_AVAILABLE = False


class ParsedFeedback(BaseModel):
    sentiment_score: float = Field(
        description="User enjoyment/sentiment score on 1-5 scale (1: Hated, 5: Loved)",
        default=3.0
    )
    pacing_preference: str = Field(
        description="Extracted pacing preference ('fast_paced', 'slow_burn', 'moderate', 'unspecified')",
        default="unspecified"
    )
    tone_preference: str = Field(
        description="Extracted tone preference ('dark_gritty', 'uplifting_feelgood', 'cerebral_thoughtprovoking', 'fun_humorous', 'tense_suspenseful', 'unspecified')",
        default="unspecified"
    )
    wants_more_like_this: float = Field(
        description="Probability that user wants more movies like this (0 to 1)",
        default=0.5
    )
    complained_about_runtime: float = Field(
        description="Probability that user complained about movie length (0 to 1)",
        default=0.0
    )
    preferred_runtime_category: str = Field(
        description="Preferred runtime category ('under_90m', 'under_2h', 'epic_over_2h', 'unspecified')",
        default="unspecified"
    )
    disliked_genre: str = Field(
        description="Specific genre user noted they dislike or want to avoid ('horror', 'romance', 'action', 'sci_fi', 'comedy', 'drama', 'none')",
        default="none"
    )
    confidence: float = Field(
        description="System 1 confidence in the parsed feedback",
        default=1.0
    )


class JevClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY")
        self.client = None
        if TYPESAFE_AVAILABLE and self.api_key:
            self.client = TypeSafeClient(api_key=self.api_key)

    def is_configured(self) -> bool:
        return self.client is not None

    def parse_user_feedback(self, feedback_text: str, movie_context: Optional[str] = None) -> ParsedFeedback:
        """
        Uses Jev System 1 to decompose free-form user critiques into typed preference vectors.
        Fast, non-autoregressive, and deterministic.
        """
        if not self.client:
            # Fallback heuristic parser when Jev API key is not configured
            return self._heuristic_fallback_parse(feedback_text)

        state_context = f"Movie Context: {movie_context}\nUser Feedback: {feedback_text}" if movie_context else feedback_text

        questions = {
            "sentiment": Score(
                instructions="Score the user's overall sentiment/enjoyment of the movie.",
                criteria=[
                    "1: Strongly negative / hated it / regretted watching",
                    "2: Disliked / boring / flawed",
                    "3: Neutral / mixed feelings / okay",
                    "4: Liked / enjoyed / good watch",
                    "5: Loved / exceptional / highly recommended"
                ]
            ),
            "pacing": Choice(
                instructions="What pacing preference or critique is indicated?",
                criteria={
                    "fast_paced": "Prefers fast-paced, high momentum, snappy progression",
                    "slow_burn": "Prefers slow-burn, atmospheric, gradual buildup",
                    "moderate": "Prefers balanced, traditional pacing",
                    "unspecified": "No clear pacing preference mentioned"
                }
            ),
            "tone": Choice(
                instructions="What tone or mood does the user indicate preferring or enjoying?",
                criteria={
                    "dark_gritty": "Dark, gritty, realistic, intense, bleak",
                    "uplifting_feelgood": "Uplifting, feel-good, inspiring, warm",
                    "cerebral_thoughtprovoking": "Cerebral, complex, philosophical, mind-bending",
                    "fun_humorous": "Fun, witty, comedic, entertaining",
                    "tense_suspenseful": "Tense, suspenseful, edge-of-seat, mysterious",
                    "unspecified": "No tone preference indicated"
                }
            ),
            "wants_similar": Noul(
                instructions="Does the user want more movies similar to this one in style, theme, or director?"
            ),
            "runtime_complaint": Noul(
                instructions="Did the user express that the movie was too long, dragged on, or that they want shorter films?"
            ),
            "runtime_category": Choice(
                instructions="What runtime duration preference does the user indicate?",
                criteria={
                    "under_90m": "Under 90 minutes (short & tight)",
                    "under_2h": "Standard runtime under 2 hours",
                    "epic_over_2h": "Long, epic format over 2 hours",
                    "unspecified": "No runtime preference mentioned"
                }
            ),
            "disliked_genre": Choice(
                instructions="Did the user identify a specific genre they dislike or want to avoid?",
                criteria={
                    "horror": "Avoid horror / excessive gore",
                    "romance": "Avoid romance / rom-coms",
                    "action": "Avoid generic action",
                    "sci_fi": "Avoid sci-fi",
                    "comedy": "Avoid comedy",
                    "drama": "Avoid heavy drama",
                    "none": "No genre disliked"
                }
            )
        }

        try:
            response = self.client.system_one(state=state_context, questions=questions)
            answers = response.answers

            # Parse score (1-5)
            sentiment_score = 3.0
            if "sentiment" in answers and hasattr(answers["sentiment"], "score"):
                sentiment_score = float(answers["sentiment"].score)

            # Parse pacing
            pacing = "unspecified"
            if "pacing" in answers and hasattr(answers["pacing"], "choice"):
                pacing = answers["pacing"].choice

            # Parse tone
            tone = "unspecified"
            if "tone" in answers and hasattr(answers["tone"], "choice"):
                tone = answers["tone"].choice

            # Parse nouls (yes/no probabilities)
            wants_more = 0.5
            if "wants_similar" in answers and hasattr(answers["wants_similar"], "noul"):
                wants_more = float(answers["wants_similar"].noul)

            runtime_complaint = 0.0
            if "runtime_complaint" in answers and hasattr(answers["runtime_complaint"], "noul"):
                runtime_complaint = float(answers["runtime_complaint"].noul)

            # Parse runtime category
            runtime_cat = "unspecified"
            if "runtime_category" in answers and hasattr(answers["runtime_category"], "choice"):
                runtime_cat = answers["runtime_category"].choice

            # Parse disliked genre
            disliked_genre = "none"
            if "disliked_genre" in answers and hasattr(answers["disliked_genre"], "choice"):
                disliked_genre = answers["disliked_genre"].choice

            return ParsedFeedback(
                sentiment_score=sentiment_score,
                pacing_preference=pacing,
                tone_preference=tone,
                wants_more_like_this=wants_more,
                complained_about_runtime=runtime_complaint,
                preferred_runtime_category=runtime_cat,
                disliked_genre=disliked_genre,
                confidence=1.0
            )
        except Exception as e:
            print(f"[JevClient] System 1 call failed: {e}. Using fallback heuristic.")
            return self._heuristic_fallback_parse(feedback_text)

    def score_candidate_diversity(
        self,
        candidate_summary: str,
        user_history_summaries: List[str]
    ) -> float:
        """
        Uses Jev to calculate a novelty/diversity score (0.0 to 1.0) against recently recommended movies.
        Higher score means novel/distinct; lower score means too similar to recently watched.
        """
        if not self.client or not user_history_summaries:
            return 1.0

        state = (
            f"Candidate: {candidate_summary}\n\n"
            f"Recent Recommendations:\n" + "\n".join(f"- {s}" for s in user_history_summaries[:5])
        )

        questions = {
            "is_novel": Noul(
                instructions="Is this candidate distinctly fresh and different in theme, premise, or genre compared to the recent recommendations?"
            )
        }

        try:
            res = self.client.system_one(state=state, questions=questions)
            if "is_novel" in res.answers and hasattr(res.answers["is_novel"], "noul"):
                return float(res.answers["is_novel"].noul)
        except Exception:
            pass
        return 1.0

    def _heuristic_fallback_parse(self, text: str) -> ParsedFeedback:
        """Fallback rule-based parser if Jev API key is not yet set."""
        lower = text.lower()
        
        # Sentiment
        sentiment = 3.0
        if any(w in lower for w in ["loved", "amazing", "masterpiece", "great", "excellent", "favorite"]):
            sentiment = 5.0
        elif any(w in lower for w in ["liked", "good", "enjoyed", "solid", "fun"]):
            sentiment = 4.0
        elif any(w in lower for w in ["hated", "awful", "terrible", "waste of time", "garbage"]):
            sentiment = 1.0
        elif any(w in lower for w in ["disliked", "boring", "slow", "meh", "bad"]):
            sentiment = 2.0

        # Pacing
        pacing = "unspecified"
        if any(w in lower for w in ["fast", "fast-paced", "quick", "snappy"]):
            pacing = "fast_paced"
        elif any(w in lower for w in ["slow", "slow-burn", "dragged", "sluggish"]):
            pacing = "slow_burn"

        # Tone
        tone = "unspecified"
        if any(w in lower for w in ["dark", "gritty", "bleak"]):
            tone = "dark_gritty"
        elif any(w in lower for w in ["uplifting", "feel-good", "wholesome", "heartwarming"]):
            tone = "uplifting_feelgood"
        elif any(w in lower for w in ["mind-bending", "cerebral", "complex", "twist", "philosophical"]):
            tone = "cerebral_thoughtprovoking"
        elif any(w in lower for w in ["funny", "hilarious", "comedy", "witty"]):
            tone = "fun_humorous"
        elif any(w in lower for w in ["tense", "suspenseful", "thrilling"]):
            tone = "tense_suspenseful"

        runtime_complaint = 0.8 if any(w in lower for w in ["too long", "dragged on", "shorter"]) else 0.0
        wants_more = 0.8 if any(w in lower for w in ["more like this", "loved this style", "similar"]) else 0.5

        return ParsedFeedback(
            sentiment_score=sentiment,
            pacing_preference=pacing,
            tone_preference=tone,
            wants_more_like_this=wants_more,
            complained_about_runtime=runtime_complaint,
            preferred_runtime_category="under_2h" if runtime_complaint > 0.5 else "unspecified",
            disliked_genre="horror" if "no horror" in lower else "none",
            confidence=0.7
        )
