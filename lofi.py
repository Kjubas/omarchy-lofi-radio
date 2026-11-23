import os
import sys
import signal
import random
import pathlib
import numpy as np
import sounddevice as sd

PID_FILE = pathlib.Path("/tmp/omarchy-lofi.pid")
VOL_FILE = pathlib.Path("/tmp/omarchy-lofi.vol")

PID_FILE.write_text(str(os.getpid()))
if not VOL_FILE.exists():
    VOL_FILE.write_text("0.8")

running = True
def handle_stop(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)

def get_volume():
    try:
        return max(0.0, min(1.5, float(VOL_FILE.read_text().strip())))
    except Exception:
        return 0.8

SR = 44100
mood = sys.argv.pop(1) if len(sys.argv) > 1 else "chill"

CHORDS_CHILL = (
    (53, 57, 60, 64, 67),
    (52, 55, 59, 62, 66),
    (50, 53, 57, 60, 64),
    (48, 52, 55, 59, 62),
)

CHORDS_RAINY = (
    (50, 53, 57, 60, 64),
    (55, 59, 62, 65, 69),
    (52, 55, 59, 62, 66),
    (45, 48, 52, 55, 59),
)

CHORDS_STUDY = (
    (48, 52, 55, 59, 62),
    (45, 48, 52, 55, 59),
    (53, 57, 60, 64, 67),
    (55, 59, 62, 65, 69),
)

SCALE_MAIN = (60, 62, 64, 67, 69, 72, 74, 76)

if mood == "rainy":
    BPM, RAIN, CHORDS = 68, 0.016, CHORDS_RAINY
elif mood == "study":
    BPM, RAIN, CHORDS = 84, 0.004, CHORDS_STUDY
else:
    BPM, RAIN, CHORDS = 76, 0.0, CHORDS_CHILL

rng = np.random.default_rng()

def lowpass(signal, width=6):
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(signal, kernel, mode="same")

def midi_to_freq(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))

def synth_rhodes_chord(notes, total_samples):
    t = np.arange(total_samples, dtype=np.float32) / SR
    env = np.minimum(1.0, t / 0.04) * np.exp(-t * 1.1)
    wave = np.zeros(total_samples, dtype=np.float32)
    for n in notes:
        for detune in (-0.18, 0.18):
            f = midi_to_freq(n) + detune
            osc = (
                np.sin(2 * np.pi * f * t)
                + 0.28 * np.sin(4 * np.pi * f * t) * np.exp(-t * 2.5)
                + 0.08 * np.sin(6 * np.pi * f * t) * np.exp(-t * 6.0)
            )
            wave += osc
    wave = (wave / (len(notes) * 2)) * env * 0.28
    return lowpass(wave, width=5)

def synth_bass(root_note, total_samples):
    t = np.arange(total_samples, dtype=np.float32) / SR
    env = np.minimum(1.0, t / 0.03) * np.exp(-t * 1.6)
    f = midi_to_freq(root_note - 12)
    bass = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)
    return bass * env * 0.24

def synth_melody_note(note, length):
    t = np.arange(length, dtype=np.float32) / SR
    env = np.minimum(1.0, t / 0.02) * np.exp(-t * 3.5)
    f = midi_to_freq(note)
    sig = np.sin(2 * np.pi * f * t) + 0.15 * np.sin(4 * np.pi * f * t)
    return lowpass(sig * env * 0.11, width=4)

def synth_kick(length):
    t = np.arange(length, dtype=np.float32) / SR
    freq = 42.0 + 75.0 * np.exp(-t * 32.0)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 11.0)
    return np.sin(phase) * env * 0.48

def synth_snare(length):
    t = np.arange(length, dtype=np.float32) / SR
    noise = rng.normal(0, 1, length).astype(np.float32)
    body = np.sin(2 * np.pi * 175 * t) * np.exp(-t * 22.0)
    env = np.exp(-t * 18.0)
    return lowpass(noise * env * 0.28, width=4) + body * 0.15

def synth_hat(length, velocity=1.0):
    t = np.arange(length, dtype=np.float32) / SR
    noise = rng.normal(0, 1, length).astype(np.float32)
    hp = np.diff(noise, prepend=0)
    env = np.exp(-t * 65.0)
    return hp * env * 0.06 * velocity

def render_bar(chord_notes):
    eighth_sec = (60.0 / BPM) / 2.0
    step_lengths = []
    for i in range(8):
        swing = 1.14 if i % 2 == 0 else 0.86
        step_lengths.append(int(SR * eighth_sec * swing))

    bar_len = sum(step_lengths)
    mix = np.zeros(bar_len, dtype=np.float32)

    root_note = next(iter(chord_notes))
    mix += synth_rhodes_chord(chord_notes, bar_len)
    mix += synth_bass(root_note, bar_len)

    pos = 0
    for step_idx, slen in enumerate(step_lengths):
        if step_idx in (0, 5) or (step_idx == 7 and random.random() < 0.25):
            k = synth_kick(slen)
            mix[pos:pos + len(k)] += k

        if step_idx in (2, 6):
            s = synth_snare(slen)
            mix[pos:pos + len(s)] += s

        vel = 1.0 if step_idx % 2 == 0 else 0.55
        h = synth_hat(slen, vel)
        mix[pos:pos + len(h)] += h

        if step_idx in (1, 3, 4, 6, 7) and random.random() < 0.42:
            note = random.choice(SCALE_MAIN)
            m_len = min(bar_len - pos, int(slen * 2.2))
            mel = synth_melody_note(note, m_len)
            mix[pos:pos + m_len] += mel

        pos += slen

    vinyl_hiss = rng.normal(0, 0.005, bar_len).astype(np.float32)
    crackle_mask = rng.random(bar_len) > 0.9994
    crackle = crackle_mask * rng.uniform(-0.14, 0.14, bar_len).astype(np.float32)
    mix += vinyl_hiss + crackle

    if RAIN > 0:
        rain = lowpass(rng.normal(0, RAIN, bar_len).astype(np.float32), width=6)
        mix += rain

    return np.tanh(mix * 1.15).astype(np.float32)

bar_idx = 0
chunk_size = 2048
with sd.OutputStream(samplerate=SR, channels=1, dtype="float32") as stream:
    while running:
        chord = CHORDS[bar_idx % len(CHORDS)]
        audio_bar = render_bar(chord)
        for start in range(0, len(audio_bar), chunk_size):
            if not running:
                break
            vol = get_volume()
            stream.write(audio_bar[start:start + chunk_size] * vol)
        bar_idx += 1
