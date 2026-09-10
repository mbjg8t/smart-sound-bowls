#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SWEEP_SCRIPT = (
    REPO_ROOT / "tools" / "teensy_piezo_exciter_sweep.py"
)

SWEEP_RESULT = (
    REPO_ROOT / "results" / "teensy_piezo_exciter_sweep.csv"
)

COARSE_RESULT = (
    REPO_ROOT / "results" / "teensy_piezo_autotune_coarse.csv"
)

FINE_RESULT = (
    REPO_ROOT / "results" / "teensy_piezo_autotune_fine.csv"
)

FINAL_RESULT = (
    REPO_ROOT / "results" / "teensy_piezo_autotune.csv"
)


def load_rows(path):
    rows = []

    with path.open() as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append({
                "drive_hz": float(row["drive_hz"]),
                "piezo_freq_hz": (
                    float(row["piezo_freq_hz"])
                    if row["piezo_freq_hz"]
                    else None
                ),
                "confidence": (
                    float(row["confidence"])
                    if row["confidence"]
                    else None
                ),
                "median_p2p": float(row["median_p2p"]),
                "mean_p2p": float(row["mean_p2p"]),
                "max_p2p": int(float(row["max_p2p"])),
                "min_adc": int(float(row["min_adc"])),
                "max_adc": int(float(row["max_adc"])),
                "sample_count": int(float(row["sample_count"])),
            })

    return rows


def run_sweep(
    start,
    stop,
    step,
    amplitude,
    duration,
    save_as,
):
    cmd = [
        sys.executable,
        str(SWEEP_SCRIPT),
        "--start", str(start),
        "--stop", str(stop),
        "--step", str(step),
        "--amplitude", str(amplitude),
        "--duration", str(duration),
    ]

    print()
    print("=" * 66)
    print(
        f"RUNNING SWEEP {start:.2f}-{stop:.2f} Hz "
        f"step={step:g} "
        f"amplitude={amplitude * 100:.3f}%"
    )
    print("=" * 66)

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise RuntimeError("Sweep failed")

    if not SWEEP_RESULT.exists():
        raise RuntimeError(
            f"Sweep result not found: {SWEEP_RESULT}"
        )

    save_as.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        SWEEP_RESULT,
        save_as,
    )

    rows = load_rows(save_as)

    if not rows:
        raise RuntimeError("Sweep produced no data")

    return rows


def peak_row(rows):
    return max(
        rows,
        key=lambda r: r["median_p2p"],
    )


def clipped_near_peak(rows):
    peak = peak_row(rows)
    threshold = peak["median_p2p"] * 0.75

    for row in rows:
        if row["median_p2p"] < threshold:
            continue

        if (
            row["min_adc"] <= 0
            or row["max_adc"] >= 4095
        ):
            return True

    return False


def parabolic_peak(rows):
    rows = sorted(
        rows,
        key=lambda r: r["drive_hz"],
    )

    idx = max(
        range(len(rows)),
        key=lambda i: rows[i]["median_p2p"],
    )

    if idx == 0 or idx == len(rows) - 1:
        return rows[idx]["drive_hz"]

    left = rows[idx - 1]
    center = rows[idx]
    right = rows[idx + 1]

    y1 = left["median_p2p"]
    y2 = center["median_p2p"]
    y3 = right["median_p2p"]

    denominator = (
        y1
        - (2.0 * y2)
        + y3
    )

    if abs(denominator) < 1e-9:
        return center["drive_hz"]

    step = (
        right["drive_hz"]
        - center["drive_hz"]
    )

    offset = (
        0.5
        * (y1 - y3)
        / denominator
    )

    if offset < -1.0 or offset > 1.0:
        return center["drive_hz"]

    return (
        center["drive_hz"]
        + offset * step
    )


