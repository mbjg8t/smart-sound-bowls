#!/usr/bin/env python3

import csv
import math
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hardware.adxl345 import ADXL345


# ---------------------------------------------------------
# Sweep configuration
# ---------------------------------------------------------

START_HZ = 80
STOP_HZ = 380
STEP_HZ = 5

ADXL_RATE = 800
ADXL_RANGE_G = 16

AUDIO_RATE = 48000
AUDIO_AMPLITUDE = 0.001

SETTLE_SECONDS = 0.05
MEASURE_SECONDS = 0.15
TAIL_SECONDS = 0.01

PLAYBACK_DEVICE = (
    "plughw:CARD=SmartBowlAudio,DEV=1"
)

TONE_FILE = Path(
    "/tmp/smartbowl_sweep_tone.wav"
)

RESULT_DIR = ROOT / "results"
RESULT_FILE = (
    RESULT_DIR /
    "resonance_sweep_adxl345.csv"
)


def make_tone(
    frequency,
    duration,
):
    samples = int(
        AUDIO_RATE * duration
    )

    t = (
        np.arange(samples) /
        AUDIO_RATE
    )

    signal = (
        np.sin(
            2.0 *
            np.pi *
            frequency *
            t
        )
        *
        AUDIO_AMPLITUDE
    )

    pcm = np.clip(
        signal * 32767.0,
        -32768,
        32767,
    ).astype(np.int16)

    # Stereo: same signal L/R
    stereo = np.column_stack(
        (pcm, pcm)
    ).reshape(-1)

    with wave.open(
        str(TONE_FILE),
        "wb",
    ) as wf:

        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_RATE)

        wf.writeframes(
            stereo.tobytes()
        )


def synchronous_amplitude(
    timestamps,
    signal,
    frequency,
):
    """
    Lock-in style measurement at the exact
    commanded frequency.

    Uses the measured timestamps rather than
    assuming perfect Python sample timing.
    """

    signal = np.asarray(
        signal,
        dtype=np.float64,
    )

    timestamps = np.asarray(
        timestamps,
        dtype=np.float64,
    )

    signal = signal - np.mean(signal)

    phase = (
        2.0 *
        np.pi *
        frequency *
        timestamps
    )

    sin_ref = np.sin(phase)
    cos_ref = np.cos(phase)

    sin_part = (
        2.0 /
        len(signal)
        *
        np.sum(
            signal *
            sin_ref
        )
    )

    cos_part = (
        2.0 /
        len(signal)
        *
        np.sum(
            signal *
            cos_ref
        )
    )

    amplitude = math.sqrt(
        sin_part ** 2 +
        cos_part ** 2
    )

    return amplitude


def measure_frequency(
    sensor,
    frequency,
):
    total_duration = (
        SETTLE_SECONDS +
        MEASURE_SECONDS +
        TAIL_SECONDS
    )

    make_tone(
        frequency,
        total_duration,
    )

    playback = subprocess.Popen(
        [
            "aplay",
            "-q",
            "-D",
            PLAYBACK_DEVICE,
            str(TONE_FILE),
        ]
    )

    timestamps = []
    samples = []

    start = time.perf_counter()

    measure_start = (
        start +
        SETTLE_SECONDS
    )

    measure_end = (
        measure_start +
        MEASURE_SECONDS
    )

    next_sample = start

    try:
        while True:
            now = time.perf_counter()

            if now >= measure_end:
                break

            if now < next_sample:
                continue

            x, y, z = sensor.read_g()

            if now >= measure_start:
                timestamps.append(
                    now - measure_start
                )

                samples.append(
                    (x, y, z)
                )

            next_sample += (
                1.0 /
                ADXL_RATE
            )

    finally:
        try:
            playback.wait(
                timeout=1.0
            )
        except subprocess.TimeoutExpired:
            playback.terminate()

    data = np.asarray(
        samples,
        dtype=np.float64,
    )

    timestamps = np.asarray(
        timestamps,
        dtype=np.float64,
    )

    if len(data) < 10:
        raise RuntimeError(
            "Too few accelerometer samples"
        )

    actual_rate = (
        (len(timestamps) - 1)
        /
        (
            timestamps[-1] -
            timestamps[0]
        )
    )

    # Remove DC / gravity before RMS
    ac = (
        data -
        np.mean(
            data,
            axis=0,
        )
    )

    rms = np.sqrt(
        np.mean(
            ac ** 2,
            axis=0,
        )
    )

    amp_x = synchronous_amplitude(
        timestamps,
        data[:, 0],
        frequency,
    )

    amp_y = synchronous_amplitude(
        timestamps,
        data[:, 1],
        frequency,
    )

    amp_z = synchronous_amplitude(
        timestamps,
        data[:, 2],
        frequency,
    )

    vector_amp = math.sqrt(
        amp_x ** 2 +
        amp_y ** 2 +
        amp_z ** 2
    )

    peak_abs = np.max(
        np.abs(data),
        axis=0,
    )

    max_g = float(
        np.max(peak_abs)
    )

    return {
        "frequency_hz": frequency,
        "samples": len(data),
        "actual_rate_hz": actual_rate,

        "amp_x_g": amp_x,
        "amp_y_g": amp_y,
        "amp_z_g": amp_z,

        "vector_amp_g": vector_amp,

        "rms_x_g": rms[0],
        "rms_y_g": rms[1],
        "rms_z_g": rms[2],

        "max_abs_g": max_g,
    }


