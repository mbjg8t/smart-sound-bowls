import sys
import time

from app.hardware.adxl345 import ADXL345


if len(sys.argv) != 2 or sys.argv[1] not in ("1", "2"):
    print()
    print("Usage:")
    print("  python3 -m tools.test_adxl 1")
    print("  python3 -m tools.test_adxl 2")
    print()
    raise SystemExit(1)


accel_number = int(sys.argv[1])

# Accel 1 = SPI0 CE0
# Accel 2 = SPI0 CE1
spi_device = accel_number - 1

sensor = ADXL345(
    bus=0,
    device=spi_device,
)


try:
    sensor.open()

    print()
    print(f"ACCEL {accel_number} PROBE")
    print("-----------------")
    print(
        f"SPI: /dev/spidev0.{spi_device}"
    )

    result = sensor.probe()

    print(
        f"Found:     {result.get('found')}"
    )
    print(
        f"Device ID: {result.get('device_id')}"
    )
    print(
        f"Readings:  {result.get('readings')}"
    )

    if not result.get("found"):
        print()
        print(
            "ERROR: ADXL345 not detected."
        )
        print(
            "Expected device ID: "
            "229 (0xE5)"
        )
        raise SystemExit(2)

    sensor.configure(
        rate=800,
        range_g=16,
    )

    print()
    print("ADXL345 detected: 0xE5")
    print()
    print("LIVE DATA")
    print("---------")

    for i in range(50):
        x, y, z = sensor.read_g()

        print(
            f"{i:02d}  "
            f"X={x:+7.4f} g   "
            f"Y={y:+7.4f} g   "
            f"Z={z:+7.4f} g"
        )

        time.sleep(0.1)

finally:
    sensor.close()
