from app.core.audio_engine import AudioEngine
from app.core.state import StateStore


class SoundBowlController:

    def __init__(self):
        self.state = StateStore()
        self.audio = AudioEngine()

    def get_state(self):
        return self.state.snapshot()

    def configure_audio(
        self,
        frequency_hz=None,
        amplitude=None,
        waveform=None,
    ):
        status = self.audio.configure(
            frequency_hz=frequency_hz,
            amplitude=amplitude,
            waveform=waveform,
        )

        self.state.update(
            frequency_hz=status["frequency_hz"],
            amplitude=status["amplitude"],
            waveform=status["waveform"],
        )

        return self.get_state()

    def start_audio(self):
        status = self.audio.start()

        self.state.update(
            output_running=status["running"],
            frequency_hz=status["frequency_hz"],
            amplitude=status["amplitude"],
            waveform=status["waveform"],
        )

        return self.get_state()

    def stop_audio(self):
        status = self.audio.stop()

        self.state.update(
            output_running=status["running"],
        )

        return self.get_state()
