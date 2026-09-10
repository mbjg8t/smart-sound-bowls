#!/usr/bin/env python3

import argparse
import re
import statistics
import sys
import threading
import time
from pathlib import Path

import serial

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.hardware.pcm5122 import PCM5122


LINE_RE = re.compile(
    r"min=(?P<min>\d+)\s+"
    r"max=(?P<max>\d+)\s+"
    r"mean=(?P<mean>[\d.]+)\s+"
    r"p2p=(?P<p2p>\d+)"
    r"(?:\s+freq=(?P<freq>[\d.]+)Hz"
    r"\s+conf=(?P<conf>[\d.]+))?"
)


def measure_chunk(
    dac,
    ser,
    frequency,
    amplitude,
    duration,
    settle,
):
    samples = []

    ser.reset_input_buffer()

    result_holder = {}

    def play():
        result_holder["result"] = dac.test(
            frequency_hz=frequency,
            amplitude=amplitude,
            duration_s=duration,
        )

    thread = threading.Thread(
        target=play,
        daemon=True,
    )

    start = time.monotonic()
    thread.start()

    deadline = start + duration

    while time.monotonic() < deadline:

        line = ser.readline().decode(
            "utf-8",
            errors="ignore",
        ).strip()

        if not line:
            continue

        match = LINE_RE.search(line)

        if not match:
            continue

        elapsed = time.monotonic() - start

        if elapsed < settle:
            continue

        sample = {
            "min": int(match.group("min")),
            "max": int(match.group("max")),
            "p2p": int(match.group("p2p")),
            "freq": (
                float(match.group("freq"))
                if match.group("freq")
                else None
            ),
            "conf": (
                float(match.group("conf"))
                if match.group("conf")
                else None
            ),
        }

        samples.append(sample)

    thread.join()

    if not samples:
        return None

    p2ps = [
        s["p2p"]
        for s in samples
    ]

    frequencies = [
        s["freq"]
        for s in samples
        if s["freq"] is not None
    ]

    confidences = [
        s["conf"]
        for s in samples
        if s["conf"] is not None
    ]

    return {
        "median_p2p": statistics.median(p2ps),
        "max_p2p": max(p2ps),
        "min_adc": min(s["min"] for s in samples),
        "max_adc": max(s["max"] for s in samples),
        "frequency": (
            statistics.median(frequencies)
            if frequencies
            else None
        ),
        "confidence": (
            statistics.mean(confidences)
            if confidences
            else None
        ),
        "count": len(samples),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Closed-loop bowl vibration level hold "
            "using Teensy piezo feedback."
        )
    )

    parser.add_argument(
        "--frequency",
        type=float,
        default=529.0,
    )

    parser.add_argument(
        "--target",
        type=float,
        default=220.0,
        help="Target median piezo peak-to-peak ADC counts",
    )

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.0010,
        help="Initial DAC amplitude",
    )

    parser.add_argument(
        "--min-amplitude",
        type=float,
        default=0.0002,
    )

    parser.add_argument(
        "--max-amplitude",
        type=float,
        default=0.0050,
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Total control test duration",
    )

    parser.add_argument(
        "--chunk",
        type=float,
        default=0.60,
        help="Tone duration for each control iteration",
    )

    parser.add_argument(
        "--settle",
        type=float,
        default=0.15,
    )

    parser.add_argument(
        "--gain",
        type=float,
        default=0.40,
        help="Proportional amplitude adjustment gain",
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

    dac = PCM5122()

    ser = serial.Serial(
        args.port,
        args.baud,
        timeout=0.12,
    )

    time.sleep(0.5)

    amplitude = args.amplitude

    print()
    print("=" * 72)
    print(" SMART SOUND BOWL - CLOSED LOOP PIEZO LEVEL HOLD")
    print("=" * 72)

    print(f"Frequency      : {args.frequency:.3f} Hz")
    print(f"Target P2P     : {args.target:.1f}")
    print(f"Initial DAC    : {amplitude * 100:.4f}%")
    print(f"Amplitude max  : {args.max_amplitude * 100:.4f}%")
    print(f"Duration       : {args.duration:.1f} sec")
    print()

    print(
        f"{'Time':>6} "
        f"{'DAC %':>8} "
        f"{'P2P':>8} "
        f"{'Error':>8} "
        f"{'Piezo Hz':>10} "
        f"{'ADC':>11}"
    )

    print("-" * 72)

    test_start = time.monotonic()

    try:

        while (
            time.monotonic() - test_start
            < args.duration
        ):

            measurement = measure_chunk(
                dac,
                ser,
                args.frequency,
                amplitude,
                args.chunk,
                args.settle,
            )

            elapsed = (
                time.monotonic()
                - test_start
            )

            if measurement is None:
                print(
                    f"{elapsed:6.1f} "
                    f"{amplitude * 100:8.4f} "
                    f"{'---':>8} "
                    f"{'---':>8} "
                    f"{'---':>10}"
                )
                continue

            p2p = measurement["median_p2p"]

            error = args.target - p2p

            piezo_freq = (
                f"{measurement['frequency']:.2f}"
                if measurement["frequency"] is not None
                else "---"
            )

            adc_text = (
                f"{measurement['min_adc']}-"
                f"{measurement['max_adc']}"
            )

            print(
                f"{elapsed:6.1f} "
                f"{amplitude * 100:8.4f} "
                f"{p2p:8.1f} "
                f"{error:8.1f} "
                f"{piezo_freq:>10} "
                f"{adc_text:>11}"
            )

            if (
                measurement["min_adc"] <= 0
                or measurement["max_adc"] >= 4095
            ):
                amplitude *= 0.70

                amplitude = max(
                    args.min_amplitude,
                    amplitude,
                )

                print(
                    "       ADC CLIP -> reducing drive"
                )

                continue

            normalized_error = (
                error / args.target
            )

            correction = (
                1.0
                + args.gain
                * normalized_error
            )

            correction = max(
                0.75,
                min(1.25, correction),
            )

            amplitude *= correction

            amplitude = max(
                args.min_amplitude,
                min(
                    args.max_amplitude,
                    amplitude,
                ),
            )

    except KeyboardInterrupt:
        print()
        print("Stopped.")

    finally:
        ser.close()

    print()
    print("=" * 72)
    print(" LEVEL HOLD COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
