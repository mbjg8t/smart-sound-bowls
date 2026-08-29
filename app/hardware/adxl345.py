import time

try:
    import spidev
except ImportError:
    spidev = None


class ADXL345:
    DEVID = 0x00
    BW_RATE = 0x2C
    POWER_CTL = 0x2D
    DATA_FORMAT = 0x31
    DATAX0 = 0x32

    DEVICE_ID = 0xE5

    READ = 0x80
    MULTI = 0x40

    RATE_CODES = {
        100: 0x0A,
        200: 0x0B,
        400: 0x0C,
        800: 0x0D,
        1600: 0x0E,
        3200: 0x0F,
    }

    RANGE_CODES = {
        2: 0x00,
        4: 0x01,
        8: 0x02,
        16: 0x03,
    }

    def __init__(
        self,
        bus=0,
        device=0,
        max_speed_hz=500_000,
    ):
        self.bus = bus
        self.device = device
        self.max_speed_hz = max_speed_hz
        self.spi = None

    def open(self):
        if spidev is None:
            raise RuntimeError(
                "python3-spidev is not installed"
            )

        self.spi = spidev.SpiDev()
        self.spi.open(self.bus, self.device)
        self.spi.mode = 3
        self.spi.max_speed_hz = self.max_speed_hz

        time.sleep(0.05)

        # Standby helps stabilize this breakout
        self._write_reg(
            self.POWER_CTL,
            0x00,
        )

        time.sleep(0.05)

        return self

    def close(self):
        if self.spi is not None:
            self.spi.close()
            self.spi = None

    def _read_reg(self, reg):
        result = self.spi.xfer2([
            reg | self.READ,
            0x00,
        ])

        return result[1]

    def _write_reg(self, reg, value):
        self.spi.xfer2([
            reg & 0x3F,
            value & 0xFF,
        ])

    def _read_regs(self, reg, count):
        result = self.spi.xfer2(
            [
                reg | self.READ | self.MULTI
            ]
            + [0x00] * count
        )

        return result[1:]

    def read_device_id(self):
        return self._read_reg(self.DEVID)

    def probe(self, attempts=10):
        readings = []

        for _ in range(attempts):
            devid = self.read_device_id()
            readings.append(devid)

            if devid == self.DEVICE_ID:
                return {
                    "found": True,
                    "device_id": devid,
                    "readings": readings,
                    "spi": (
                        f"/dev/spidev"
                        f"{self.bus}.{self.device}"
                    ),
                }

            time.sleep(0.02)

        return {
            "found": False,
            "device_id": readings[-1],
            "readings": readings,
            "spi": (
                f"/dev/spidev"
                f"{self.bus}.{self.device}"
            ),
        }

    def configure(
        self,
        rate=100,
        range_g=2,
    ):
        if rate not in self.RATE_CODES:
            raise ValueError(
                f"Unsupported rate: {rate}"
            )

        if range_g not in self.RANGE_CODES:
            raise ValueError(
                f"Unsupported range: +/-{range_g} g"
            )

        # Standby
        self._write_reg(
            self.POWER_CTL,
            0x00,
        )

        time.sleep(0.02)

        # FULL_RES bit = 1
        # plus requested range bits
        data_format = (
            0x08 |
            self.RANGE_CODES[range_g]
        )

        self._write_reg(
            self.DATA_FORMAT,
            data_format,
        )

        self._write_reg(
            self.BW_RATE,
            self.RATE_CODES[rate],
        )

        # Measurement mode
        self._write_reg(
            self.POWER_CTL,
            0x08,
        )

        time.sleep(0.05)

    @staticmethod
    def _signed16(low, high):
        value = low | (high << 8)

        if value & 0x8000:
            value -= 65536

        return value

    def read_raw(self):
        data = self._read_regs(
            self.DATAX0,
            6,
        )

        return (
            self._signed16(data[0], data[1]),
            self._signed16(data[2], data[3]),
            self._signed16(data[4], data[5]),
        )

    def read_g(self):
        x, y, z = self.read_raw()

        # ADXL345 full-resolution mode:
        # approximately 3.9 mg/LSB
        scale = 0.0039

        return (
            x * scale,
            y * scale,
            z * scale,
        )
