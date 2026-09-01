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

    transcriber = Transcriber(
        model_size=config.get("whisper_model", "small"),
        silence_threshold=config.get("silence_threshold", 0.01),
    )
    matcher = PhraseMatcher(config["phrases"], threshold=config.get("fuzzy_threshold", 75))

    buffer_seconds = config.get("buffer_seconds", 6)
    system_buffer = []
    mic_buffer = []

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

                system_chunk, mic_chunk = chunk
                system_buffer.append(system_chunk)
                mic_buffer.append(mic_chunk)

                if sum(len(c) for c in system_buffer) >= target_samples:
                    system_data = np.concatenate(system_buffer)
                    mic_data = np.concatenate(mic_buffer)
                    system_buffer.clear()
                    mic_buffer.clear()

                    system_text = transcriber.transcribe(system_data).strip()
                    mic_text = transcriber.transcribe(mic_data).strip() if capture_mic else ""

                    lines = []
                    if system_text:
                        lines.append(f"(System) {system_text}")
                    if mic_text:
                        lines.append(f"(Mic) {mic_text}")

                    if lines:
                        timestamp = time.strftime('%H:%M:%S')
                        for line in lines:
                            print(f"[{timestamp}] {line}")
                        db.update_transcript("\n".join(lines))

                    for source, text in (("System", system_text), ("Mic", mic_text)):
                        for phrase_id, phrase_name in matcher.find_matches(text):
                            count = db.increment(phrase_id)
                            print(f'  >>> "{phrase_name}" detected via {source}! Total: {count}\n')

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
