"""Tests for AudioMonitorWorker and voice reactivity energy calculation."""

import numpy as np
from selficamera.audio.voice_monitor import AudioMonitorWorker


def test_audio_energy_bounds(mock_audio_pcm_speech: np.ndarray):
    """Verify computed energy is strictly bounded in [0.0, 1.0]."""
    worker = AudioMonitorWorker(mock_mode=True)
    energy = worker.compute_energy_from_pcm(mock_audio_pcm_speech)
    assert 0.0 <= energy <= 1.0


def test_speech_vs_silence_energy(mock_audio_pcm_speech: np.ndarray, mock_audio_pcm_silence: np.ndarray):
    """Verify that speech produces higher energy than silence."""
    worker = AudioMonitorWorker(mock_mode=True)

    # Process speech multiple times to build attack
    for _ in range(5):
        speech_energy = worker.compute_energy_from_pcm(mock_audio_pcm_speech)

    worker_silent = AudioMonitorWorker(mock_mode=True)
    silent_energy = worker_silent.compute_energy_from_pcm(mock_audio_pcm_silence)

    assert speech_energy > silent_energy
    assert speech_energy > 0.25
    assert silent_energy < 0.10


def test_asymmetric_decay():
    """Verify that energy decays smoothly rather than instantaneously dropping to zero."""
    worker = AudioMonitorWorker(mock_mode=True)
    # Prime with loud speech
    loud_pcm = np.full(512, 0.8, dtype=np.float32)
    worker.compute_energy_from_pcm(loud_pcm)
    high_energy = worker.current_energy
    assert high_energy > 0.3

    # Now provide silence
    silent_pcm = np.zeros(512, dtype=np.float32)
    decay_energy = worker.compute_energy_from_pcm(silent_pcm)

    # Must have decayed, but still be > 0.0 (smooth falloff)
    assert 0.0 < decay_energy < high_energy
    # Expected: approx 0.88 * high_energy
    assert abs(decay_energy - (0.88 * high_energy)) < 0.05


def test_mock_audio_worker_emits_signals(qtbot):
    """Verify that mock audio worker emits energy_updated signals."""
    worker = AudioMonitorWorker(mock_mode=True)
    signals_received = []

    worker.energy_updated.connect(lambda e: signals_received.append(e))

    with qtbot.waitSignal(worker.energy_updated, timeout=1000):
        worker.start()

    assert len(signals_received) > 0
    assert 0.0 <= signals_received[-1] <= 1.0
    worker.stop()
