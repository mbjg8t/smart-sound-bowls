#!/usr/bin/env python3

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.hardware.pcm5122 import PCM5122


def main():
    parser = argparse.ArgumentParser(
        description="Exciter-only frequency sweep"
    )

    parser.add_argument("--start", type=float, default=450.0)
    parser.add_argument("--stop", type=float, default=600.0)
    parser.add_argument("--step", type=float, default=5.0)
    parser.add_argument("--amplitude", type=float, default=0.005)
    parser.add_argument("--duration", type=float, default=0.65)
    parser.add_argument("--gap", type=float, default=0.05)

    args = parser.parse_args()

    dac = PCM5122()
    status = dac.status()

    if not status["found"]:
        raise SystemExit("PCM5122 DAC not found")

    print()
    print("=" * 55)
    print(" EXCITER SWEEP")
    print("=" * 55)
    print(f"Device    : {status['device']}")
    print(f"Range     : {args.start:.1f} - {args.stop:.1f} Hz")
    print(f"Step      : {args.step:.1f} Hz")
    print(f"Amplitude : {args.amplitude * 100:.2f}%")
    print(f"Duration  : {args.duration:.2f} sec/step")
    print()

    frequency = args.start

    try:
        while frequency <= args.stop + 0.0001:

            print(
                f"DRIVE {frequency:7.1f} Hz   "
                f"{args.amplitude * 100:.2f}%",
                flush=True,
            )

            result = dac.test(
                frequency_hz=frequency,
                amplitude=args.amplitude,
                duration_s=args.duration,
            )

            if not result["ok"]:
                print(result["stderr"])
                raise SystemExit(
                    f"Playback failed at {frequency:.1f} Hz"
                )

            time.sleep(args.gap)
            frequency += args.step

    except KeyboardInterrupt:
        print("\nSweep stopped.")

    print()
    print("Sweep complete.")


if __name__ == "__main__":
    main()