def print_bar(
    value,
    maximum,
    width=35,
):
    if maximum <= 0:
        return ""

    length = int(
        width *
        value /
        maximum
    )

    return "#" * max(
        1,
        length,
    )


def main():
    print()
    print(
        "========================================"
    )
    print(
        " SMART BOWL RESONANCE SWEEP"
    )
    print(
        " PCM5122 + ADXL345"
    )
    print(
        "========================================"
    )
    print()

    print(
        f"Sweep       : "
        f"{START_HZ}-{STOP_HZ} Hz "
        f"in {STEP_HZ} Hz steps"
    )

    print(
        f"ADXL345     : "
        f"{ADXL_RATE} Hz, "
        f"+/-{ADXL_RANGE_G} g"
    )

    print(
        f"Drive       : "
        f"{AUDIO_AMPLITUDE * 100:.1f}%"
    )

    print(
        f"Measurement : "
        f"{MEASURE_SECONDS:.2f} sec/frequency"
    )

    print()

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sensor = ADXL345(
        max_speed_hz=500_000
    )

    results = []

    try:
        sensor.open()

        info = sensor.probe()

        if not info["found"]:
            print(
                "ADXL345 NOT DETECTED"
            )
            return 1

        print(
            "ADXL345 detected ✓"
        )

        sensor.configure(
            rate=ADXL_RATE,
            range_g=ADXL_RANGE_G,
        )

        time.sleep(0.25)

        print()
        print(
            "Starting sweep..."
        )
        print()

        frequencies = range(
            START_HZ,
            STOP_HZ + 1,
            STEP_HZ,
        )

        for frequency in frequencies:

            result = measure_frequency(
                sensor,
                frequency,
            )

            results.append(result)

            print(
                f"{frequency:4d} Hz  "
                f"response="
                f"{result['vector_amp_g']:8.4f} g  "
                f"X={result['amp_x_g']:7.4f}  "
                f"Y={result['amp_y_g']:7.4f}  "
                f"Z={result['amp_z_g']:7.4f}  "
                f"max={result['max_abs_g']:6.2f} g"
            )

            # Short pause between tones
            time.sleep(0.02)

    except KeyboardInterrupt:
        print()
        print("Sweep interrupted.")

    finally:
        sensor.close()

    if not results:
        return 1

    with open(
        RESULT_FILE,
        "w",
        newline="",
    ) as f:

        fieldnames = list(
            results[0].keys()
        )

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    ranked = sorted(
        results,
        key=lambda r: r[
            "vector_amp_g"
        ],
        reverse=True,
    )

    maximum = ranked[0][
        "vector_amp_g"
    ]

    print()
    print(
        "========================================"
    )
    print(
        " STRONGEST RESPONSES"
    )
    print(
        "========================================"
    )
    print()

    for i, result in enumerate(
        ranked[:10],
        start=1,
    ):
        bar = print_bar(
            result[
                "vector_amp_g"
            ],
            maximum,
        )

        print(
            f"{i:2d}. "
            f"{result['frequency_hz']:4.0f} Hz  "
            f"{result['vector_amp_g']:8.4f} g  "
            f"{bar}"
        )

    print()
    print(
        f"CSV saved:"
    )
    print(
        RESULT_FILE
    )

    print()

    max_seen = max(
        r["max_abs_g"]
        for r in results
    )

    print(
        f"Maximum instantaneous "
        f"acceleration observed: "
        f"{max_seen:.2f} g"
    )

    if max_seen > 14.0:
        print()
        print(
            "WARNING: approaching "
            "+/-16 g sensor range."
        )

    print()
    print(
        "Sweep complete."
    )
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
