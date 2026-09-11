from copy import deepcopy

from app.core.audio_engine import AudioEngine
from app.core.hardware_config import HardwareConfigStore
from app.core.state import StateStore


class SoundBowlController:
    BOWL_COUNT = 2

    def __init__(self):
        self.hardware = HardwareConfigStore()
        self.state = StateStore(self.BOWL_COUNT)
        self.audio = {bowl_id: AudioEngine() for bowl_id in range(1, self.BOWL_COUNT + 1)}
        self._sync_initial_hardware_defaults()

    def _sync_initial_hardware_defaults(self):
        for bowl_id in range(1, self.BOWL_COUNT + 1):
            cfg = self.hardware.bowl_config(bowl_id)
            calibration = cfg.get("calibration", {})
            updates = {"name": cfg.get("name", f"Bowl {bowl_id}")}
            if calibration.get("resonance_hz") is not None:
                updates["resonance_frequency_hz"] = float(calibration["resonance_hz"])
                updates["frequency_hz"] = float(calibration["resonance_hz"])
            if calibration.get("preferred_drive") is not None:
                updates["amplitude"] = float(calibration["preferred_drive"])
            self.state.update(bowl_id, **updates)

    def _merge_hardware(self, bowl_id, state):
        cfg = self.hardware.bowl_config(bowl_id)
        profile = cfg["profile"]
        merged = deepcopy(state)
        merged["hardware"] = cfg
        # Compatibility aliases while older pages are phased out.
        merged["output_channel"] = cfg.get("driver_channel", "")
        merged["pickup_channel"] = f"{profile['feedback'].get('backend', '')} {cfg.get('feedback_channel', '')}".strip()
        merged["hardware_mode"] = profile.get("label", cfg.get("hardware_profile", ""))
        return merged

    def get_state(self, bowl_id=None):
        if bowl_id is not None:
            return self._merge_hardware(int(bowl_id), self.state.snapshot(bowl_id))
        return {
            key: self._merge_hardware(int(key), value)
            for key, value in self.state.snapshot().items()
        }

    def get_hardware_profiles(self):
        return self.hardware.profiles()

    def configure_hardware(self, bowl_id, **settings):
        bowl_id = int(bowl_id)
        cfg = self.hardware.update_bowl(bowl_id, **settings)
        updates = {"name": cfg.get("name", f"Bowl {bowl_id}")}
        calibration = cfg.get("calibration", {})
        if calibration.get("resonance_hz") is not None:
            updates["resonance_frequency_hz"] = float(calibration["resonance_hz"])
        self.state.update(bowl_id, **updates)
        return self.get_state(bowl_id)

    def configure_bowl(self, bowl_id, **settings):
        bowl_id = int(bowl_id)
        allowed = {
            "frequency_hz": float,
            "amplitude": float,
            "pattern": str,
            "waveform": str,
            "attack_s": float,
            "hold_s": float,
            "release_s": float,
            "rest_s": float,
            "repeats": int,
            "chirp_span_hz": float,
            "wah_depth_hz": float,
            "wah_rate_hz": float,
        }
        cleaned = {}
        for key, caster in allowed.items():
            if key in settings and settings[key] is not None:
                cleaned[key] = caster(settings[key])

        if "frequency_hz" in cleaned and not 10 <= cleaned["frequency_hz"] <= 5000:
            raise ValueError("Frequency must be 10-5000 Hz.")
        if "amplitude" in cleaned:
            max_drive = float(self.hardware.bowl_config(bowl_id).get("calibration", {}).get("max_drive", 0.10))
            if not 0 <= cleaned["amplitude"] <= max_drive:
                raise ValueError(f"Amplitude must be 0.0-{max_drive:g} for this bowl hardware configuration.")
        for key in ("attack_s", "hold_s", "release_s", "rest_s"):
            if key in cleaned and not 0 <= cleaned[key] <= 120:
                raise ValueError(f"{key} must be 0-120 seconds.")
        if "repeats" in cleaned and not 1 <= cleaned["repeats"] <= 100:
            raise ValueError("Repeats must be 1-100.")

        if any(k in cleaned for k in ("frequency_hz", "amplitude", "waveform")):
            self.audio[bowl_id].configure(
                frequency_hz=cleaned.get("frequency_hz"),
                amplitude=cleaned.get("amplitude"),
                waveform=cleaned.get("waveform"),
            )
        self.state.update(bowl_id, **cleaned)
        return self.get_state(bowl_id)

    def start_bowl(self, bowl_id):
        bowl_id = int(bowl_id)
        current = self.get_state(bowl_id)
        self.audio[bowl_id].configure(
            frequency_hz=current["frequency_hz"],
            amplitude=current["amplitude"],
            waveform=current["waveform"],
        )
        self.audio[bowl_id].start()
        self.state.update(bowl_id, output_running=True, system_status="RUNNING")
        return self.get_state(bowl_id)

    def stop_bowl(self, bowl_id):
        bowl_id = int(bowl_id)
        self.audio[bowl_id].stop()
        self.state.update(bowl_id, output_running=False, system_status="READY")
        return self.get_state(bowl_id)

    def stop_all(self):
        return {str(i): self.stop_bowl(i) for i in range(1, self.BOWL_COUNT + 1)}

    def configure_audio(self, **kwargs):
        return self.configure_bowl(1, **kwargs)

    def start_audio(self):
        return self.start_bowl(1)

    def stop_audio(self):
        return self.stop_bowl(1)
