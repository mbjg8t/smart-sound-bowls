import os
import subprocess
import tempfile
import wave

from app.hardware.alsa import ALSA


class INMP441:

    def __init__(self):
        self.device = None

    def discover(self):
        result = ALSA.capture_devices()

        devices = result["devices"]

        if len(devices) == 1:
            self.device = devices[0]["hw"]
            return devices[0]

        # We don't guess when multiple capture devices exist.
        self.device = None
        return None

    def status(self):
        result = ALSA.capture_devices()
        found = self.discover()

        return {
            "found": found is not None,
            "device": self.device,
            "details": found,
            "all_capture_devices": result["devices"],
        }

    def capture(
        self,
        duration_s=3,
        sample_rate=48000,
    ):
        device = self.discover()

        if device is None:
            raise RuntimeError(
                "No unambiguous ALSA capture device found. "
                "The INMP441 may still need device-tree configuration."
            )

        fd, filename = tempfile.mkstemp(
            prefix="sound_bowl_mic_",
            suffix=".wav",
        )

        os.close(fd)

        command = [
            "arecord",
            "-D",
            self.device,
            "-f",
            "S32_LE",
            "-r",
            str(sample_rate),
            "-c",
            "2",
            "-d",
            str(int(duration_s)),
            filename,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=duration_s + 10,
            )

            info = {
                "ok": result.returncode == 0,
                "device": self.device,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode == 0:
                info.update(
                    self._analyze_wav(filename)
                )

            return info

        finally:
            try:
                os.unlink(filename)
            except FileNotFoundError:
                pass

    def _analyze_wav(self, filename):
        with wave.open(filename, "rb") as wav:
            return {
                "channels": wav.getnchannels(),
                "sample_rate": wav.getframerate(),
                "sample_width_bytes": wav.getsampwidth(),
                "frames": wav.getnframes(),
                "duration_s": (
                    wav.getnframes()
                    / wav.getframerate()
                ),
            }
