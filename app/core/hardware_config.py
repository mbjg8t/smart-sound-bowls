import json
from copy import deepcopy
from pathlib import Path
from threading import Lock


class HardwareConfigStore:
    """Persisted bowl-to-hardware mapping, intentionally independent of Flask/UI."""

    def __init__(self, config_dir=None):
        root = Path(__file__).resolve().parents[2]
        self.config_dir = Path(config_dir) if config_dir else root / "config"
        self.profiles_path = self.config_dir / "hardware_profiles.json"
        self.bowls_path = self.config_dir / "bowls.json"
        self._lock = Lock()
        self._profiles = self._load_json(self.profiles_path)
        self._bowls = self._load_json(self.bowls_path)

    @staticmethod
    def _load_json(path):
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _write_json(path, value):
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=False)
            fh.write("\n")
        tmp.replace(path)

    def profiles(self):
        with self._lock:
            return deepcopy(self._profiles)

    def bowl_config(self, bowl_id):
        key = str(int(bowl_id))
        with self._lock:
            if key not in self._bowls:
                raise KeyError(f"Unknown bowl: {bowl_id}")
            assignment = deepcopy(self._bowls[key])
            profile_name = assignment["hardware_profile"]
            if profile_name not in self._profiles:
                raise KeyError(f"Unknown hardware profile: {profile_name}")
            return self._compose(assignment, self._profiles[profile_name])

    def all_bowls(self):
        with self._lock:
            return {
                key: self._compose(deepcopy(assignment), self._profiles[assignment["hardware_profile"]])
                for key, assignment in self._bowls.items()
            }

    @staticmethod
    def _compose(assignment, profile):
        return {
            **assignment,
            "profile": deepcopy(profile),
        }

    def update_bowl(self, bowl_id, **changes):
        key = str(int(bowl_id))
        with self._lock:
            if key not in self._bowls:
                raise KeyError(f"Unknown bowl: {bowl_id}")
            assignment = self._bowls[key]

            if "hardware_profile" in changes:
                profile_name = str(changes["hardware_profile"])
                if profile_name not in self._profiles:
                    raise ValueError(f"Unknown hardware profile: {profile_name}")
                assignment["hardware_profile"] = profile_name

            for field in ("name", "driver_channel", "feedback_channel", "notes"):
                if field in changes:
                    assignment[field] = str(changes[field])

            if "calibration" in changes:
                calibration = changes["calibration"] or {}
                current = assignment.setdefault("calibration", {})
                for field in ("resonance_hz", "preferred_drive", "max_drive", "feedback_scale"):
                    if field in calibration:
                        value = calibration[field]
                        current[field] = None if value in (None, "") and field == "resonance_hz" else float(value)

            self._write_json(self.bowls_path, self._bowls)
            return self._compose(deepcopy(assignment), self._profiles[assignment["hardware_profile"]])
