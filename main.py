import json
import os
import time
import webbrowser

import numpy as np
from dotenv import load_dotenv

from audio_capture import AudioCapture
from transcriber import Transcriber
from phrase_matcher import PhraseMatcher
from supabase_client import SupabaseClient

DASHBOARD_URL = "https://soban-a.github.io/Phrase-Counter/"


def load_config():
    with open("config.json") as f:
        return json.load(f)


def main():
    load_dotenv()
    config = load_config()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY — copy .env.example to .env and fill them in.")

    db = SupabaseClient(url, key)
    db.sync_phrases(config["phrases"])

    transcriber = Transcriber(model_size=config.get("whisper_model", "small"))
    matcher = PhraseMatcher(config["phrases"], threshold=config.get("fuzzy_threshold", 75))

    buffer_seconds = config.get("buffer_seconds", 6)
    audio_buffer = []

    capture_mic = config.get("capture_mic", True)

    print("Phrase Counter running!")
    print(f"Tracking: {', '.join(p['name'] for p in config['phrases'])}")
    source_desc = "system audio + microphone" if capture_mic else "system audio"
    print(f"Listening to {source_desc}... (Ctrl+C to stop)\n")

    if config.get("open_dashboard", True):
        webbrowser.open(DASHBOARD_URL)

    with AudioCapture(capture_mic=capture_mic) as capture:
        target_samples = 16000 * buffer_seconds

        try:
            while True:
                chunk = capture.get_chunk()
                if chunk is None:
                    continue

                audio_buffer.append(chunk)

                if sum(len(c) for c in audio_buffer) >= target_samples:
                    audio_data = np.concatenate(audio_buffer)
                    audio_buffer.clear()

                    transcript = transcriber.transcribe(audio_data)
                    if transcript.strip():
                        text = transcript.strip()
                        print(f"[{time.strftime('%H:%M:%S')}] {text}")
                        db.update_transcript(text)
                        for phrase_id, phrase_name in matcher.find_matches(transcript):
                            count = db.increment(phrase_id)
                            print(f'  >>> "{phrase_name}" detected! Total: {count}\n')

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
