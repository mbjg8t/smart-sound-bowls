# Smart Sound Bowls

Raspberry Pi based resonant sound bowl excitation and feedback system.

## Initial Hardware

- Raspberry Pi 4
- Waveshare PCM5122 I2S DAC
- TPA3118 Class-D amplifier
- Bowl exciter
- INMP441 I2S microphone

## Architecture

The application separates:

1. Flask web interface
2. application/controller state
3. audio engine
4. hardware drivers
5. feedback and resonance processing

The Flask application does not directly control hardware.

The controller owns the system state and communicates with long-running
hardware/audio services.

## Initial Development Stage

The current AudioEngine uses a mock backend.

This allows the UI, API, controller, and state architecture to be tested
without energizing the amplifier or exciter.

## Run

Create a virtual environment:

    python3 -m venv .venv

Activate:

    source .venv/bin/activate

Install:

    pip install -r requirements.txt

Run:

    python run.py

Open:

    http://rpi.local:5000

## Utilities

Audio:

    /utilities/audio

Microphone:

    /utilities/microphone

System:

    /utilities/system

## Planned Signal Path

    Raspberry Pi
        |
        | I2S
        v
    PCM5122 DAC
        |
        | analog audio
        v
    TPA3118 amplifier
        |
        v
    Exciter
        |
        v
    Sound Bowl

Feedback:

    Sound Bowl
        |
        v
    INMP441
        |
        | I2S PCM_DIN
        v
    Raspberry Pi

Future feedback sources include accelerometer and piezo vibration sensing.
