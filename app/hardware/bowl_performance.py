import math
import os
import subprocess
import tempfile
import time
import wave

import numpy as np

from app.hardware.adxl345 import ADXL345

from app.hardware.resonance_player import (
    AUDIO_DEVICE,
    AUDIO_RATE,
    ADXL_RATE,
    _sync_amplitude,
)


MAX_DRIVE_PERCENT = 2.0


def _smooth01(x):
    x = max(0.0, min(1.0, float(x)))

    return 0.5 - 0.5 * math.cos(
        math.pi * x
    )


def _continuous_envelope(t, duration):
    fade = min(
        3.0,
        max(
            0.5,
            duration * 0.15,
        ),
    )

    if t < fade:
        return _smooth01(
            t / fade
        )

    if t > duration - fade:
        return _smooth01(
            (duration - t) / fade
        )

    return 1.0


def _breathing_envelope(t, duration):
    edge = _continuous_envelope(
        t,
        duration,
    )

    cycle_seconds = 12.0

    cycle = (
        0.5 -
        0.5 * math.cos(
            2.0 *
            math.pi *
            t /
            cycle_seconds
        )
    )

    breathing = (
        0.18 +
        0.82 * cycle
    )

    return edge * breathing


def _strike_envelope(t):
    attack = 0.08
    release = 0.55

    if t < 0:
        return 0.0

    if t < attack:
        return _smooth01(
            t / attack
        )

    t_release = t - attack

    if t_release < release:
        return 1.0 - _smooth01(
            t_release / release
        )

    return 0.0


def _performance_arrays(
    preset,
    center_frequency,
    peak_drive,
    duration,
    movement,
    character,
):
    preset = str(preset).lower()

    sample_count = int(
        duration * AUDIO_RATE
    )

    t = (
        np.arange(
            sample_count,
            dtype=np.float64,
        ) /
        AUDIO_RATE
    )

    envelope = np.zeros(
        sample_count,
        dtype=np.float64,
    )

    frequency = np.full(
        sample_count,
        center_frequency,
        dtype=np.float64,
    )

    if preset == "continuous":
        for i, ti in enumerate(t):
            envelope[i] = (
                _continuous_envelope(
                    ti,
                    duration,
                )
            )

        if character > 0:
            envelope *= (
                1.0 +
                0.08 *
                character *
                np.sin(
                    2.0 *
                    np.pi *
                    0.11 *
                    t
                )
            )

        depth = (
            2.0 * movement
        )

        frequency += (
            depth *
            (
                0.65 *
                np.sin(
                    2.0 *
                    np.pi *
                    0.067 *
                    t
                )
                +
                0.35 *
                np.sin(
                    2.0 *
                    np.pi *
                    0.029 *
                    t +
                    1.1
                )
            )
        )

    elif preset == "breathing":
        for i, ti in enumerate(t):
            envelope[i] = (
                _breathing_envelope(
                    ti,
                    duration,
                )
            )

        depth = (
            1.5 * movement
        )

        frequency += (
            depth *
            (
                0.7 *
                np.sin(
                    2.0 *
                    np.pi *
                    0.045 *
                    t
                )
                +
                0.3 *
                np.sin(
                    2.0 *
                    np.pi *
                    0.021 *
                    t +
                    0.8
                )
            )
        )

    elif preset == "strike":
        for i, ti in enumerate(t):
            envelope[i] = (
                _strike_envelope(
                    ti
                )
            )

    else:
        raise ValueError(
            "Unknown preset: "
            f"{preset}"
        )

    phase = (
        2.0 *
        np.pi *
        np.cumsum(
            frequency
        ) /
        AUDIO_RATE
    )

    signal = (
        np.sin(phase) *
        envelope *
        peak_drive
    )

    drive_percent = (
        envelope *
        peak_drive *
        100.0
    )

    return {
        "signal": signal,
        "frequency": frequency,
        "drive_percent": drive_percent,
        "envelope": envelope,
    }


def _build_signal(
    preset,
    center_frequency,
    peak_drive_percent,
    duration,
    movement,
    character,
):
    peak_drive = (
        peak_drive_percent /
        100.0
    )

    return _performance_arrays(
        preset=preset,
        center_frequency=center_frequency,
        peak_drive=peak_drive,
        duration=duration,
        movement=movement,
        character=character,
    )


