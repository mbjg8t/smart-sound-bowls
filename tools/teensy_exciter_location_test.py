#!/usr/bin/env python3

import argparse
import csv
import re
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import serial

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.hardware.pcm5122 import PCM5122


AUTOTUNE_SCRIPT = (
    REPO_ROOT / "tools" / "teensy_piezo_autotune.py"
)

AUTOTUNE_FINE = (
    REPO_ROOT / "results" / "teensy_piezo_autotune_fine.csv"
)

RESULTS_DIR = REPO_ROOT / "results" / "exciter_location_tests"

SUMMARY_FILE = (
    RESULTS_DIR / "exciter_location_summary.csv"
)


LINE_RE = re.compile(
    r"min=(?P<min>\d+)\s+"
    r"max=(?P<max>\d+)\s+"
    r"mean=(?P<mean>[\d.]+)\s+"
    r"p2p=(?P<p2p>\d+)"
    r"(?:\s+freq=(?P<freq>[\d.]+)Hz"
    r"\s+conf=(?P<conf>[\d.]+))?"
)


def sanitize_label(label):
    return re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        label.strip(),
    )


def parse_teensy_line(line):
    match = LINE_RE.search(line)

    if not match:
        return None

    return {
        "min_adc": int(match.group("min")),
        "max_adc": int(match.group("max")),
        "mean_adc": float(match.group("mean")),
        "p2p": int(match.group("p2p")),
        "frequency_hz": (
            float(match.group("freq"))
            if match.group("freq")
            else None
        ),
        "confidence": (
            float(match.group("conf"))
            if match.group("conf")
            else None
        ),
    }


def load_sweep_rows(path):
    rows = []

    with path.open() as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append({
                "drive_hz": float(row["drive_hz"]),
                "median_p2p": float(row["median_p2p"]),
            })

    return rows


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
        - 2.0 * y2
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


def run_autotune(args):
    cmd = [
        sys.executable,
        str(AUTOTUNE_SCRIPT),

        "--start",
        str(args.start),

        "--stop",
        str(args.stop),

        "--coarse-step",
        str(args.coarse_step),

        "--fine-span",
        str(args.fine_span),

        "--fine-step",
        str(args.fine_step),

        "--amplitude",
        str(args.sweep_amplitude),

        "--duration",
        str(args.sweep_duration),
    ]

    print()
    print("=" * 72)
    print(" AUTOTUNE")
    print("=" * 72)

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise RuntimeError("Autotune failed")

    if not AUTOTUNE_FINE.exists():
        raise RuntimeError(
            f"Autotune output not found: {AUTOTUNE_FINE}"
        )

    rows = load_sweep_rows(
        AUTOTUNE_FINE
    )

    if not rows:
        raise RuntimeError(
            "Autotune fine sweep contained no data"
        )

    resonance = parabolic_peak(rows)

    peak = max(
        rows,
        key=lambda r: r["median_p2p"],
    )

    return resonance, peak["median_p2p"]


def read_for_duration(
    ser,
    duration,
    phase,
    start_time,
):
    samples = []

    end_time = time.monotonic() + duration

    while time.monotonic() < end_time:

        line = ser.readline().decode(
            "utf-8",
            errors="ignore",
        ).strip()

        sample = parse_teensy_line(line)

        if sample is None:
            continue

        sample["phase"] = phase
        sample["time_s"] = (
            time.monotonic() - start_time
        )
        sample["ringdown_s"] = ""

        samples.append(sample)

    return samples


