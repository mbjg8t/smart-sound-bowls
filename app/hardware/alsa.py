import re
import subprocess


class ALSA:

    @staticmethod
    def _run(command):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    @classmethod
    def playback_devices(cls):
        result = cls._run(["aplay", "-l"])

        devices = []

        pattern = re.compile(
            r"card\s+(\d+):\s+([^\[]+)\[([^\]]+)\],\s+"
            r"device\s+(\d+):\s+([^\[]+)\[([^\]]+)\]"
        )

        for line in result["stdout"].splitlines():
            match = pattern.search(line)

            if match:
                devices.append({
                    "card": int(match.group(1)),
                    "card_id": match.group(2).strip(),
                    "card_name": match.group(3).strip(),
                    "device": int(match.group(4)),
                    "device_id": match.group(5).strip(),
                    "device_name": match.group(6).strip(),
                    "hw": f"hw:{match.group(1)},{match.group(4)}",
                })

        return {
            "devices": devices,
            "raw": result["stdout"] + result["stderr"],
        }

    @classmethod
    def capture_devices(cls):
        result = cls._run(["arecord", "-l"])

        devices = []

        pattern = re.compile(
            r"card\s+(\d+):\s+([^\[]+)\[([^\]]+)\],\s+"
            r"device\s+(\d+):\s+([^\[]+)\[([^\]]+)\]"
        )

        for line in result["stdout"].splitlines():
            match = pattern.search(line)

            if match:
                devices.append({
                    "card": int(match.group(1)),
                    "card_id": match.group(2).strip(),
                    "card_name": match.group(3).strip(),
                    "device": int(match.group(4)),
                    "device_id": match.group(5).strip(),
                    "device_name": match.group(6).strip(),
                    "hw": f"hw:{match.group(1)},{match.group(4)}",
                })

        return {
            "devices": devices,
            "raw": result["stdout"] + result["stderr"],
        }

    @classmethod
    def status(cls):
        return {
            "playback": cls.playback_devices(),
            "capture": cls.capture_devices(),
        }
