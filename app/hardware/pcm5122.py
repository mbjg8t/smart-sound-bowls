import math
import os
import struct
import subprocess
import tempfile
import wave

from app.hardware.alsa import ALSA


class PCM5122:

    def __init__(self):
        self.device = None

    def discover(self):
        result = ALSA.playback_devices()

        devices = result["devices"]

        if not devices:
            self.device = None
            return None

        # Prefer devices whose name looks like PCM5122 / HiFi / DAC.
        preferred_terms = (
            "pcm5122",
            "pcm512x",
            "iqaudiodac",
            "iqaudio dac",
            "hifiberry",
            "sndrpihifiberry",
            "waveshare",
        )

        for device in devices:
            searchable = " ".join(
                [
                    device["card_id"],
                    device["card_name"],
                    device["device_id"],
                    device["device_name"],
                ]
            ).lower()

            if any(term in searchable for term in preferred_terms):
                self.device = device["hw"]
                return device

        # Do NOT silently pick the first playback device.
        self.device = None
        return None

    def status(self):
        found = self.discover()

        return {
            "found": found is not None,
            "device": self.device,
            "details": found,
        }

    def generate_test_wave(
        self,
        frequency_hz=220.0,
        amplitude=0.03,
        duration_s=2.0,
        sample_rate=48000,
    ):
        frequency_hz = float(frequency_hz)
        amplitude = float(amplitude)
        duration_s = float(duration_s)

        if not 10 <= frequency_hz <= 5000:
            raise ValueError("Test frequency must be 10-5000 Hz.")

        # Keep hardware test amplitude intentionally conservative.
        if not 0.0 < amplitude <= 0.10:
            raise ValueError(
                "Hardware test amplitude must be greater than 0 "
                "and no more than 0.10."
            )

        if not 0.1 <= duration_s <= 10.0:
            raise ValueError("Duration must be 0.1-10 seconds.")

        fd, filename = tempfile.mkstemp(
            prefix="sound_bowl_dac_",
            suffix=".wav",
        )

        os.close(fd)

        frames = int(sample_rate * duration_s)

        with wave.open(filename, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            for n in range(frames):
                value = amplitude * math.sin(
                    2.0
                    * math.pi
                    * frequency_hz
                    * n
                    / sample_rate
                )

                sample = int(
                    max(-1.0, min(1.0, value))
                    * 32767
                )

                # Duplicate mono test tone into L + R.
                wav.writeframesraw(
                    struct.pack("<hh", sample, sample)
                )

        return filename

    def test(
        self,
        frequency_hz=220.0,
        amplitude=0.03,
        duration_s=2.0,
    ):
        device = self.discover()

        if device is None:
            raise RuntimeError(
                "PCM5122 playback device was not automatically identified. "
                "Check /api/hardware/alsa before testing."
            )

        filename = self.generate_test_wave(
            frequency_hz=frequency_hz,
            amplitude=amplitude,
            duration_s=duration_s,
        )

        try:
            command = [
                "aplay",
                "-D",
                self.device,
                filename,
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
            )

            return {
                "ok": result.returncode == 0,
                "device": self.device,
                "command": " ".join(command),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        finally:
            try:
                os.unlink(filename)
            except FileNotFoundError:
                pass
