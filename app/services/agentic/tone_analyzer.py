"""
Journal tone analyzer using TextBlob sentiment analysis.
Maps sentiment polarity to ZenU emotional categories.
Free, no API calls needed.
"""

from textblob import TextBlob
from typing import List


class ToneAnalyzer:

    def dominant_tone(self, texts: List[str]) -> str:
        if not texts:
            return "neutral"

        scores = []
        for text in texts:
            blob = TextBlob(text)
            scores.append(blob.sentiment.polarity)

        avg = sum(scores) / len(scores)
        subjectivity = sum(TextBlob(t).sentiment.subjectivity for t in texts) / len(texts)

        # Map polarity to tone buckets
        if avg < -0.3:
            return "negative"
        elif avg < -0.05:
            # Low polarity + high subjectivity = anxious
            if subjectivity > 0.6:
                return "anxious"
            return "negative"
        elif avg > 0.2:
            return "positive"
        else:
            return "neutral"

    def tone_score(self, text: str) -> float:
        """Returns normalized 0-1 score where 1 = most positive."""
        blob = TextBlob(text)
        return round((blob.sentiment.polarity + 1) / 2.0, 4)
