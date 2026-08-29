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


import argparse
import sys

from app.hardware.inmp441 import INMP441


def main():
    parser = argparse.ArgumentParser(
        description="Standalone INMP441 microphone test"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=3,
        help="Capture duration in seconds",
    )

    args = parser.parse_args()

    mic = INMP441()

    print()
    print("=" * 60)
    print("INMP441 MICROPHONE TEST")
    print("=" * 60)

    status = mic.status()

    print()
    print("Discovery:")
    print(status)

    if not status["found"]:
        print()
        print("No unambiguous capture device found.")
        print("Run:")
        print("  python tools/test_alsa.py")
        sys.exit(1)

    print()
    print(
        f"Recording for {args.duration} seconds..."
    )

    result = mic.capture(
        duration_s=args.duration,
    )

    print()
    print("Result:")
    print(result)

    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