def _make_performance_wave(
    preset,
    center_frequency,
    peak_drive_percent,
    duration,
    movement,
    character,

    signal_2_mode="mirror",

    signal_2_preset=None,
    signal_2_center_frequency=None,
    signal_2_peak_drive_percent=None,
    signal_2_movement=None,
    signal_2_character=None,
):
    signal_1 = _build_signal(
        preset=preset,
        center_frequency=center_frequency,
        peak_drive_percent=(
            peak_drive_percent
        ),
        duration=duration,
        movement=movement,
        character=character,
    )

    signal_2_mode = str(
        signal_2_mode
    ).lower()

    if signal_2_mode == "mirror":
        signal_2 = {
            "signal":
                signal_1["signal"].copy(),

            "frequency":
                signal_1["frequency"].copy(),

            "drive_percent":
                signal_1[
                    "drive_percent"
                ].copy(),

            "envelope":
                signal_1[
                    "envelope"
                ].copy(),
        }

        signal_2_config = {
            "mode": "mirror",
            "preset": preset,
            "center_frequency_hz":
                center_frequency,
            "peak_drive_percent":
                peak_drive_percent,
            "movement": movement,
            "character": character,
        }

    elif signal_2_mode == "off":
        signal_2 = {
            "signal":
                np.zeros_like(
                    signal_1["signal"]
                ),

            "frequency":
                np.zeros_like(
                    signal_1["frequency"]
                ),

            "drive_percent":
                np.zeros_like(
                    signal_1[
                        "drive_percent"
                    ]
                ),

            "envelope":
                np.zeros_like(
                    signal_1["envelope"]
                ),
        }

        signal_2_config = {
            "mode": "off",
            "preset": None,
            "center_frequency_hz": None,
            "peak_drive_percent": 0.0,
            "movement": 0.0,
            "character": 0.0,
        }

    elif signal_2_mode == "independent":
        if signal_2_preset is None:
            signal_2_preset = preset

        if (
            signal_2_center_frequency
            is None
        ):
            signal_2_center_frequency = (
                center_frequency
            )

        if (
            signal_2_peak_drive_percent
            is None
        ):
            signal_2_peak_drive_percent = (
                peak_drive_percent
            )

        if signal_2_movement is None:
            signal_2_movement = movement

        if signal_2_character is None:
            signal_2_character = (
                character
            )

        signal_2 = _build_signal(
            preset=signal_2_preset,

            center_frequency=(
                signal_2_center_frequency
            ),

            peak_drive_percent=(
                signal_2_peak_drive_percent
            ),

            duration=duration,

            movement=signal_2_movement,

            character=signal_2_character,
        )

        signal_2_config = {
            "mode": "independent",

            "preset":
                signal_2_preset,

            "center_frequency_hz":
                signal_2_center_frequency,

            "peak_drive_percent":
                signal_2_peak_drive_percent,

            "movement":
                signal_2_movement,

            "character":
                signal_2_character,
        }

    else:
        raise ValueError(
            "signal_2_mode must be "
            "'mirror', 'independent', "
            "or 'off'"
        )

    stereo = np.column_stack(
        (
            signal_1["signal"],
            signal_2["signal"],
        )
    )

    stereo = np.clip(
        stereo,
        -1.0,
        1.0,
    )

    pcm = (
        stereo *
        32767.0
    ).astype(
        np.int16
    )

    fd, path = tempfile.mkstemp(
        suffix=".wav",
        prefix="bowl_performance_",
    )

    os.close(fd)

    with wave.open(
        path,
        "wb",
    ) as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(
            AUDIO_RATE
        )
        wav.writeframes(
            pcm.tobytes()
        )

    return (
        path,
        signal_1,
        signal_2,
        signal_2_config,
    )


