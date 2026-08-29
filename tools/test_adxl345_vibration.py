#!/usr/bin/env python3

import sys
import time
import math
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hardware.adxl345 import ADXL345


SAMPLE_RATE = 800
TEST_DURATION = 5.0
DRIVE_FREQUENCY = 220.0


def main():
    print()
    print("========================================")
    print(" ADXL345 VIBRATION TEST")
    print("========================================")
    print()

    sensor = ADXL345(
        max_speed_hz=500_000
    )

    try:
        sensor.open()

        info = sensor.probe()

        if not info["found"]:
            print("ADXL345 NOT DETECTED")
            return 1

        print("ADXL345 detected")
        print(f"ODR          : {SAMPLE_RATE} Hz")
        print(f"Drive freq   : {DRIVE_FREQUENCY} Hz")
        print()

        sensor.configure(rate=SAMPLE_RATE)

        # Let sensor settle
        time.sleep(0.25)

        print("Starting 220 Hz exciter...")
        print()

        playback = subprocess.Popen([
            "aplay",
            "-q",
            "-D",
            "plughw:CARD=SmartBowlAudio,DEV=1",
            "smartbowl-tone.wav",
        ])

        samples = []
        timestamps = []

        start = time.perf_counter()
        next_sample = start

        while True:
            now = time.perf_counter()

            if now - start >= TEST_DURATION:
                break

            if now >= next_sample:
                x, y, z = sensor.read_g()

                timestamps.append(now - start)
                samples.append((x, y, z))

                next_sample += 1.0 / SAMPLE_RATE

        playback.terminate()

        data = np.array(samples, dtype=np.float64)
        t = np.array(timestamps, dtype=np.float64)

        if len(data) < 100:
            print("Not enough samples")
            return 1

        actual_rate = (
            (len(t) - 1) /
            (t[-1] - t[0])
        )

        print(f"Samples      : {len(data)}")
        print(f"Actual rate  : {actual_rate:.1f} Hz")

        # Remove DC / gravity
        data -= np.mean(data, axis=0)

        print()
        print("RMS vibration:")
        print(
            f"X = {np.sqrt(np.mean(data[:,0]**2)):.5f} g"
        )
        print(
            f"Y = {np.sqrt(np.mean(data[:,1]**2)):.5f} g"
        )
        print(
            f"Z = {np.sqrt(np.mean(data[:,2]**2)):.5f} g"
        )

        print()
        print("220 Hz response:")

        for axis_index, axis_name in enumerate(
            ["X", "Y", "Z"]
        ):
            signal = data[:, axis_index]

            # Use actual measured sampling rate
            freqs = np.fft.rfftfreq(
                len(signal),
                d=1.0 / actual_rate
            )

            spectrum = np.abs(
                np.fft.rfft(
                    signal *
                    np.hanning(len(signal))
                )
            )

            target = np.argmin(
                np.abs(freqs - DRIVE_FREQUENCY)
            )

            peak = np.argmax(spectrum[1:]) + 1

            print(
                f"{axis_name}: "
                f"220Hz={spectrum[target]:.3e}   "
                f"strongest={freqs[peak]:.2f} Hz"
            )

        print()
        print("Test complete.")
        print()

        return 0

    finally:
        sensor.close()


if __name__ == "__main__":
    raise SystemExit(main())
