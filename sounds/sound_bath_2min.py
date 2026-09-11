#!/usr/bin/env python3

import argparse
import subprocess
import sys

import numpy as np


SAMPLE_RATE = 48000


def smooth_transition(start, end, samples):
    """Raised-cosine transition with zero slope at both ends."""
    if samples <= 0:
        return np.empty(0, dtype=np.float64)

    x = np.linspace(0.0, 1.0, samples, endpoint=False)
    blend = 0.5 - 0.5 * np.cos(np.pi * x)

    return start + (end - start) * blend


def hold_level(level, samples):
    return np.full(samples, level, dtype=np.float64)


def main():
    parser = argparse.ArgumentParser(
        description="2-minute resonance-locked sound-bowl capability demo"
    )

    parser.add_argument("--device", default="hw:3,1")
    parser.add_argument("--frequency", type=float, default=528.7)

    parser.add_argument(
        "--max-percent",
        type=float,
        default=0.10,
        help="Maximum DAC output in percent. Example: 0.10 = 0.10%%",
    )

    args = parser.parse_args()

    max_amp = args.max_percent / 100.0

    # ------------------------------------------------------------
    # PERFORMANCE SCORE
    #
    # mode:
    #   ramp = smooth raised-cosine transition
    #   hold = maintain target intensity
    #   off  = electrical drive completely removed
    #
    # Levels are fractions of --max-percent.
    #
    # Frequency NEVER changes.
    # Oscillator phase continues running even while drive = 0.
    #
    # Total = 120 seconds.
    # ------------------------------------------------------------

    score = [
        # mode    duration   target
        #
        # Resonance remains FIXED.
        #
        # First section deliberately explores electrical ON/OFF
        # excitation and natural mechanical ringdown.
        #
        # Total = 120 seconds.

        # --------------------------------------------------------
        # STRIKE / RINGDOWN EXPERIMENT
        # --------------------------------------------------------

        ("ramp",    1.0,     0.45),   # small quick strike
        ("off",     0.750,   0.00),

        ("ramp",    0.7,     0.70),   # harder strike
        ("off",     0.825,   0.00),

        ("ramp",    0.5,     1.00),   # near-full strike
        ("off",     1.000,   0.00),

        # Repeated short excitation
        ("ramp",    0.5,     0.60),
        ("off",     0.375,   0.00),

        ("ramp",    0.5,     0.75),
        ("off",     0.375,   0.00),

        ("ramp",    0.5,     0.90),
        ("off",     0.625,   0.00),

        # Full-on / full-off behavior
        ("ramp",    0.4,     1.00),
        ("hold",    1.6,     1.00),
        ("off",     3.0,     0.00),

        ("ramp",    0.4,     1.00),
        ("hold",    3.0,     1.00),
        ("off",     4.0,     0.00),

        # --------------------------------------------------------
        # ACTIVE PERFORMANCE SECTION
        # --------------------------------------------------------

        ("ramp",    3.0,     0.50),
        ("ramp",    2.0,     0.82),
        ("ramp",    4.0,     0.35),

        ("ramp",    2.0,     0.95),
        ("hold",    3.0,     0.95),
        ("ramp",    5.0,     0.45),

        ("ramp",    2.5,     0.75),
        ("ramp",    2.5,     0.40),
        ("ramp",    2.0,     0.88),
        ("ramp",    4.0,     0.30),

        # Small strike emerging from an already active bowl
        ("ramp",    1.0,     0.85),
        ("off",     3.0,     0.00),

        # --------------------------------------------------------
        # BIGGER SUSTAINED SWELLS
        # --------------------------------------------------------

        ("ramp",    4.0,     0.55),
        ("ramp",    3.0,     1.00),
        ("hold",    4.0,     1.00),
        ("ramp",    5.0,     0.50),

        ("ramp",    2.0,     0.80),
        ("ramp",    3.0,     0.35),
        ("ramp",    2.0,     0.70),
        ("ramp",    4.0,     0.25),

        # Final strike and natural decay
        ("ramp",    0.6,     1.00),
        ("off",     5.4,     0.00),

        # Gentle ending
        ("ramp",    3.0,     0.40),
        ("ramp",    5.0,     0.00),
    ]

    total_seconds = sum(duration for _, duration, _ in score)

    envelope_parts = []
    current_fraction = 0.0

    print()
    print("=" * 76)
    print(" SMART SOUND BOWL - RESONANCE-LOCKED CAPABILITY DEMO")
    print("=" * 76)
    print(f"Device          : {args.device}")
    print(f"Frequency       : {args.frequency:.3f} Hz  [FIXED]")
    print(f"Maximum drive   : {args.max_percent:.4f}%")
    print(f"Duration        : {total_seconds:.1f} sec")
    print(f"PCM             : 32-bit / {SAMPLE_RATE} Hz")
    print()

    elapsed = 0.0

    for mode, duration, target_fraction in score:
        samples = int(round(duration * SAMPLE_RATE))

        if mode == "ramp":
            part = smooth_transition(
                current_fraction * max_amp,
                target_fraction * max_amp,
                samples,
            )

        elif mode == "hold":
            part = hold_level(
                target_fraction * max_amp,
                samples,
            )

        elif mode == "gate":
            # Immediate electrical ON at target amplitude.
            # No attack envelope.
            part = hold_level(
                target_fraction * max_amp,
                samples,
            )

        elif mode == "off":
            # Immediate electrical OFF.
            part = hold_level(0.0, samples)

        else:
            raise ValueError(f"Unknown mode: {mode}")

        envelope_parts.append(part)

        start_time = elapsed
        elapsed += duration

        if mode == "off":
            description = "DRIVE OFF - NATURAL RINGDOWN"
        elif mode == "hold":
            description = f"HOLD {target_fraction * 100:5.1f}%"
        else:
            description = (
                f"{current_fraction * 100:5.1f}%"
                f" -> {target_fraction * 100:5.1f}%"
            )

        print(
            f"{start_time:6.1f}-{elapsed:6.1f} sec   "
            f"{mode.upper():4s}   {description}"
        )

        current_fraction = target_fraction

    envelope = np.concatenate(envelope_parts)

    # ------------------------------------------------------------
    # ONE CONTINUOUS OSCILLATOR
    #
    # Frequency and phase never reset.
    #
    # During an OFF section the oscillator mathematically continues,
    # but its gain is exactly zero.
    # ------------------------------------------------------------

    sample_count = len(envelope)

    phase_increment = (
        2.0 * np.pi * args.frequency / SAMPLE_RATE
    )

    phase = (
        np.arange(sample_count, dtype=np.float64)
        * phase_increment
    )

    signal = np.sin(phase) * envelope

    # 32-bit signed PCM.
    scale = 2147483647.0

    mono = np.clip(
        signal * scale,
        -2147483648,
        2147483647
    ).astype("<i4")

    stereo = np.column_stack((mono, mono)).reshape(-1)

    print()
    print("=" * 76)
    print("Starting performance...")
    print("=" * 76)
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

    process = None

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE
        )

        process.stdin.write(stereo.tobytes())
        process.stdin.close()

        return_code = process.wait()

        if return_code != 0:
            sys.exit(return_code)

    except KeyboardInterrupt:
        print("\nPerformance stopped.")

        if process is not None and process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    main()