def _build_points(
    times,
    xs,
    ys,
    zs,
    signal_1_frequency,
    signal_1_drive,
):
    if len(times) < 10:
        return []

    times = np.asarray(
        times,
        dtype=np.float64,
    )

    xs = np.asarray(
        xs,
        dtype=np.float64,
    )

    ys = np.asarray(
        ys,
        dtype=np.float64,
    )

    zs = np.asarray(
        zs,
        dtype=np.float64,
    )

    points = []

    window_seconds = 0.250
    step_seconds = 0.050

    start = float(
        times[0]
    )

    end = float(
        times[-1]
    )

    center = (
        start +
        window_seconds / 2.0
    )

    while (
        center +
        window_seconds / 2.0
        <= end
    ):
        low = (
            center -
            window_seconds / 2.0
        )

        high = (
            center +
            window_seconds / 2.0
        )

        mask = (
            (times >= low) &
            (times <= high)
        )

        if np.count_nonzero(
            mask
        ) >= 10:
            relative_time = (
                center - start
            )

            audio_index = int(
                relative_time *
                AUDIO_RATE
            )

            audio_index = max(
                0,
                min(
                    audio_index,
                    len(
                        signal_1_frequency
                    ) - 1,
                ),
            )

            frequency = float(
                signal_1_frequency[
                    audio_index
                ]
            )

            drive_percent = float(
                signal_1_drive[
                    audio_index
                ]
            )

            tx = (
                times[mask] -
                times[mask][0]
            )

            x_amp = _sync_amplitude(
                tx,
                xs[mask],
                frequency,
            )

            y_amp = _sync_amplitude(
                tx,
                ys[mask],
                frequency,
            )

            z_amp = _sync_amplitude(
                tx,
                zs[mask],
                frequency,
            )

            response = math.sqrt(
                x_amp * x_amp +
                y_amp * y_amp +
                z_amp * z_amp
            )

            points.append({
                "time":
                    round(
                        relative_time,
                        4,
                    ),

                "frequency_hz":
                    frequency,

                "drive_percent":
                    drive_percent,

                "response_g":
                    response,

                "x_g":
                    x_amp,

                "y_g":
                    y_amp,

                "z_g":
                    z_amp,
            })

        center += step_seconds

    return points


