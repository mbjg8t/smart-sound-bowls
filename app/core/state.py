from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class BowlState:
    bowl_id: int
    name: str
    system_status: str = "READY"
    output_running: bool = False
    pattern: str = "strike"
    waveform: str = "sine"
    frequency_hz: float = 528.7
    amplitude: float = 0.0007
    attack_s: float = 3.0
    hold_s: float = 4.0
    release_s: float = 5.0
    rest_s: float = 3.0
    repeats: int = 1
    chirp_span_hz: float = 20.0
    wah_depth_hz: float = 8.0
    wah_rate_hz: float = 0.35
    piezo_level: float | None = None
    detected_frequency_hz: float | None = None
    resonance_frequency_hz: float | None = None


class StateStore:
    def __init__(self, bowl_count=2):
        self._lock = Lock()
        self._bowls = {
            bowl_id: BowlState(bowl_id=bowl_id, name=f"Bowl {bowl_id}")
            for bowl_id in range(1, bowl_count + 1)
        }

    def snapshot(self, bowl_id=None):
        with self._lock:
            if bowl_id is not None:
                return asdict(self._get(bowl_id))
            return {str(k): asdict(v) for k, v in self._bowls.items()}

    def update(self, bowl_id, **kwargs):
        with self._lock:
            state = self._get(bowl_id)
            for key, value in kwargs.items():
                if not hasattr(state, key):
                    raise AttributeError(f"Unknown bowl state field: {key}")
                setattr(state, key, value)
            return asdict(state)

    def _get(self, bowl_id):
        bowl_id = int(bowl_id)
        if bowl_id not in self._bowls:
            raise KeyError(f"Unknown bowl: {bowl_id}")
        return self._bowls[bowl_id]
