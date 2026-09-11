#!/usr/bin/env python3

import argparse
import subprocess
import numpy as np


SAMPLE_RATE = 48000


def smooth_transition(start, end, samples):
    if samples <= 0:
        return np.empty(0, dtype=np.float64)

    x = np.linspace(0.0, 1.0, samples, endpoint=False)
    blend = 0.5 - 0.5 * np.cos(np.pi * x)

    return start + (end - start) * blend


def main():
    parser = argparse.ArgumentParser(
        description="Repeated resonant excitation / natural ringdown test"
    )

    parser.add_argument(
        "--device",
        default="hw:3,1",
    )

    parser.add_argument(
        "--frequency",
        type=float,
        default=528.7,
    )

    parser.add_argument(
        "--max-percent",
        type=float,
        default=0.05,
        help="Maximum excitation intensity in DAC percent. Default: 0.05%%",
    )

    parser.add_argument(
        "--rest-time",
        type=float,
        default=0.40,
        help="Natural ringdown/rest time between excitations. Default: 0.40 sec",
    )

    parser.add_argument(
        "--on-time",
        type=float,
        default=0.50,
        help="Excitation duration. Default: 0.50 sec",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Total test duration. Default: 10 sec",
    )

    args = parser.parse_args()

    max_amp = args.max_percent / 100.0

    total_samples = int(args.duration * SAMPLE_RATE)
    on_samples = max(1, int(args.on_time * SAMPLE_RATE))
    rest_samples = max(1, int(args.rest_time * SAMPLE_RATE))

    envelope = np.zeros(total_samples, dtype=np.float64)

    position = 0
    strikes = 0

    while position < total_samples:

        # Excite bowl from zero to selected MAX intensity.
        n = min(on_samples, total_samples - position)

        envelope[position:position + n] = smooth_transition(
            0.0,
            max_amp,
            n,
        )

        position += n
        strikes += 1

        # Immediately remove drive.
        # Bowl rings naturally during this interval.
        position += min(
            rest_samples,
            max(0, total_samples - position),
        )

    # Fixed resonant oscillator.
    # Frequency NEVER changes.
    phase_increment = (
        2.0 * np.pi * args.frequency / SAMPLE_RATE
    )

    phase = (
        np.arange(total_samples, dtype=np.float64)
        * phase_increment
    )

    signal = np.sin(phase) * envelope

    mono = np.clip(
        signal * 2147483647.0,
        -2147483648,
        2147483647,
    ).astype("<i4")

    stereo = np.column_stack((mono, mono)).reshape(-1)

    print()
    print("=" * 64)
    print(" BOWL WAWA TEST")
    print("=" * 64)
    print(f"Frequency       : {args.frequency:.3f} Hz")
    print(f"Max intensity   : {args.max_percent:.4f}%")
    print(f"Excitation time : {args.on_time:.3f} sec")
    print(f"Rest time       : {args.rest_time:.3f} sec")
    print(f"Duration        : {args.duration:.1f} sec")
    print(f"Excitations     : {strikes}")
    print("=" * 64)
    print()

    cmd = [
        "aplay",
        "-q",
        "-D", args.device,
        "-t", "raw",
        "-f", "S32_LE",
        "-r", str(SAMPLE_RATE),
        "-c", "2",
    ]

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
    )

    try:
        process.stdin.write(stereo.tobytes())
        process.stdin.close()
        process.wait()

    except KeyboardInterrupt:
        print("\nStopped.")
        process.terminate()


if __name__ == "__main__":
    main()
