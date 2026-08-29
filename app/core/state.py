from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class BowlState:
    system_status: str = "READY"

    output_running: bool = False
    waveform: str = "sine"
    frequency_hz: float = 220.0
    amplitude: float = 0.05

    mic_enabled: bool = False
    mic_level_dbfs: float | None = None
    detected_frequency_hz: float | None = None

    resonance_frequency_hz: float | None = None

    hardware_mode: str = "MOCK"


class StateStore:
    def __init__(self):
        self._state = BowlState()
        self._lock = Lock()

    def snapshot(self):
        with self._lock:
            return asdict(self._state)

    def update(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                if not hasattr(self._state, key):
                    raise AttributeError(f"Unknown state field: {key}")

                setattr(self._state, key, value)

            return asdict(self._state)
