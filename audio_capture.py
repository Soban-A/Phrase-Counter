import queue
import time
from math import gcd

import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import resample_poly


def _to_mono_16k(audio: np.ndarray, rate: int, channels: int) -> np.ndarray:
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        g = gcd(rate, 16000)
        audio = resample_poly(audio, 16000 // g, rate // g).astype(np.float32)
    return audio


class AudioCapture:
    """Captures system audio (WASAPI loopback) and, optionally, the default
    microphone, mixing both into a single mono 16kHz stream."""

    def __init__(self, chunk_duration=0.5, capture_mic=True):
        self.chunk_duration = chunk_duration
        self.capture_mic = capture_mic
        self._system_queue = queue.Queue()
        self._mic_queue = queue.Queue()
        self._pa = None
        self._system_stream = None
        self._mic_stream = None

    def _find_loopback_device(self, pa):
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            raise RuntimeError(
                "WASAPI not available. Are you on Windows with a compatible audio driver?"
            )

        default_output = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

        for loopback in pa.get_loopback_device_info_generator():
            if default_output["name"] in loopback["name"]:
                return loopback

        raise RuntimeError(
            f"No loopback device found for '{default_output['name']}'. "
            "Ensure your audio device supports WASAPI loopback."
        )

    def _find_mic_device(self, pa):
        try:
            return pa.get_default_input_device_info()
        except OSError:
            raise RuntimeError("No default microphone found.")

    def _make_callback(self, out_queue, rate, channels):
        def _callback(in_data, frame_count, time_info, status):
            audio = np.frombuffer(in_data, dtype=np.float32).copy()
            out_queue.put(_to_mono_16k(audio, rate, channels))
            return (None, pyaudio.paContinue)

        return _callback

    def start(self):
        self._pa = pyaudio.PyAudio()

        system_device = self._find_loopback_device(self._pa)
        system_rate = int(system_device["defaultSampleRate"])
        system_channels = int(system_device["maxInputChannels"])
        self._system_stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=system_channels,
            rate=system_rate,
            input=True,
            input_device_index=system_device["index"],
            frames_per_buffer=int(system_rate * self.chunk_duration),
            stream_callback=self._make_callback(self._system_queue, system_rate, system_channels),
        )
        self._system_stream.start_stream()
        print(f"Capturing system audio: {system_device['name']} @ {system_rate}Hz, {system_channels}ch")

        if self.capture_mic:
            mic_device = self._find_mic_device(self._pa)
            mic_rate = int(mic_device["defaultSampleRate"])
            mic_channels = int(mic_device["maxInputChannels"])
            self._mic_stream = self._pa.open(
                format=pyaudio.paFloat32,
                channels=mic_channels,
                rate=mic_rate,
                input=True,
                input_device_index=mic_device["index"],
                frames_per_buffer=int(mic_rate * self.chunk_duration),
                stream_callback=self._make_callback(self._mic_queue, mic_rate, mic_channels),
            )
            self._mic_stream.start_stream()
            print(f"Capturing microphone: {mic_device['name']} @ {mic_rate}Hz, {mic_channels}ch")

        return self

    def stop(self):
        for stream in (self._system_stream, self._mic_stream):
            if stream:
                stream.stop_stream()
                stream.close()
        if self._pa:
            self._pa.terminate()

    def _drain(self, q):
        """Non-blocking: pulls every chunk currently queued, or an empty array."""
        chunks = []
        while True:
            try:
                chunks.append(q.get_nowait())
            except queue.Empty:
                break
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def get_chunk(self, timeout=1.0, poll_interval=0.05):
        """Returns one mixed, mono, 16kHz float32 chunk, or None if neither source
        produced anything within `timeout`.

        System audio and the mic are drained independently — WASAPI loopback can
        stop delivering callbacks entirely when system output is truly silent (e.g.
        no one is talking on a call with no other sound), so waiting on system audio
        before checking the mic would starve mic capture during exactly that case.
        Whichever source has nothing this cycle is padded with silence instead."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            system_audio = self._drain(self._system_queue)
            mic_audio = self._drain(self._mic_queue) if self.capture_mic else np.zeros(0, dtype=np.float32)
            if len(system_audio) or len(mic_audio):
                break
            time.sleep(poll_interval)
        else:
            return None

        if not self.capture_mic:
            return system_audio if len(system_audio) else None

        n = max(len(system_audio), len(mic_audio))
        if len(system_audio) < n:
            system_audio = np.pad(system_audio, (0, n - len(system_audio)))
        if len(mic_audio) < n:
            mic_audio = np.pad(mic_audio, (0, n - len(mic_audio)))

        return np.clip(system_audio + mic_audio, -1.0, 1.0)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()
