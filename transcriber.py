import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size="small"):
        print(f"Loading Whisper '{model_size}' model...")
        print("(First run downloads the model — ~500MB for 'small')")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Model ready.\n")

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""
        # vad_filter uses Silero VAD to skip non-speech regions before decoding —
        # cuts compute on silence and avoids Whisper hallucinating stock phrases
        # ("You", "Thank you.") that it associates with quiet gaps.
        segments, _ = self.model.transcribe(audio, beam_size=5, language="en", vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments)
