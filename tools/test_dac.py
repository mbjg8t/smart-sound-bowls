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

from app.hardware.pcm5122 import PCM5122


def main():
    parser = argparse.ArgumentParser(
        description="Standalone PCM5122 DAC test"
    )

    parser.add_argument(
        "--frequency",
        type=float,
        default=220.0,
        help="Test tone frequency in Hz",
    )

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.02,
        help="Amplitude 0.0-0.10",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Duration in seconds",
    )

    args = parser.parse_args()

    dac = PCM5122()

    print()
    print("=" * 60)
    print("PCM5122 DAC TEST")
    print("=" * 60)

    status = dac.status()

    print()
    print("Discovery:")
    print(status)

    if not status["found"]:
        print()
        print("PCM5122 not identified.")
        print("Run:")
        print("  python tools/test_alsa.py")
        sys.exit(1)

    print()
    print(
        f"Playing {args.frequency:.2f} Hz "
        f"at {args.amplitude * 100:.1f}% "
        f"for {args.duration:.1f} sec"
    )

    result = dac.test(
        frequency_hz=args.frequency,
        amplitude=args.amplitude,
        duration_s=args.duration,
    )

    print()
    print("Result:")
    print(result)

    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
