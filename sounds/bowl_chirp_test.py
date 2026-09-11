#!/usr/bin/env python3

import argparse
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Sweep bowl strike rest time from 0.05 to 1.0 seconds"
    )

    parser.add_argument(
        "--max-percent",
        type=float,
        default=0.05,
        help="Maximum DAC output percent. Default: 0.05%%",
    )

    parser.add_argument(
        "--on-time",
        type=float,
        default=0.50,
        help="Excitation time for each strike. Default: 0.50 sec",
    )

    parser.add_argument(
        "--test-duration",
        type=float,
        default=10.0,
        help="Duration of each rest-time test. Default: 10 sec",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=1.0,
        help="Pause between test sections. Default: 1 sec",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    wawa_script = script_dir / "bowl_wawa_test.py"

    separations = [
        0.05,
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.40,
        0.50,
        0.60,
        0.75,
        1.00,
    ]

    print()
    print("=" * 68)
    print(" BOWL CHIRP TEST")
    print("=" * 68)
    print(f"Maximum drive : {args.max_percent:.4f}%")
    print(f"Excitation    : {args.on_time:.3f} sec")
    print(f"Each section  : {args.test_duration:.1f} sec")
    print("=" * 68)

    for i, rest in enumerate(separations, start=1):

        print()
        print(
            f"[{i}/{len(separations)}] "
            f"REST TIME = {rest:.3f} sec"
        )

        cmd = [
            "python",
            str(wawa_script),
            "--max-percent", str(args.max_percent),
            "--rest-time", str(rest),
            "--on-time", str(args.on_time),
            "--duration", str(args.test_duration),
        ]

        result = subprocess.run(cmd)

        if result.returncode != 0:
            raise SystemExit(result.returncode)

        if i < len(separations):
            time.sleep(args.pause)


if __name__ == "__main__":
    main()
