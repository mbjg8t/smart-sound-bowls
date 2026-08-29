#!/usr/bin/env python3

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hardware.adxl345 import ADXL345


def main():
    print()
    print("========================================")
    print(" ADXL345 STABILITY TEST")
    print("========================================")
    print()

    sensor = ADXL345()

    try:
        sensor.open()

        info = sensor.probe()

        print(f"SPI device : {info['spi']}")
        print(
            "ID reads   : "
            + " ".join(
                f"0x{x:02X}"
                for x in info["readings"]
            )
        )

        if not info["found"]:
            print()
            print("ADXL345 NOT DETECTED")
            return 1

        print()
        print("ADXL345 DETECTED ✓")

        sensor.configure(rate=100)

        print()
        print("Live acceleration:")
        print()

        for _ in range(30):
            devid = sensor.read_device_id()
            x, y, z = sensor.read_g()

            print(
                f"ID=0x{devid:02X}   "
                f"X={x:+8.4f}   "
                f"Y={y:+8.4f}   "
                f"Z={z:+8.4f}"
            )

            time.sleep(0.1)

        print()
        print("Test complete.")
        print()

        return 0

    finally:
        sensor.close()


if __name__ == "__main__":
    raise SystemExit(main())
