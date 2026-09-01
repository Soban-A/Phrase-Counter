from rapidfuzz import fuzz


class PhraseMatcher:
    def __init__(self, phrases: list, threshold: int = 75):
        self.phrases = phrases
        self.threshold = threshold

    def find_matches(self, transcript: str) -> list:
        """Returns (phrase_id, phrase_name), once per occurrence of each phrase detected."""
        text = transcript.lower().strip()
        if not text:
            return []

        words = text.split()
        matches = []
        for p in self.phrases:
            occurrences = self._count_occurrences(words, p["phrase"].lower())
            matches.extend([(p["id"], p["name"])] * occurrences)

        return matches

    def _count_occurrences(self, words: list, phrase: str) -> int:
        """Slides a window the width of the phrase across the transcript, counting
        non-overlapping windows that clear the fuzzy threshold."""
        window_size = len(phrase.split())
        count = 0
        i = 0
        while i <= len(words) - window_size:
            window = " ".join(words[i:i + window_size])
            if fuzz.ratio(phrase, window) >= self.threshold:
                count += 1
                i += window_size
            else:
                i += 1
        return count