def measure_drive_and_ringdown(
    ser,
    dac,
    resonance_hz,
    amplitude,
    drive_time,
    ringdown_time,
    baseline_time,
):
    all_samples = []

    print()
    print("=" * 72)
    print(" BASELINE")
    print("=" * 72)

    ser.reset_input_buffer()

    overall_start = time.monotonic()

    baseline_samples = read_for_duration(
        ser,
        baseline_time,
        "baseline",
        overall_start,
    )

    all_samples.extend(
        baseline_samples
    )

    print()
    print("=" * 72)
    print(" DRIVE + RINGDOWN")
    print("=" * 72)

    print(
        f"Frequency : {resonance_hz:.3f} Hz"
    )

    print(
        f"Amplitude : {amplitude * 100:.4f}%"
    )

    print(
        f"Drive     : {drive_time:.2f} sec"
    )

    print(
        f"Ringdown  : {ringdown_time:.2f} sec"
    )

    ser.reset_input_buffer()

    state = {
        "tone_done": None,
        "error": None,
    }

    def play():
        try:
            dac.test(
                frequency_hz=resonance_hz,
                amplitude=amplitude,
                duration_s=drive_time,
            )
        except Exception as exc:
            state["error"] = exc
        finally:
            state["tone_done"] = (
                time.monotonic()
            )

    tone_thread = threading.Thread(
        target=play,
        daemon=True,
    )

    drive_start = time.monotonic()

    tone_thread.start()

    while True:

        now = time.monotonic()

        if (
            state["tone_done"] is not None
            and
            now - state["tone_done"]
            >= ringdown_time
        ):
            break

        line = ser.readline().decode(
            "utf-8",
            errors="ignore",
        ).strip()

        sample = parse_teensy_line(line)

        if sample is None:
            continue

        now = time.monotonic()

        if state["tone_done"] is None:
            phase = "drive"
            ringdown_s = ""
        else:
            phase = "ringdown"
            ringdown_s = (
                now - state["tone_done"]
            )

        sample["phase"] = phase
        sample["time_s"] = (
            now - overall_start
        )
        sample["ringdown_s"] = (
            ringdown_s
        )

        all_samples.append(sample)

    tone_thread.join()

    if state["error"] is not None:
        raise state["error"]

    return all_samples


def median_or_none(values):
    if not values:
        return None

    return statistics.median(values)


def sustained_crossing_time(
    ringdown_samples,
    threshold,
    consecutive=3,
):
    count = 0

    for sample in ringdown_samples:

        if sample["p2p"] <= threshold:
            count += 1
        else:
            count = 0

        if count >= consecutive:
            return float(
                ringdown_samples[
                    ringdown_samples.index(sample)
                    - consecutive
                    + 1
                ]["ringdown_s"]
            )

    return None


def analyze(samples):
    baseline = [
        s
        for s in samples
        if s["phase"] == "baseline"
    ]

    drive = [
        s
        for s in samples
        if s["phase"] == "drive"
    ]

    ringdown = [
        s
        for s in samples
        if s["phase"] == "ringdown"
    ]

    baseline_p2p = median_or_none([
        s["p2p"]
        for s in baseline
    ])

    drive_p2p = median_or_none([
        s["p2p"]
        for s in drive
    ])

    drive_max = (
        max(s["p2p"] for s in drive)
        if drive
        else None
    )

    drive_freq = median_or_none([
        s["frequency_hz"]
        for s in drive
        if s["frequency_hz"] is not None
    ])

    clipped = any(
        (
            s["min_adc"] <= 0
            or s["max_adc"] >= 4095
        )
        for s in drive
    )

    initial_ring = None

    early_ring = [
        s["p2p"]
        for s in ringdown
        if (
            s["ringdown_s"] != ""
            and float(s["ringdown_s"]) <= 0.50
        )
    ]

    if early_ring:
        initial_ring = max(early_ring)

    t50 = None
    t37 = None
    t20 = None

    if (
        baseline_p2p is not None
        and initial_ring is not None
        and initial_ring > baseline_p2p
    ):

        excess = (
            initial_ring
            - baseline_p2p
        )

        threshold_50 = (
            baseline_p2p
            + 0.50 * excess
        )

        threshold_37 = (
            baseline_p2p
            + 0.368 * excess
        )

        threshold_20 = (
            baseline_p2p
            + 0.20 * excess
        )

        t50 = sustained_crossing_time(
            ringdown,
            threshold_50,
        )

        t37 = sustained_crossing_time(
            ringdown,
            threshold_37,
        )

        t20 = sustained_crossing_time(
            ringdown,
            threshold_20,
        )

    return {
        "baseline_p2p": baseline_p2p,
        "drive_median_p2p": drive_p2p,
        "drive_max_p2p": drive_max,
        "drive_measured_hz": drive_freq,
        "initial_ringdown_p2p": initial_ring,
        "t50_s": t50,
        "t37_s": t37,
        "t20_s": t20,
        "adc_clipped": clipped,
    }


