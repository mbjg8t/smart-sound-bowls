import math
import os
import subprocess
import tempfile
import time
import wave

import numpy as np

from app.hardware.adxl345 import ADXL345


AUDIO_DEVICE = "plughw:CARD=SmartBowlAudio,DEV=1"
AUDIO_RATE = 48000
ADXL_RATE = 800


def _envelope(
    t,
    attack,
    hold,
    decay,
):
    if t < 0:
        return 0.0

    if attack > 0 and t < attack:
        # Smooth half-cosine rise.
        phase = t / attack

        return 0.5 - 0.5 * math.cos(
            math.pi * phase
        )

    hold_end = attack + hold

    if t < hold_end:
        return 1.0

    decay_end = hold_end + decay

    if decay > 0 and t < decay_end:
        phase = (
            t - hold_end
        ) / decay

        return 0.5 + 0.5 * math.cos(
            math.pi * phase
        )

    return 0.0


def _make_wave(
    frequency,
    peak_drive,
    attack,
    hold,
    decay,
):
    duration = (
        attack +
        hold +
        decay
    )

    sample_count = int(
        duration *
        AUDIO_RATE
    )

    t = (
        np.arange(sample_count)
        / AUDIO_RATE
    )

    envelope = np.zeros(
        sample_count,
        dtype=np.float64,
    )

    for i in range(sample_count):
        envelope[i] = _envelope(
            t[i],
            attack,
            hold,
            decay,
        )

    signal = (
        np.sin(
            2 *
            np.pi *
            frequency *
            t
        )
        *
        envelope
        *
        peak_drive
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

    filename = temp.name
    temp.close()

    with wave.open(
        filename,
        "wb",
    ) as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_RATE)

        wf.writeframes(
            stereo.tobytes()
        )

    return filename, duration


def _sync_amplitude(
    times,
    values,
    frequency,
):
    if len(values) < 5:
        return 0.0

    times = np.asarray(
        times,
        dtype=np.float64,
    )

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    values = (
        values -
        np.mean(values)
    )

    phase = (
        2 *
        np.pi *
        frequency *
        times
    )

    sin_ref = np.sin(phase)
    cos_ref = np.cos(phase)

    a = (
        2.0 /
        len(values) *
        np.sum(
            values *
            sin_ref
        )
    )

    b = (
        2.0 /
        len(values) *
        np.sum(
            values *
            cos_ref
        )
    )

    return float(
        math.sqrt(
            a * a +
            b * b
        )
    )


def _build_response_points(
    timestamps,
    samples,
    frequency,
    peak_drive_percent,
    attack,
    hold,
    decay,
    window=0.25,
    step=0.05,
):
    timestamps = np.asarray(
        timestamps,
        dtype=np.float64,
    )

    samples = np.asarray(
        samples,
        dtype=np.float64,
    )

    if len(samples) == 0:
        return []

    total_duration = (
        attack +
        hold +
        decay
    )

    points = []

    start = 0.0

    while start < total_duration:

        end = start + window

        mask = (
            (timestamps >= start) &
            (timestamps < end)
        )

        indices = np.where(mask)[0]

        if len(indices) >= 10:

            t = timestamps[indices]

            block = samples[indices]

            x = _sync_amplitude(
                t,
                block[:, 0],
                frequency,
            )

            y = _sync_amplitude(
                t,
                block[:, 1],
                frequency,
            )

            z = _sync_amplitude(
                t,
                block[:, 2],
                frequency,
            )

            response = math.sqrt(
                x * x +
                y * y +
                z * z
            )

            center = (
                start +
                window / 2
            )

            envelope = _envelope(
                center,
                attack,
                hold,
                decay,
            )

            points.append({
                "time": round(
                    center,
                    4,
                ),

                "drive_percent":
                    float(
                        peak_drive_percent *
                        envelope
                    ),

                "response_g":
                    float(response),

                "x_g":
                    float(x),

                "y_g":
                    float(y),

                "z_g":
                    float(z),
            })

        start += step

    return points


