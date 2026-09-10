#!/usr/bin/env python3

import argparse
import math
import subprocess
import sys

import numpy as np


SAMPLE_RATE = 48000


def raised_cosine(start, end, samples):
    """
    Smooth transition with zero slope at both ends.
    """
    if samples <= 0:
        return np.empty(0, dtype=np.float64)

    x = np.linspace(0.0, 1.0, samples, endpoint=False)
    blend = 0.5 - 0.5 * np.cos(np.pi * x)
    return start + (end - start) * blend


def constant(value, samples):
    return np.full(samples, value, dtype=np.float64)


def seconds_to_samples(seconds):
    return int(round(seconds * SAMPLE_RATE))


def main():
    parser = argparse.ArgumentParser(
        description="Smooth continuous sound-bowl amplitude experiment"
    )

    parser.add_argument("--device", default="hw:3,1")
    parser.add_argument("--frequency", type=float, default=528.7)

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.0010,
        help="Peak DAC amplitude, 0.001 = 0.1%%",
    )

    parser.add_argument("--attack", type=float, default=6.0)
    parser.add_argument("--hold", type=float, default=3.0)
    parser.add_argument("--release", type=float, default=8.0)

    args = parser.parse_args()

    attack_n = seconds_to_samples(args.attack)
    hold_n = seconds_to_samples(args.hold)
    release_n = seconds_to_samples(args.release)

    envelope = np.concatenate(
        [
            raised_cosine(0.0, args.amplitude, attack_n),
            constant(args.amplitude, hold_n),
            raised_cosine(args.amplitude, 0.0, release_n),
        ]
    )

    total_samples = len(envelope)
    duration = total_samples / SAMPLE_RATE

    # Continuous oscillator: phase NEVER resets during amplitude changes.
    t = np.arange(total_samples, dtype=np.float64) / SAMPLE_RATE
    signal = np.sin(2.0 * np.pi * args.frequency * t)

    signal *= envelope

    # Use 32-bit PCM so tiny amplitudes have vastly better resolution
    # than our existing 16-bit WAV test path.
    scale = 2147483647.0
    mono = np.clip(signal * scale, -2147483648, 2147483647).astype("<i4")

    # Same signal to L/R channels.
    stereo = np.column_stack((mono, mono)).reshape(-1)

    print()
    print("=" * 70)
    print(" SMOOTH SOUND BOWL DRIVE")
    print("=" * 70)
    print(f"Device       : {args.device}")
    print(f"Frequency    : {args.frequency:.3f} Hz")
    print(f"Peak level   : {args.amplitude * 100:.4f}%")
    print(f"Attack       : {args.attack:.2f} sec")
    print(f"Hold         : {args.hold:.2f} sec")
    print(f"Release      : {args.release:.2f} sec")
    print(f"Total        : {duration:.2f} sec")
    print(f"PCM          : 32-bit / {SAMPLE_RATE} Hz")
    print("=" * 70)
    print()

    cmd = [
        "aplay",
        "-q",
        "-D",
        args.device,
        "-t",
        "raw",
        "-f",
        "S32_LE",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        "2",
    ]

    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        process.stdin.write(stereo.tobytes())
        process.stdin.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"aplay exited with status {return_code}")
            sys.exit(return_code)

    except BrokenPipeError:
        print("Audio device rejected S32_LE.")
        print("Run: aplay --dump-hw-params -D hw:3,1 /dev/zero")
        sys.exit(1)
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
        print("\nStopped.")


if __name__ == "__main__":
    main()
