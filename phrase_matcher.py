from rapidfuzz import fuzz


class PhraseMatcher:
    def __init__(self, phrases: list, threshold: int = 75):
        self.phrases = phrases
        self.threshold = threshold

    def find_matches(self, transcript: str) -> list:
        """Returns list of (phrase_id, phrase_name) for each phrase detected."""
        text = transcript.lower().strip()
        if not text:
            return []

        matches = []
        for p in self.phrases:
            score = fuzz.partial_ratio(p["phrase"].lower(), text)
            if score >= self.threshold:
                matches.append((p["id"], p["name"]))

        return matches
