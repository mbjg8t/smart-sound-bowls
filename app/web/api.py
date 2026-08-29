from flask import Blueprint, current_app, jsonify, request


api_bp = Blueprint("api", __name__)


def controller():
    return current_app.extensions["sound_bowl_controller"]


@api_bp.get("/state")
def state():
    return jsonify(controller().get_state())


@api_bp.post("/audio/configure")
def audio_configure():
    data = request.get_json(silent=True) or {}

    try:
        state = controller().configure_audio(
            frequency_hz=data.get("frequency_hz"),
            amplitude=data.get("amplitude"),
            waveform=data.get("waveform"),
        )

        return jsonify({
            "ok": True,
            "state": state,
        })

    except (ValueError, TypeError) as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400


@api_bp.post("/audio/start")
def audio_start():
    return jsonify({
        "ok": True,
        "state": controller().start_audio(),
    })


@api_bp.post("/audio/stop")
def audio_stop():
    return jsonify({
        "ok": True,
        "state": controller().stop_audio(),
    })


# ============================================================
# HARDWARE TEST API
# ============================================================

from app.hardware.alsa import ALSA


@api_bp.get("/hardware/alsa")
def hardware_alsa():

    return jsonify({
        "ok": True,
        "alsa": ALSA.status(),
    })


@api_bp.get("/hardware/dac")
def hardware_dac():

    dac = current_app.extensions["pcm5122"]

    return jsonify({
        "ok": True,
        "dac": dac.status(),
    })


@api_bp.post("/hardware/dac/test")
def hardware_dac_test():

    data = request.get_json(silent=True) or {}

    dac = current_app.extensions["pcm5122"]

    try:

        result = dac.test(
            frequency_hz=data.get(
                "frequency_hz",
                220,
            ),
            amplitude=data.get(
                "amplitude",
                0.03,
            ),
            duration_s=data.get(
                "duration_s",
                2,
            ),
        )

        return jsonify(result)

    except Exception as exc:

        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400


@api_bp.get("/hardware/mic")
def hardware_mic():

    mic = current_app.extensions["inmp441"]

    return jsonify({
        "ok": True,
        "mic": mic.status(),
    })


@api_bp.post("/hardware/mic/test")
def hardware_mic_test():

    data = request.get_json(silent=True) or {}

    mic = current_app.extensions["inmp441"]

    try:

        result = mic.capture(
            duration_s=data.get(
                "duration_s",
                3,
            ),
        )

        return jsonify(result)

    except Exception as exc:

        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400


# ---------------------------------------------------------
# ADXL345
# ---------------------------------------------------------

import math
import os
import subprocess
import tempfile
import time
import wave

import numpy as np

from app.hardware.adxl345 import ADXL345


ADXL_SAMPLE_RATE = 800
AUDIO_DEVICE = "plughw:CARD=SmartBowlAudio,DEV=1"
AUDIO_RATE = 48000


def _make_stereo_tone(
    frequency,
    amplitude,
    duration,
):
    sample_count = int(
        AUDIO_RATE * duration
    )

    t = (
        np.arange(sample_count)
        / AUDIO_RATE
    )

    signal = (
        np.sin(
            2 *
            np.pi *
            frequency *
            t
        )
        *
        amplitude
    )

    pcm = np.clip(
        signal * 32767,
        -32768,
        32767,
    ).astype(np.int16)

    stereo = np.column_stack(
        (pcm, pcm)
    ).reshape(-1)

    temp = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    )

    temp.close()

    with wave.open(
        temp.name,
        "wb",
    ) as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(
            stereo.tobytes()
        )

    return temp.name


def _sync_amplitude(
    timestamps,
    signal,
    frequency,
):
    timestamps = np.asarray(
        timestamps,
        dtype=np.float64,
    )

    signal = np.asarray(
        signal,
        dtype=np.float64,
    )

    signal = signal - np.mean(signal)

    phase = (
        2 *
        np.pi *
        frequency *
        timestamps
    )

    s = np.sin(phase)
    c = np.cos(phase)

    a = (
        2.0 /
        len(signal) *
        np.sum(signal * s)
    )

    b = (
        2.0 /
        len(signal) *
        np.sum(signal * c)
    )

    return float(
        math.sqrt(
            a * a +
            b * b
        )
    )


def _measure_adxl_frequency(
    sensor,
    frequency,
    amplitude,
    settle_seconds,
    measure_seconds,
):
    total_duration = (
        settle_seconds +
        measure_seconds +
        0.02
    )

    filename = _make_stereo_tone(
        frequency,
        amplitude,
        total_duration,
    )

    playback = subprocess.Popen(
        [
            "aplay",
            "-q",
            "-D",
            AUDIO_DEVICE,
            filename,
        ]
    )

    timestamps = []
    samples = []

    start = time.perf_counter()
    measure_start = (
        start +
        settle_seconds
    )
    measure_end = (
        measure_start +
        measure_seconds
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
                ADXL_SAMPLE_RATE
            )

    finally:
        try:
            playback.wait(
                timeout=0.5
            )
        except subprocess.TimeoutExpired:
            playback.terminate()

        try:
            os.unlink(filename)
        except OSError:
            pass

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
            "Too few ADXL345 samples"
        )

    amp_x = _sync_amplitude(
        timestamps,
        data[:, 0],
        frequency,
    )

    amp_y = _sync_amplitude(
        timestamps,
        data[:, 1],
        frequency,
    )

    amp_z = _sync_amplitude(
        timestamps,
        data[:, 2],
        frequency,
    )

    vector = math.sqrt(
        amp_x ** 2 +
        amp_y ** 2 +
        amp_z ** 2
    )

    max_abs = float(
        np.max(
            np.abs(data)
        )
    )

    return {
        "frequency_hz":
            float(frequency),

        "amp_x_g":
            float(amp_x),

        "amp_y_g":
            float(amp_y),

        "amp_z_g":
            float(amp_z),

        "vector_amp_g":
            float(vector),

        "max_abs_g":
            max_abs,

        "samples":
            int(len(data)),
    }


