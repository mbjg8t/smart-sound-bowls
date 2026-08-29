#!/usr/bin/env python3

import argparse
import csv
import math
import os
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 48000

PLAYBACK_DEVICE = "plughw:CARD=SmartBowlAudio,DEV=1"
CAPTURE_DEVICE = "plughw:CARD=SmartBowlAudio,DEV=0"


def create_tone(filename, frequency, amplitude, duration):
    frames = int(SAMPLE_RATE * duration)

    with wave.open(str(filename), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)

        data = bytearray()

        for n in range(frames):
            sample = int(
                32767
                * amplitude
                * math.sin(2.0 * math.pi * frequency * n / SAMPLE_RATE)
            )

            data += struct.pack("<hh", sample, sample)

        wav.writeframes(data)


def record_and_play(tone_file, capture_file):
    capture = subprocess.Popen(
        [
            "arecord",
            "-q",
            "-D",
            CAPTURE_DEVICE,
            "-f",
            "S32_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            "2",
            "-d",
            "1",
            str(capture_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Allow capture stream and I2S clocks to settle.
    time.sleep(0.15)

    playback = subprocess.run(
        [
            "aplay",
            "-q",
            "-D",
            PLAYBACK_DEVICE,
            str(tone_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    capture.wait()

    if playback.returncode != 0:
        raise RuntimeError(
            f"aplay failed: {playback.stderr.strip()}"
        )


def read_active_channel(filename):
    with wave.open(str(filename), "rb") as wav:
        channels = wav.getnchannels()
        rate = wav.getframerate()
        width = wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())

    if rate != SAMPLE_RATE:
        raise RuntimeError(
            f"Unexpected sample rate: {rate}"
        )

    if width != 4:
        raise RuntimeError(
            f"Unexpected sample width: {width * 8} bit"
        )

    samples = np.frombuffer(raw, dtype="<i4")

    if channels == 1:
        signal = samples.astype(np.float64)
    else:
        samples = samples.reshape(-1, channels)

        left = samples[:, 0].astype(np.float64)
        right = samples[:, 1].astype(np.float64)

        # INMP441 L/R pin is currently tied low, so LEFT should
        # normally contain the valid channel. Still choose based
        # on RMS so the utility is robust.
        left_rms = np.sqrt(np.mean(left * left))
        right_rms = np.sqrt(np.mean(right * right))

        signal = left if left_rms >= right_rms else right

    return signal


def amplitude_at_frequency(signal, frequency):
    # Playback begins roughly 150 ms into the 1-second capture.
    # Analyze the central region to avoid startup/stop transients.
    start = int(0.25 * SAMPLE_RATE)
    stop = int(0.75 * SAMPLE_RATE)

    if len(signal) < stop:
        stop = len(signal)

    signal = signal[start:stop]

    signal = signal - np.mean(signal)

    n = len(signal)

    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    sin_ref = np.sin(2.0 * np.pi * frequency * t)
    cos_ref = np.cos(2.0 * np.pi * frequency * t)

    i_component = np.dot(signal, cos_ref)
    q_component = np.dot(signal, sin_ref)

    amplitude = (
        2.0
        * math.sqrt(
            i_component * i_component
            + q_component * q_component
        )
        / n
    )

    rms = np.sqrt(np.mean(signal * signal))
    peak = np.max(np.abs(signal))

    return amplitude, rms, peak


def find_local_peaks(results):
    peaks = []

    for i in range(1, len(results) - 1):
        previous = results[i - 1]["response"]
        current = results[i]["response"]
        following = results[i + 1]["response"]

        if current > previous and current > following:
            peaks.append(results[i])

    peaks.sort(
        key=lambda item: item["response"],
        reverse=True,
    )

    return peaks


def main():
    parser = argparse.ArgumentParser(
        description="Smart Sound Bowl resonance sweep"
    )

    parser.add_argument(
        "--start",
        type=float,
        default=80.0,
        help="Start frequency in Hz",
    )

    parser.add_argument(
        "--stop",
        type=float,
        default=1200.0,
        help="Stop frequency in Hz",
    )

    parser.add_argument(
        "--step",
        type=float,
        default=20.0,
        help="Frequency step in Hz",
    )

    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.01,
        help="DAC amplitude 0.0-1.0",
    )

    parser.add_argument(
        "--tone-duration",
        type=float,
        default=0.65,
        help="Tone duration per step",
    )

    args = parser.parse_args()

    if args.amplitude <= 0 or args.amplitude > 0.10:
        raise SystemExit(
            "Amplitude must be > 0 and <= 0.10"
        )

    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    csv_file = output_dir / "resonance_sweep.csv"

    frequencies = np.arange(
        args.start,
        args.stop + (args.step / 2),
        args.step,
    )

    results = []

    print()
    print("==========================================")
    print(" SMART SOUND BOWL - RESONANCE SWEEP")
    print("==========================================")
    print()
    print(
        f"Range       : {args.start:.1f} - "
        f"{args.stop:.1f} Hz"
    )
    print(f"Step        : {args.step:.1f} Hz")
    print(f"Points      : {len(frequencies)}")
    print(
        f"DAC level   : "
        f"{args.amplitude * 100:.1f}%"
    )
    print(f"Playback    : {PLAYBACK_DEVICE}")
    print(f"Capture     : {CAPTURE_DEVICE}")
    print()
    print("Frequency       Response           RMS")
    print("---------------------------------------------")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        for index, frequency in enumerate(
            frequencies,
            start=1,
        ):
            tone_file = temp_dir / "tone.wav"
            capture_file = temp_dir / "capture.wav"

            create_tone(
                tone_file,
                frequency,
                args.amplitude,
                args.tone_duration,
            )

            record_and_play(
                tone_file,
                capture_file,
            )

            signal = read_active_channel(
                capture_file
            )

            response, rms, peak = (
                amplitude_at_frequency(
                    signal,
                    frequency,
                )
            )

            result = {
                "frequency": float(frequency),
                "response": float(response),
                "rms": float(rms),
                "peak": float(peak),
            }

            results.append(result)

            print(
                f"{frequency:8.1f} Hz   "
                f"{response:12.3e}   "
                f"{rms:12.3e}"
            )

    maximum = max(
        result["response"]
        for result in results
    )

    for result in results:
        if maximum > 0:
            result["relative_db"] = (
                20.0
                * math.log10(
                    max(
                        result["response"],
                        1.0,
                    )
                    / maximum
                )
            )
        else:
            result["relative_db"] = -120.0

    with open(
        csv_file,
        "w",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "frequency",
                "response",
                "relative_db",
                "rms",
                "peak",
            ],
        )

        writer.writeheader()
        writer.writerows(results)

    ranked = sorted(
        results,
        key=lambda item: item["response"],
        reverse=True,
    )

    local_peaks = find_local_peaks(results)

    print()
    print("==========================================")
    print(" STRONGEST RESPONSE POINTS")
    print("==========================================")
    print()

    for result in ranked[:10]:
        print(
            f"{result['frequency']:8.1f} Hz   "
            f"{result['relative_db']:7.2f} dB   "
            f"{result['response']:.3e}"
        )

    print()
    print("==========================================")
    print(" LOCAL RESONANCE CANDIDATES")
    print("==========================================")
    print()

    if local_peaks:
        for result in local_peaks[:10]:
            print(
                f"{result['frequency']:8.1f} Hz   "
                f"{result['relative_db']:7.2f} dB   "
                f"{result['response']:.3e}"
            )
    else:
        print("No distinct local peaks detected.")

    print()
    print(
        f"Strongest response: "
        f"{ranked[0]['frequency']:.1f} Hz"
    )

    print()
    print(f"Results saved: {csv_file}")
    print()


if __name__ == "__main__":
    main()
