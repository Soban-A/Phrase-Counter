import json
import os
import time
from math import gcd

import numpy as np
from dotenv import load_dotenv
from scipy.signal import resample_poly

from audio_capture import AudioCapture
from transcriber import Transcriber
from phrase_matcher import PhraseMatcher
from supabase_client import SupabaseClient


def load_config():
    with open("config.json") as f:
        return json.load(f)


def to_mono_16k(audio: np.ndarray, from_rate: int, channels: int) -> np.ndarray:
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if from_rate != 16000:
        g = gcd(from_rate, 16000)
        audio = resample_poly(audio, 16000 // g, from_rate // g).astype(np.float32)
    return audio


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

    print("Phrase Counter running!")
    print(f"Tracking: {', '.join(p['name'] for p in config['phrases'])}")
    print("Listening to system audio... (Ctrl+C to stop)\n")

    with AudioCapture() as capture:
        target_samples = 16000 * buffer_seconds

        try:
            while True:
                chunk = capture.get_chunk()
                if chunk is None:
                    continue

                audio_buffer.append(to_mono_16k(chunk, capture._device_rate, capture._channels))

                if sum(len(c) for c in audio_buffer) >= target_samples:
                    audio_data = np.concatenate(audio_buffer)
                    audio_buffer.clear()

                    transcript = transcriber.transcribe(audio_data)
                    if transcript.strip():
                        print(f"[{time.strftime('%H:%M:%S')}] {transcript.strip()}")
                        for phrase_id, phrase_name in matcher.find_matches(transcript):
                            count = db.increment(phrase_id)
                            print(f'  >>> "{phrase_name}" detected! Total: {count}\n')

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