@api_bp.get("/hardware/adxl345")
def api_adxl345_status():
    sensor = ADXL345()

    try:
        sensor.open()

        info = sensor.probe()

        return jsonify({
            "found":
                bool(info.get("found")),

            "device_id":
                int(
                    info.get(
                        "device_id",
                        0
                    )
                ),

            "spi":
                "/dev/spidev0.0",
        })

    except Exception as exc:
        return jsonify({
            "found": False,
            "device_id": 0,
            "spi":
                "/dev/spidev0.0",
            "error":
                str(exc),
        }), 500

    finally:
        sensor.close()


@api_bp.get(
    "/hardware/adxl345/sample"
)
def api_adxl345_sample():
    sensor = ADXL345()

    try:
        sensor.open()

        info = sensor.probe()

        if not info.get("found"):
            return jsonify({
                "ok": False,
                "error":
                    "ADXL345 not detected",
            }), 500

        sensor.configure(
            rate=100,
            range_g=16,
        )

        time.sleep(0.03)

        x, y, z = sensor.read_g()

        total = math.sqrt(
            x * x +
            y * y +
            z * z
        )

        return jsonify({
            "ok": True,
            "x": x,
            "y": y,
            "z": z,
            "total": total,
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500

    finally:
        sensor.close()


@api_bp.post(
    "/hardware/adxl345/vibration-test"
)
def api_adxl345_vibration_test():
    payload = request.get_json(
        silent=True
    ) or {}

    frequency = float(
        payload.get(
            "frequency",
            220,
        )
    )

    amplitude_percent = float(
        payload.get(
            "amplitude_percent",
            0.1,
        )
    )

    duration = float(
        payload.get(
            "duration",
            2,
        )
    )

    amplitude = (
        amplitude_percent /
        100.0
    )

    sensor = ADXL345()

    try:
        sensor.open()

        info = sensor.probe()

        if not info.get("found"):
            raise RuntimeError(
                "ADXL345 not detected"
            )

        sensor.configure(
            rate=800,
            range_g=16,
        )

        time.sleep(0.05)

        result = _measure_adxl_frequency(
            sensor=sensor,
            frequency=frequency,
            amplitude=amplitude,
            settle_seconds=0.05,
            measure_seconds=max(
                0.15,
                duration - 0.05,
            ),
        )

        result["ok"] = True
        result[
            "amplitude_percent"
        ] = amplitude_percent

        return jsonify(result)

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500

    finally:
        sensor.close()


@api_bp.post(
    "/hardware/adxl345/sweep"
)
def api_adxl345_sweep():
    payload = request.get_json(
        silent=True
    ) or {}

    start_hz = float(
        payload.get(
            "start_hz",
            80,
        )
    )

    stop_hz = float(
        payload.get(
            "stop_hz",
            380,
        )
    )

    step_hz = float(
        payload.get(
            "step_hz",
            5,
        )
    )

    amplitude_percent = float(
        payload.get(
            "amplitude_percent",
            0.1,
        )
    )

    settle_seconds = float(
        payload.get(
            "settle_seconds",
            0.05,
        )
    )

    measure_seconds = float(
        payload.get(
            "measure_seconds",
            0.15,
        )
    )

    if step_hz <= 0:
        return jsonify({
            "ok": False,
            "error":
                "Step must be greater than 0",
        }), 400

    if stop_hz <= start_hz:
        return jsonify({
            "ok": False,
            "error":
                "Stop must be greater than start",
        }), 400

    amplitude = (
        amplitude_percent /
        100.0
    )

    sensor = ADXL345()
    results = []

    try:
        sensor.open()

        info = sensor.probe()

        if not info.get("found"):
            raise RuntimeError(
                "ADXL345 not detected"
            )

        sensor.configure(
            rate=800,
            range_g=16,
        )

        time.sleep(0.05)

        frequency = start_hz

        while (
            frequency <=
            stop_hz + 0.0001
        ):
            result = (
                _measure_adxl_frequency(
                    sensor=sensor,
                    frequency=frequency,
                    amplitude=amplitude,
                    settle_seconds=
                        settle_seconds,
                    measure_seconds=
                        measure_seconds,
                )
            )

            results.append(result)

            frequency += step_hz

        ranked = sorted(
            results,
            key=lambda row:
                row["vector_amp_g"],
            reverse=True,
        )

        return jsonify({
            "ok": True,

            "sensor_location":
                "directly on exciter",

            "measurement_type":
                "exciter mechanical response",

            "amplitude_percent":
                amplitude_percent,

            "results":
                results,

            "peaks":
                ranked[:10],
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500

    finally:
        sensor.close()
