import threading
import time
import wave

from pathlib import Path

from arduino.app_peripherals.microphone import Microphone
from arduino.app_bricks.asr import WAVAutomaticSpeechRecognition
from arduino.app_utils import App


class Recorder:

    def __init__(self):
        self.microphone = Microphone(
            "hw:0,1",
            sample_rate=Microphone.RATE_16K,
            channels=Microphone.CHANNELS_MONO,
            buffer_size=1120,
            shared=False
        )

        self.wav_file = Path("recordings/recording.wav")
        self.wav_file.parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        self.mode = "idle"
        self.text = ""
        self.error = ""
        self.duration = 0.0
        self.asr_duration = 0.0
        self.started_at = None

    def start_record(self):
        with self.lock:
            if self.mode != "idle":
                return {"error": "Application occupée"}

            self.mode = "recording"
            self.text = ""
            self.error = ""
            self.duration = 0.0
            self.asr_duration = 0.0
            self.started_at = time.monotonic()
            self.stop_event.clear()

        threading.Thread(
            target=self._record_worker,
            daemon=True
        ).start()

        return {"status": "recording"}

    def stop_record(self):
        with self.lock:
            if self.mode != "recording":
                return {"error": "Aucun enregistrement en cours"}

            self.mode = "stopping"
            self.stop_event.set()

        return {"status": "stopping"}

    def _record_worker(self):
        chunks = []
        started = False

        try:
            self.microphone.start()
            started = True

            print("Microphone : enregistrement", flush=True)

            for chunk in self.microphone.stream():
                if self.stop_event.is_set():
                    break

                chunks.append(chunk.tobytes())

            with self.lock:
                self.duration = (
                    time.monotonic() - self.started_at
                )

            if not chunks:
                raise RuntimeError("Aucune donnée audio enregistrée")

            # Construction du fichier WAV
            with wave.open(str(self.wav_file), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)

                for chunk in chunks:
                    wav.writeframes(chunk)

            print(
                f"WAV enregistré : {self.wav_file}",
                flush=True
            )

        except Exception as exc:
            self._set_error(exc)
            return

        finally:
            if started:
                self.microphone.stop()

        # Le microphone est libéré avant la transcription.
        self._transcribe()

    def _transcribe(self):
        with self.lock:
            self.mode = "transcribing"

        try:
            print("ASR : transcription en cours", flush=True)

            with open(self.wav_file, "rb") as file:
                audio_bytes = file.read()

            asr = WAVAutomaticSpeechRecognition(audio_bytes)
            App.start_brick(asr)

            start = time.monotonic()
            text = asr.transcribe()
            elapsed = time.monotonic() - start

            with self.lock:
                self.text = text
                self.asr_duration = elapsed
                self.mode = "idle"

            print(f"Transcription : {text}", flush=True)
            print(
                f"Durée ASR : {elapsed:.2f} secondes",
                flush=True
            )

        except Exception as exc:
            self._set_error(exc)

    def _set_error(self, exc):
        print(f"Erreur : {exc}", flush=True)

        with self.lock:
            self.error = str(exc)
            self.mode = "idle"

    def status(self):
        with self.lock:
            duration = self.duration

            if self.mode == "recording":
                duration = time.monotonic() - self.started_at

            return {
                "mode": self.mode,
                "duration": round(duration, 1),
                "text": self.text,
                "error": self.error,
                "asr_duration": round(self.asr_duration, 2)
            }