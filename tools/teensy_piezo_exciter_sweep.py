#!/usr/bin/env python3

import argparse
import csv
import re
import statistics
import sys
import threading
import time
from pathlib import Path

import serial

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.hardware.pcm5122 import PCM5122


# Example Teensy line:
#
# A0 n=2000 min=0 max=785 mean=285.5 p2p=785
# freq=530.0Hz conf=0.95 detect=...
#
LINE_RE = re.compile(
    r"min=(?P<min>\d+)\s+"
    r"max=(?P<max>\d+)\s+"
    r"mean=(?P<mean>[\d.]+)\s+"
    r"p2p=(?P<p2p>\d+)"
    r"(?:\s+freq=(?P<freq>[\d.]+)Hz"
    r"\s+conf=(?P<conf>[\d.]+))?"
)


def parse_teensy_line(line):
    m = LINE_RE.search(line)
    if not m:
        return None

    return {
        "min": int(m.group("min")),
        "max": int(m.group("max")),
        "mean": float(m.group("mean")),
        "p2p": int(m.group("p2p")),
        "freq": (
            float(m.group("freq"))
            if m.group("freq") is not None
            else None
        ),
        "conf": (
            float(m.group("conf"))
            if m.group("conf") is not None
            else None
        ),
    }


def summarize_samples(samples):
    if not samples:
        return None

    p2ps = [s["p2p"] for s in samples]

    valid_freq = [
        s["freq"]
        for s in samples
        if s["freq"] is not None
    ]

    valid_conf = [
        s["conf"]
        for s in samples
        if s["conf"] is not None
    ]

    return {
        "sample_count": len(samples),

        # robust sweep response measurement
        "median_p2p": statistics.median(p2ps),

        # useful for seeing absolute peak
        "mean_p2p": statistics.mean(p2ps),
        "max_p2p": max(p2ps),

        "min_adc": min(s["min"] for s in samples),
        "max_adc": max(s["max"] for s in samples),

        "piezo_freq": (
            statistics.median(valid_freq)
            if valid_freq else None
        ),

        "confidence": (
            statistics.mean(valid_conf)
            if valid_conf else None
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="PCM5122 exciter sweep with Teensy piezo measurement"
    )

    parser.add_argument("--start", type=float, default=515.0)
    parser.add_argument("--stop", type=float, default=545.0)
    parser.add_argument("--step", type=float, default=1.0)

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.005,
        help="DAC amplitude, e.g. 0.005 = 0.5%%",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=0.75,
        help="Tone duration per frequency",
    )

    parser.add_argument(
        "--settle",
        type=float,
        default=0.15,
        help="Ignore Teensy samples for this long after tone starts",
    )

    parser.add_argument(
        "--gap",
        type=float,
        default=0.20,
        help="Quiet gap between frequencies",
    )

    parser.add_argument(
        "--serial",
        default="/dev/ttyACM0",
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
    )

    parser.add_argument(
        "--output",
        default="results/teensy_piezo_exciter_sweep.csv",
    )

    args = parser.parse_args()

    if args.stop < args.start:
        raise SystemExit("stop must be >= start")

    if args.step <= 0:
        raise SystemExit("step must be > 0")

    if args.amplitude <= 0 or args.amplitude > 0.10:
        raise SystemExit("amplitude must be > 0 and <= 0.10")

    dac = PCM5122()
    status = dac.status()

    if not status["found"]:
        raise SystemExit("PCM5122 DAC not found")

    print()
    print("=" * 66)
    print(" SMART SOUND BOWL - PIEZO + EXCITER SWEEP")
    print("=" * 66)
    print(f"DAC         : {status['device']}")
    print(f"Teensy      : {args.serial}")
    print(f"Range       : {args.start:.1f} - {args.stop:.1f} Hz")
    print(f"Step        : {args.step:.1f} Hz")
    print(f"DAC level   : {args.amplitude * 100:.2f}%")
    print(f"Tone        : {args.duration:.2f} sec")
    print(f"Settle      : {args.settle:.2f} sec")
    print()

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        ser = serial.Serial(
            args.serial,
            args.baud,
            timeout=0.05,
        )
    except serial.SerialException as exc:
        raise SystemExit(
            f"Could not open Teensy at {args.serial}: {exc}\n"
            "Make sure 'pio device monitor' is closed."
        )

    # Let USB serial stabilize.
    time.sleep(0.5)
    ser.reset_input_buffer()

    results = []

    frequency = args.start

    try:
        print(
            f"{'Drive':>8} "
            f"{'Piezo':>8} "
            f"{'Med P2P':>9} "
            f"{'Max P2P':>9} "
            f"{'Conf':>7} "
            f"{'ADC':>11}"
        )
        print("-" * 62)

        while frequency <= args.stop + 1e-6:

            # Get rid of old samples from previous frequency.
            ser.reset_input_buffer()

            playback_result = {}

            def play_tone():
                playback_result["result"] = dac.test(
                    frequency_hz=frequency,
                    amplitude=args.amplitude,
                    duration_s=args.duration,
                )

            playback_thread = threading.Thread(
                target=play_tone,
                daemon=True,
            )

            start_time = time.monotonic()
            playback_thread.start()

            samples = []

            while playback_thread.is_alive():

                raw = ser.readline()

                if not raw:
                    continue

                elapsed = time.monotonic() - start_time

                try:
                    line = raw.decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()
                except Exception:
                    continue

                sample = parse_teensy_line(line)

                if sample is None:
                    continue

                # Ignore attack/startup portion.
                if elapsed < args.settle:
                    continue

                samples.append(sample)

            playback_thread.join()

            result = playback_result.get("result")

            if not result or not result.get("ok"):
                error = (
                    result.get("stderr", "unknown playback error")
                    if result else
                    "playback returned no result"
                )

                raise RuntimeError(
                    f"DAC playback failed at "
                    f"{frequency:.1f} Hz: {error}"
                )

            summary = summarize_samples(samples)

            if summary is None:
                print(
                    f"{frequency:8.1f} "
                    f"{'---':>8} "
                    f"{'---':>9} "
                    f"{'---':>9} "
                    f"{'---':>7} "
                    f"{'NO DATA':>11}"
                )

                frequency += args.step
                time.sleep(args.gap)
                continue

            piezo_freq = summary["piezo_freq"]
            confidence = summary["confidence"]

            freq_text = (
                f"{piezo_freq:.1f}"
                if piezo_freq is not None
                else "---"
            )

            conf_text = (
                f"{confidence:.2f}"
                if confidence is not None
                else "---"
            )

            adc_text = (
                f"{summary['min_adc']}-"
                f"{summary['max_adc']}"
            )

            print(
                f"{frequency:8.1f} "
                f"{freq_text:>8} "
                f"{summary['median_p2p']:9.1f} "
                f"{summary['max_p2p']:9d} "
                f"{conf_text:>7} "
                f"{adc_text:>11}"
            )

            results.append({
                "drive_hz": frequency,
                "piezo_freq_hz": piezo_freq,
                "confidence": confidence,
                "median_p2p": summary["median_p2p"],
                "mean_p2p": summary["mean_p2p"],
                "max_p2p": summary["max_p2p"],
                "min_adc": summary["min_adc"],
                "max_adc": summary["max_adc"],
                "sample_count": summary["sample_count"],
            })

            frequency += args.step
            time.sleep(args.gap)

    except KeyboardInterrupt:
        print("\nSweep stopped by user.")

    finally:
        ser.close()

    if not results:
        raise SystemExit("No valid sweep measurements collected.")

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "drive_hz",
                "piezo_freq_hz",
                "confidence",
                "median_p2p",
                "mean_p2p",
                "max_p2p",
                "min_adc",
                "max_adc",
                "sample_count",
            ],
        )

        writer.writeheader()
        writer.writerows(results)

    # Use median P2P as the robust resonance metric.
    peak = max(
        results,
        key=lambda row: row["median_p2p"],
    )

    print()
    print("=" * 66)
    print(" SWEEP RESULT")
    print("=" * 66)

    print(
        f"Peak response frequency : "
        f"{peak['drive_hz']:.2f} Hz"
    )

    print(
        f"Median piezo P2P        : "
        f"{peak['median_p2p']:.1f}"
    )

    print(
        f"Maximum piezo P2P       : "
        f"{peak['max_p2p']}"
    )

    if peak["piezo_freq_hz"] is not None:
        print(
            f"Measured piezo freq     : "
            f"{peak['piezo_freq_hz']:.2f} Hz"
        )

    if peak["confidence"] is not None:
        print(
            f"YIN confidence          : "
            f"{peak['confidence']:.3f}"
        )

    if peak["min_adc"] == 0:
        print()
        print(
            "WARNING: ADC clipped at 0 near resonance. "
            "Reduce DAC amplitude."
        )

    print()
    print(f"CSV saved: {output_path}")


if __name__ == "__main__":
    main()