def play_resonance(
    frequency=529.0,
    peak_drive_percent=0.5,
    attack=3.0,
    hold=5.0,
    decay=8.0,
):
    frequency = float(frequency)

    peak_drive_percent = float(
        peak_drive_percent
    )

    attack = float(attack)
    hold = float(hold)
    decay = float(decay)

    if frequency < 20:
        raise ValueError(
            "Frequency too low"
        )

    if frequency > 2000:
        raise ValueError(
            "Frequency too high"
        )

    if peak_drive_percent <= 0:
        raise ValueError(
            "Drive must be greater than 0"
        )

    # Conservative prototype safety limit.
    if peak_drive_percent > 2.0:
        raise ValueError(
            "Drive is currently limited to 2%"
        )

    if attack < 0:
        raise ValueError(
            "Attack cannot be negative"
        )

    if hold < 0:
        raise ValueError(
            "Hold cannot be negative"
        )

    if decay < 0:
        raise ValueError(
            "Decay cannot be negative"
        )

    duration = (
        attack +
        hold +
        decay
    )

    if duration < 0.25:
        raise ValueError(
            "Envelope is too short"
        )

    if duration > 60:
        raise ValueError(
            "Envelope is limited to 60 seconds"
        )

    peak_drive = (
        peak_drive_percent /
        100.0
    )

    filename, duration = _make_wave(
        frequency,
        peak_drive,
        attack,
        hold,
        decay,
    )

    sensor = ADXL345()

    playback = None

    timestamps = []
    samples = []

    total_reads = 0
    invalid_samples = 0

    try:
        sensor.open()

        info = sensor.probe()

        if not info.get("found"):
            raise RuntimeError(
                "ADXL345 not detected"
            )

        sensor.configure(
            rate=ADXL_RATE,
            range_g=16,
        )

        time.sleep(0.05)

        playback = subprocess.Popen(
            [
                "aplay",
                "-q",
                "-D",
                AUDIO_DEVICE,
                filename,
            ]
        )

        start_time = time.perf_counter()

        next_sample = start_time

        end_time = (
            start_time +
            duration
        )

        while True:

            now = time.perf_counter()

            if now >= end_time:
                break

            if now < next_sample:
                continue

            x, y, z = sensor.read_g()

            total_reads += 1

            # ADXL345 is configured for +/-16 g.
            # Reject impossible values caused by a bad SPI read
            # or corrupted sample rather than allowing them to
            # contaminate response/safety calculations.
            if (
                abs(x) > 16.5 or
                abs(y) > 16.5 or
                abs(z) > 16.5
            ):
                invalid_samples += 1

                next_sample += (
                    1.0 /
                    ADXL_RATE
                )

                continue

            timestamps.append(
                now -
                start_time
            )

            samples.append(
                (x, y, z)
            )

            next_sample += (
                1.0 /
                ADXL_RATE
            )

        playback.wait(
            timeout=2
        )

        data = np.asarray(
            samples,
            dtype=np.float64,
        )

        max_abs_g = 0.0

        if len(data):
            max_abs_g = float(
                np.max(
                    np.abs(data)
                )
            )

        points = _build_response_points(
            timestamps,
            samples,
            frequency,
            peak_drive_percent,
            attack,
            hold,
            decay,
        )

        peak_response = 0.0
        peak_response_time = 0.0

        if points:
            strongest = max(
                points,
                key=lambda p:
                    p["response_g"],
            )

            peak_response = strongest[
                "response_g"
            ]

            peak_response_time = strongest[
                "time"
            ]

        return {
            "ok": True,

            "frequency_hz":
                frequency,

            "peak_drive_percent":
                peak_drive_percent,

            "attack_seconds":
                attack,

            "hold_seconds":
                hold,

            "decay_seconds":
                decay,

            "duration_seconds":
                duration,

            "peak_response_g":
                peak_response,

            "peak_response_time":
                peak_response_time,

            "max_abs_g":
                max_abs_g,

            "samples":
                len(samples),

            "total_reads":
                total_reads,

            "invalid_samples":
                invalid_samples,

            "points":
                points,
        }

    finally:

        if playback is not None:

            if playback.poll() is None:

                playback.terminate()

                try:
                    playback.wait(
                        timeout=0.5
                    )

                except subprocess.TimeoutExpired:
                    playback.kill()

        sensor.close()

        try:
            os.unlink(filename)

        except OSError:
            pass