def play_performance(
    preset="continuous",
    center_frequency=529.0,
    peak_drive_percent=0.10,
    duration=15.0,
    movement=0.5,
    character=0.5,

    signal_2_mode="mirror",

    signal_2_preset=None,
    signal_2_center_frequency=None,
    signal_2_peak_drive_percent=None,
    signal_2_movement=None,
    signal_2_character=None,
):
    preset = str(
        preset
    ).lower()

    signal_2_mode = str(
        signal_2_mode
    ).lower()

    center_frequency = float(
        center_frequency
    )

    peak_drive_percent = float(
        peak_drive_percent
    )

    duration = float(
        duration
    )

    movement = float(
        movement
    )

    character = float(
        character
    )

    if preset not in (
        "continuous",
        "strike",
        "breathing",
    ):
        raise ValueError(
            "Preset must be "
            "continuous, strike, "
            "or breathing"
        )

    if not (
        20.0 <=
        center_frequency <=
        2000.0
    ):
        raise ValueError(
            "Frequency must be "
            "20-2000 Hz"
        )

    if not (
        0.0 <
        peak_drive_percent <=
        MAX_DRIVE_PERCENT
    ):
        raise ValueError(
            "Signal 1 drive must be "
            f"> 0 and <= "
            f"{MAX_DRIVE_PERCENT}%"
        )

    if duration < 2.0:
        raise ValueError(
            "Performance must be at "
            "least 2 seconds"
        )

    if duration > 120.0:
        raise ValueError(
            "Performance limited to "
            "120 seconds"
        )

    if preset == "strike":
        duration = max(
            duration,
            6.0,
        )

    movement = max(
        0.0,
        min(
            1.0,
            movement,
        ),
    )

    character = max(
        0.0,
        min(
            1.0,
            character,
        ),
    )

    if (
        signal_2_mode ==
        "independent"
    ):
        if (
            signal_2_center_frequency
            is None
        ):
            signal_2_center_frequency = (
                center_frequency
            )

        if (
            signal_2_peak_drive_percent
            is None
        ):
            signal_2_peak_drive_percent = (
                peak_drive_percent
            )

        signal_2_center_frequency = float(
            signal_2_center_frequency
        )

        signal_2_peak_drive_percent = float(
            signal_2_peak_drive_percent
        )

        if not (
            20.0 <=
            signal_2_center_frequency <=
            2000.0
        ):
            raise ValueError(
                "Signal 2 frequency must "
                "be 20-2000 Hz"
            )

        if not (
            0.0 <
            signal_2_peak_drive_percent <=
            MAX_DRIVE_PERCENT
        ):
            raise ValueError(
                "Signal 2 drive must be "
                f"> 0 and <= "
                f"{MAX_DRIVE_PERCENT}%"
            )

    wav_path = None
    sensor = None
    player = None

    times = []
    xs = []
    ys = []
    zs = []

    invalid_samples = 0
    total_reads = 0

    try:
        (
            wav_path,
            signal_1,
            signal_2,
            signal_2_config,
        ) = _make_performance_wave(
            preset=preset,

            center_frequency=(
                center_frequency
            ),

            peak_drive_percent=(
                peak_drive_percent
            ),

            duration=duration,

            movement=movement,

            character=character,

            signal_2_mode=(
                signal_2_mode
            ),

            signal_2_preset=(
                signal_2_preset
            ),

            signal_2_center_frequency=(
                signal_2_center_frequency
            ),

            signal_2_peak_drive_percent=(
                signal_2_peak_drive_percent
            ),

            signal_2_movement=(
                signal_2_movement
            ),

            signal_2_character=(
                signal_2_character
            ),
        )

        sensor = ADXL345()

        sensor.open()

        sensor.configure(
            rate=ADXL_RATE,
            range_g=16,
        )

        player = subprocess.Popen(
            [
                "aplay",
                "-q",
                "-D",
                AUDIO_DEVICE,
                wav_path,
            ],

            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        start = time.monotonic()

        sample_interval = (
            1.0 /
            ADXL_RATE
        )

        next_sample = start

        while player.poll() is None:
            now = time.monotonic()

            if now < next_sample:
                time.sleep(
                    min(
                        next_sample - now,
                        0.001,
                    )
                )

                continue

            total_reads += 1

            x, y, z = (
                sensor.read_g()
            )

            max_axis = max(
                abs(x),
                abs(y),
                abs(z),
            )

            if max_axis > 16.5:
                invalid_samples += 1

            else:
                times.append(
                    now
                )

                xs.append(
                    x
                )

                ys.append(
                    y
                )

                zs.append(
                    z
                )

            next_sample += (
                sample_interval
            )

        points = _build_points(
            times=times,
            xs=xs,
            ys=ys,
            zs=zs,

            signal_1_frequency=(
                signal_1["frequency"]
            ),

            signal_1_drive=(
                signal_1[
                    "drive_percent"
                ]
            ),
        )

        if points:
            peak_point = max(
                points,
                key=lambda p:
                    p["response_g"],
            )

            peak_response_g = (
                peak_point[
                    "response_g"
                ]
            )

            peak_response_time = (
                peak_point[
                    "time"
                ]
            )

        else:
            peak_response_g = 0.0
            peak_response_time = 0.0

        max_abs_g = 0.0

        if xs:
            max_abs_g = max(
                np.max(
                    np.abs(xs)
                ),
                np.max(
                    np.abs(ys)
                ),
                np.max(
                    np.abs(zs)
                ),
            )

        signal_1_config = {
            "mode": "independent",

            "preset":
                preset,

            "center_frequency_hz":
                center_frequency,

            "peak_drive_percent":
                peak_drive_percent,

            "movement":
                movement,

            "character":
                character,

            "dac_output":
                "left",
        }

        signal_2_config[
            "dac_output"
        ] = "right"

        return {
            "ok": True,

            # New two-signal representation
            "signal_1":
                signal_1_config,

            "signal_2":
                signal_2_config,

            # Legacy fields retained so
            # existing UI/API code continues
            # to work unchanged.
            "preset":
                preset,

            "center_frequency_hz":
                center_frequency,

            "peak_drive_percent":
                peak_drive_percent,

            "duration_seconds":
                duration,

            "movement":
                movement,

            "character":
                character,

            "peak_response_g":
                peak_response_g,

            "peak_response_time":
                peak_response_time,

            "max_abs_g":
                float(
                    max_abs_g
                ),

            "samples":
                len(times),

            "total_reads":
                total_reads,

            "invalid_samples":
                invalid_samples,

            "points":
                points,
        }

    finally:
        if (
            player is not None and
            player.poll() is None
        ):
            player.terminate()

            try:
                player.wait(
                    timeout=1.0
                )

            except subprocess.TimeoutExpired:
                player.kill()

        if sensor is not None:
            try:
                sensor.close()

            except Exception:
                pass

        if (
            wav_path and
            os.path.exists(
                wav_path
            )
        ):
            try:
                os.unlink(
                    wav_path
                )

            except OSError:
                pass