def save_samples(
    path,
    samples,
):
    fieldnames = [
        "phase",
        "time_s",
        "ringdown_s",
        "p2p",
        "min_adc",
        "max_adc",
        "mean_adc",
        "frequency_hz",
        "confidence",
    ]

    with path.open(
        "w",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for sample in samples:
            writer.writerow(sample)


def append_summary(
    label,
    exciter,
    location,
    resonance_hz,
    sweep_peak_p2p,
    amplitude,
    analysis,
):
    fieldnames = [
        "label",
        "exciter",
        "location",
        "resonance_hz",
        "sweep_peak_p2p",
        "drive_amplitude",
        "baseline_p2p",
        "drive_median_p2p",
        "drive_max_p2p",
        "drive_measured_hz",
        "initial_ringdown_p2p",
        "t50_s",
        "t37_s",
        "t20_s",
        "adc_clipped",
    ]

    row = {
        "label": label,
        "exciter": exciter,
        "location": location,
        "resonance_hz": resonance_hz,
        "sweep_peak_p2p": sweep_peak_p2p,
        "drive_amplitude": amplitude,
        **analysis,
    }

    exists = SUMMARY_FILE.exists()

    with SUMMARY_FILE.open(
        "a",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def fmt(value, digits=2):
    if value is None:
        return "---"

    return f"{value:.{digits}f}"


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare exciter mounting locations using "
            "automatic resonance tuning and ringdown."
        )
    )

    parser.add_argument(
        "--label",
        required=True,
    )

    parser.add_argument(
        "--exciter",
        default="unknown",
    )

    parser.add_argument(
        "--location",
        default="unknown",
    )

    parser.add_argument(
        "--start",
        type=float,
        default=450.0,
    )

    parser.add_argument(
        "--stop",
        type=float,
        default=600.0,
    )

    parser.add_argument(
        "--coarse-step",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--fine-span",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--fine-step",
        type=float,
        default=0.25,
    )

    parser.add_argument(
        "--sweep-amplitude",
        type=float,
        default=0.0015,
    )

    parser.add_argument(
        "--sweep-duration",
        type=float,
        default=0.75,
    )

    parser.add_argument(
        "--drive-amplitude",
        type=float,
        default=0.0015,
    )

    parser.add_argument(
        "--drive-time",
        type=float,
        default=2.0,
    )

    parser.add_argument(
        "--ringdown-time",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--baseline-time",
        type=float,
        default=1.0,
    )

    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
    )

    args = parser.parse_args()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    label = sanitize_label(
        args.label
    )

    sample_file = (
        RESULTS_DIR
        / f"{label}.csv"
    )

    print()
    print("=" * 72)
    print(" SMART SOUND BOWL - EXCITER LOCATION TEST")
    print("=" * 72)

    print(f"Label       : {label}")
    print(f"Exciter     : {args.exciter}")
    print(f"Location    : {args.location}")

    resonance_hz, sweep_peak_p2p = (
        run_autotune(args)
    )

    dac = PCM5122()

    ser = serial.Serial(
        args.port,
        args.baud,
        timeout=0.12,
    )

    time.sleep(0.5)

    try:
        samples = measure_drive_and_ringdown(
            ser=ser,
            dac=dac,
            resonance_hz=resonance_hz,
            amplitude=args.drive_amplitude,
            drive_time=args.drive_time,
            ringdown_time=args.ringdown_time,
            baseline_time=args.baseline_time,
        )

    finally:
        ser.close()

    analysis = analyze(samples)

    save_samples(
        sample_file,
        samples,
    )

    append_summary(
        label=label,
        exciter=args.exciter,
        location=args.location,
        resonance_hz=resonance_hz,
        sweep_peak_p2p=sweep_peak_p2p,
        amplitude=args.drive_amplitude,
        analysis=analysis,
    )

    print()
    print("=" * 72)
    print(" LOCATION TEST RESULT")
    print("=" * 72)

    print(
        f"Resonance            : "
        f"{resonance_hz:.3f} Hz"
    )

    print(
        f"Sweep peak P2P        : "
        f"{sweep_peak_p2p:.1f}"
    )

    print(
        f"Baseline P2P          : "
        f"{fmt(analysis['baseline_p2p'], 1)}"
    )

    print(
        f"Driven median P2P     : "
        f"{fmt(analysis['drive_median_p2p'], 1)}"
    )

    print(
        f"Driven max P2P        : "
        f"{fmt(analysis['drive_max_p2p'], 1)}"
    )

    print(
        f"Measured driven freq  : "
        f"{fmt(analysis['drive_measured_hz'], 2)} Hz"
    )

    print(
        f"Initial ringdown P2P  : "
        f"{fmt(analysis['initial_ringdown_p2p'], 1)}"
    )

    print(
        f"Decay to 50%          : "
        f"{fmt(analysis['t50_s'], 2)} sec"
    )

    print(
        f"Decay to 36.8%        : "
        f"{fmt(analysis['t37_s'], 2)} sec"
    )

    print(
        f"Decay to 20%          : "
        f"{fmt(analysis['t20_s'], 2)} sec"
    )

    print(
        f"ADC clipped           : "
        f"{analysis['adc_clipped']}"
    )

    print()
    print(f"Raw CSV     : {sample_file}")
    print(f"Summary CSV : {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
