#!/usr/bin/env python3

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app.hardware.alsa import ALSA


def print_devices(title, data):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)

    devices = data["devices"]

    if not devices:
        print("No devices found.")
        return

    for dev in devices:
        print(
            f"card={dev['card']} "
            f"device={dev['device']} "
            f"hw={dev['hw']}"
        )
        print(f"  card_id   : {dev['card_id']}")
        print(f"  card_name : {dev['card_name']}")
        print(f"  device_id : {dev['device_id']}")
        print(f"  device    : {dev['device_name']}")
        print()


def main():
    playback = ALSA.playback_devices()
    capture = ALSA.capture_devices()

    print_devices(
        "PLAYBACK DEVICES",
        playback,
    )

    print_devices(
        "CAPTURE DEVICES",
        capture,
    )


if __name__ == "__main__":
    main()
