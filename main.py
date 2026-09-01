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

METER_WIDTH = 20
METER_MAX = 0.15
METER_INTERVAL = 0.5


def load_config():
    with open("config.json") as f:
        return json.load(f)


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0


def _meter_bar(value: float, max_value: float = METER_MAX, width: int = METER_WIDTH) -> str:
    filled = min(int((value / max_value) * width), width)
    return "█" * filled + "░" * (width - filled)


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
    system_buffer = []
    mic_buffer = []

    capture_mic = config.get("capture_mic", True)
    volume_threshold = config.get("volume_threshold", 0.02)

    print("Phrase Counter running!")
    print(f"Tracking: {', '.join(p['name'] for p in config['phrases'])}")
    source_desc = "system audio + microphone" if capture_mic else "system audio"
    print(f"Listening to {source_desc}... (Ctrl+C to stop)\n")

    dashboard_url = config.get("dashboard_url")
    if config.get("open_dashboard", True) and dashboard_url:
        webbrowser.open(dashboard_url)

    with AudioCapture(capture_mic=capture_mic) as capture:
        target_samples = 16000 * buffer_seconds
        last_meter_time = 0.0

        try:
            while True:
                chunk = capture.get_chunk()
                if chunk is None:
                    continue

                system_chunk, mic_chunk = chunk
                system_buffer.append(system_chunk)
                mic_buffer.append(mic_chunk)

                now = time.monotonic()
                if now - last_meter_time >= METER_INTERVAL:
                    last_meter_time = now
                    system_vol = _rms(system_chunk)
                    mic_vol = _rms(mic_chunk) if capture_mic else 0.0
                    print(
                        f"  [vol] System {_meter_bar(system_vol)} {system_vol:.3f}"
                        f"  |  Mic {_meter_bar(mic_vol)} {mic_vol:.3f}"
                        f"  (threshold ref: {volume_threshold:.3f})"
                    )
                    db.update_levels(system_vol, mic_vol, volume_threshold)

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
