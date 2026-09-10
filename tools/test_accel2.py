import time

from app.hardware.adxl345 import ADXL345


sensor = ADXL345(
    bus=0,
    device=1,
)

try:
    sensor.open()

    print()
    print("ACCEL 2 PROBE")
    print("-------------")

    result = sensor.probe()

    print(result)

    sensor.configure(
        rate=800,
        range_g=16,
    )

    print()
    print("LIVE ACCEL 2 DATA")
    print("-----------------")

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
