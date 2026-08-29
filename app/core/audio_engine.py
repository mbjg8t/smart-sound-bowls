from threading import Lock


class AudioEngine:
    """
    Long-running audio engine abstraction.

    For the first stage this is deliberately MOCKED.

    Later this class will own the actual PCM5122 playback stream so
    Flask requests only change parameters. Flask itself will never
    directly generate audio samples or execute hardware commands.
    """

    SUPPORTED_WAVEFORMS = {
        "sine",
        "square",
        "triangle",
        "saw",
    }

    def __init__(self):
        self._lock = Lock()

        self.running = False
        self.waveform = "sine"
        self.frequency_hz = 220.0
        self.amplitude = 0.05

    def configure(
        self,
        frequency_hz=None,
        amplitude=None,
        waveform=None,
    ):
        with self._lock:

            if frequency_hz is not None:
                frequency_hz = float(frequency_hz)

                if not 1.0 <= frequency_hz <= 20000.0:
                    raise ValueError(
                        "Frequency must be between 1 and 20000 Hz."
                    )

                self.frequency_hz = frequency_hz

            if amplitude is not None:
                amplitude = float(amplitude)

                if not 0.0 <= amplitude <= 1.0:
                    raise ValueError(
                        "Amplitude must be between 0.0 and 1.0."
                    )

                self.amplitude = amplitude

            if waveform is not None:
                waveform = str(waveform).lower()

                if waveform not in self.SUPPORTED_WAVEFORMS:
                    raise ValueError(
                        f"Unsupported waveform: {waveform}"
                    )

                self.waveform = waveform

            return self.status()

    def start(self):
        with self._lock:
            self.running = True

            print(
                "[MOCK AUDIO] START "
                f"{self.waveform} "
                f"{self.frequency_hz:.2f} Hz "
                f"amplitude={self.amplitude:.3f}"
            )

            return self.status()

    def stop(self):
        with self._lock:
            self.running = False

            print("[MOCK AUDIO] STOP")

            return self.status()

    def status(self):
        return {
            "running": self.running,
            "waveform": self.waveform,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
            "backend": "mock",
        }