def save_final(rows):
    FINAL_RESULT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "drive_hz",
        "piezo_freq_hz",
        "confidence",
        "median_p2p",
        "mean_p2p",
        "max_p2p",
        "min_adc",
        "max_adc",
        "sample_count",
    ]

    with FINAL_RESULT.open(
        "w",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def hold_resonance(
    frequency,
    amplitude,
    duration,
):
    print()
    print("=" * 66)
    print(" RESONANCE HOLD")
    print("=" * 66)

    print(
        f"Frequency : {frequency:.3f} Hz"
    )

    print(
        f"Amplitude : {amplitude * 100:.3f}%"
    )

    print(
        f"Duration  : {duration:.2f} sec"
    )

    cmd = [
        sys.executable,
        str(
            REPO_ROOT
            / "tools"
            / "exciter_sweep.py"
        ),
        "--start", str(frequency),
        "--stop", str(frequency),
        "--step", "1",
        "--amplitude", str(amplitude),
        "--duration", str(duration),
        "--gap", "0",
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise RuntimeError(
            "Resonance hold failed"
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Automatic coarse/fine resonance finder "
            "for Teensy piezo + PCM5122 exciter"
        )
    )

    parser.add_argument(
        "--start",
        type=float,
        default=150.0,
    )

    parser.add_argument(
        "--stop",
        type=float,
        default=1200.0,
    )

    parser.add_argument(
        "--coarse-step",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--fine-span",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--fine-step",
        type=float,
        default=0.5,
    )

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.0015,
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=0.75,
    )

    parser.add_argument(
        "--min-amplitude",
        type=float,
        default=0.0005,
    )

    parser.add_argument(
        "--hold",
        type=float,
        default=0.0,
        help=(
            "After autotune, hold detected resonance "
            "for this many seconds"
        ),
    )

    parser.add_argument(
        "--hold-amplitude",
        type=float,
        default=None,
        help=(
            "DAC amplitude for final hold. "
            "Defaults to final sweep amplitude."
        ),
    )

    args = parser.parse_args()

    amplitude = args.amplitude

    # --------------------------------------------------
    # COARSE
    # --------------------------------------------------

    coarse = run_sweep(
        args.start,
        args.stop,
        args.coarse_step,
        amplitude,
        args.duration,
        COARSE_RESULT,
    )

    coarse_peak = peak_row(coarse)

    print()
    print(
        f"Coarse peak: "
        f"{coarse_peak['drive_hz']:.2f} Hz "
        f"P2P={coarse_peak['median_p2p']:.1f}"
    )

    # --------------------------------------------------
    # FINE
    # --------------------------------------------------

    fine_start = max(
        args.start,
        coarse_peak["drive_hz"]
        - args.fine_span,
    )

    fine_stop = min(
        args.stop,
        coarse_peak["drive_hz"]
        + args.fine_span,
    )

    fine = run_sweep(
        fine_start,
        fine_stop,
        args.fine_step,
        amplitude,
        args.duration,
        FINE_RESULT,
    )

    # --------------------------------------------------
    # AUTO REDUCE DRIVE IF CLIPPING
    # --------------------------------------------------

    while clipped_near_peak(fine):

        new_amplitude = amplitude * 0.6

        if new_amplitude < args.min_amplitude:
            print()
            print(
                "WARNING: clipping remains at "
                "minimum allowed amplitude."
            )
            break

        amplitude = new_amplitude

        print()
        print(
            "ADC clipping detected near resonance."
        )

        print(
            f"Reducing DAC amplitude to "
            f"{amplitude * 100:.3f}%"
        )

        fine = run_sweep(
            fine_start,
            fine_stop,
            args.fine_step,
            amplitude,
            args.duration,
            FINE_RESULT,
        )

    # --------------------------------------------------
    # FINAL
    # --------------------------------------------------

    peak = peak_row(fine)

    resonance_hz = parabolic_peak(
        fine
    )

    save_final(fine)

    print()
    print("=" * 66)
    print(" AUTOMATIC RESONANCE RESULT")
    print("=" * 66)

    print(
        f"Measured peak point     : "
        f"{peak['drive_hz']:.3f} Hz"
    )

    print(
        f"Interpolated resonance  : "
        f"{resonance_hz:.3f} Hz"
    )

    print(
        f"Peak median P2P         : "
        f"{peak['median_p2p']:.1f}"
    )

    if peak["piezo_freq_hz"] is not None:
        print(
            f"Piezo measured freq     : "
            f"{peak['piezo_freq_hz']:.3f} Hz"
        )

    print(
        f"Final DAC amplitude     : "
        f"{amplitude * 100:.3f}%"
    )

    print()
    print(f"Coarse CSV : {COARSE_RESULT}")
    print(f"Fine CSV   : {FINE_RESULT}")
    print(f"Final CSV  : {FINAL_RESULT}")

    # --------------------------------------------------
    # OPTIONAL RESONANCE HOLD
    # --------------------------------------------------

    if args.hold > 0:

        hold_amplitude = (
            args.hold_amplitude
            if args.hold_amplitude is not None
            else amplitude
        )

        hold_resonance(
            resonance_hz,
            hold_amplitude,
            args.hold,
        )


if __name__ == "__main__":
    main()
