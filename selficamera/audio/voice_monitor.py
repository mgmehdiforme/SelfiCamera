"""Microphone audio reactivity monitor computing RMS voice energy with asymmetric attack/decay."""

from __future__ import annotations

import logging
import math
import time
from typing import Optional
import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

logger = logging.getLogger(__name__)


class AudioMonitorWorker(QThread):
    """Background QThread monitoring microphone input via sounddevice and emitting normalized voice energy."""

    energy_updated = Signal(float)  # Emits smoothed energy in range [0.0, 1.0]
    error_occurred = Signal(str)

    def __init__(
        self,
        device: Optional[str | int] = None,
        sample_rate: int = 44100,
        block_size: int = 512,
        min_db: float = -48.0,
        max_db: float = -12.0,
        mock_mode: bool = False,
    ) -> None:
        super().__init__()
        self.device = device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.min_db = min_db
        self.max_db = max_db
        self.mock_mode = mock_mode

        self._running = False
        self._current_energy: float = 0.0
        self._mutex = QMutex()
        self._mock_step: int = 0

    @property
    def current_energy(self) -> float:
        """Return the current smoothed audio energy."""
        with QMutexLocker(self._mutex):
            return self._current_energy

    def compute_energy_from_pcm(self, pcm_data: np.ndarray) -> float:
        """Calculate RMS dBFS and apply asymmetric attack/decay envelope filter."""
        if pcm_data.size == 0:
            return 0.0

        # Compute Root Mean Square (RMS)
        rms = float(np.sqrt(np.mean(np.square(pcm_data))))
        # Convert to logarithmic dBFS
        db = 20.0 * math.log10(max(rms, 1e-5))

        # Normalize to [0.0, 1.0] range
        if db <= self.min_db:
            raw_energy = 0.0
        elif db >= self.max_db:
            raw_energy = 1.0
        else:
            raw_energy = (db - self.min_db) / (self.max_db - self.min_db)

        # Asymmetric Attack/Decay smoothing
        with QMutexLocker(self._mutex):
            if raw_energy > self._current_energy:
                # Fast attack (~30ms response)
                self._current_energy = 0.65 * self._current_energy + 0.35 * raw_energy
            else:
                # Smooth decay (~120ms falloff)
                self._current_energy = 0.88 * self._current_energy + 0.12 * raw_energy

            return self._current_energy

    def stop(self) -> None:
        """Stop worker cleanly."""
        self._running = False
        self.wait(1000)

    def run(self) -> None:
        """Audio streaming loop."""
        self._running = True

        if self.mock_mode:
            logger.info("Operating in mock audio monitor mode (synthetic sine wave).")
            while self._running:
                self._mock_step += 1
                # Synthetic pulsing speech energy pattern: bursts of speech separated by silence
                phase = (self._mock_step % 120) / 120.0
                if phase < 0.65:
                    # Active speech simulation
                    raw = 0.4 + 0.45 * np.sin(self._mock_step * 0.25)
                else:
                    # Ambient silence
                    raw = 0.02

                clamped_raw = max(0.0, min(1.0, float(raw)))
                with QMutexLocker(self._mutex):
                    if clamped_raw > self._current_energy:
                        self._current_energy = 0.65 * self._current_energy + 0.35 * clamped_raw
                    else:
                        self._current_energy = 0.88 * self._current_energy + 0.12 * clamped_raw
                    energy = self._current_energy

                self.energy_updated.emit(energy)
                self.msleep(15)
            return

        try:
            import sounddevice as sd

            def audio_callback(indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
                if not self._running:
                    return
                mono = indata[:, 0] if indata.ndim > 1 else indata
                energy = self.compute_energy_from_pcm(mono)
                self.energy_updated.emit(energy)

            with sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                callback=audio_callback,
            ):
                logger.info("Audio stream started on device %s", self.device)
                while self._running:
                    self.msleep(50)

        except Exception as e:
            logger.warning("Microphone stream unavailable (%s). Voice aura will remain quiescent.", e)
            self.error_occurred.emit(str(e))
            # Quiescent loop: emit 0.0 without crashing
            while self._running:
                with QMutexLocker(self._mutex):
                    self._current_energy = 0.0
                self.energy_updated.emit(0.0)
                self.msleep(100)
