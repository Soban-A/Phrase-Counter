import queue
import numpy as np
import pyaudiowpatch as pyaudio


class AudioCapture:
    def __init__(self, chunk_duration=0.5):
        self.chunk_duration = chunk_duration
        self.queue = queue.Queue()
        self._pa = None
        self._stream = None
        self._device_rate = None
        self._channels = None

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

    def _callback(self, in_data, frame_count, time_info, status):
        audio = np.frombuffer(in_data, dtype=np.float32).copy()
        self.queue.put(audio)
        return (None, pyaudio.paContinue)

    def start(self):
        self._pa = pyaudio.PyAudio()
        device = self._find_loopback_device(self._pa)

        self._device_rate = int(device["defaultSampleRate"])
        self._channels = int(device["maxInputChannels"])
        chunk_size = int(self._device_rate * self.chunk_duration)

        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=self._channels,
            rate=self._device_rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=chunk_size,
            stream_callback=self._callback,
        )
        self._stream.start_stream()
        print(f"Capturing: {device['name']} @ {self._device_rate}Hz, {self._channels}ch")
        return self

    def stop(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def get_chunk(self, timeout=1.0):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()
