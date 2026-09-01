import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size="small", silence_threshold=0.01):
        print(f"Loading Whisper '{model_size}' model...")
        print("(First run downloads the model — ~500MB for 'small')")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.silence_threshold = silence_threshold
        print("Model ready.\n")

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""
        # Whisper hallucinates stock phrases ("You", "Thank you.") on silence/noise
        # floor — it was trained on captioned video where those show up around
        # quiet gaps. Skip the model entirely below this volume.
        rms = np.sqrt(np.mean(np.square(audio)))
        if rms < self.silence_threshold:
            return ""
        segments, _ = self.model.transcribe(audio, beam_size=5, language="en")
        return " ".join(seg.text.strip() for seg in segments)
