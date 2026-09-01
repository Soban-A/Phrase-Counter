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
        segments, _ = self.model.transcribe(audio, beam_size=5, language="en")
        return " ".join(seg.text.strip() for seg in segments)
