#!/usr/bin/env python3
"""8-bit sound effects, synthesised at startup. No .wav files in the repo.

The shape is the one from the iThome day-28 pygame audio write-up: initialise the
mixer once, preload every effect into a dict keyed by a semantic name, and expose a
single play() that swallows errors so a machine with no audio device still runs the
game. Only the source of the samples differs -- square and LFSR-noise waves built
here rather than files loaded from disk, so the repo carries no audio assets.

To use recorded effects instead (Pixabay, freesound, your own), drop files into
audio/ named after the keys in voices() -- audio/attack.wav, audio/victory.ogg --
and they win over the synthesised blip. Anything missing stays 8-bit.

    listen: .venv/bin/python sounds.py
    check:  .venv/bin/python sounds.py --test
"""
import sys
from array import array
from pathlib import Path

import pygame

RATE = 44100            # what the mixer runs at, so the mp3 music is not downmixed
CHANNELS = 2
MASTER = 0.5            # baked into the synthesised buffers, so it is fixed at init
MUSIC_VOLUME = 0.35     # under the effects, which is where background music belongs
SFX_VOLUME = 1.0        # live trim on top of the built effects, set from the settings
SOUNDS = {}

TRACKS = {"field": "fantasy-medieval-rpg-music.mp3",
          "battle": "upbeat-rpg-battle.mp3"}
_playing = None


# ------------------------------------------------------------------ synthesis

def _tone(freq, ms, vol=0.25, duty=0.5, to=None, decay=True):
    """One square-wave note. `to` glides the pitch across the note; `duty` thins it."""
    n = max(1, int(RATE * ms / 1000))
    fade = max(1, int(RATE * 0.004))            # a few ms of ramp-in, or it clicks
    buf = array("h", bytes(2 * CHANNELS * n))
    phase = 0.0
    for i in range(n):
        f = freq if to is None else freq + (to - freq) * i / n
        phase += f / RATE
        env = min(1.0, i / fade) * ((1.0 - i / n) if decay else 1.0)
        v = int(32767 * MASTER * vol * env * (1 if phase % 1.0 < duty else -1))
        buf[i * CHANNELS] = buf[i * CHANNELS + 1] = v
    return buf


def _noise(ms, vol=0.25, period=8, decay=True):
    """The NES noise channel: a 15-bit LFSR. `period` is in 22050Hz-era samples."""
    n = max(1, int(RATE * ms / 1000))
    fade = max(1, int(RATE * 0.004))
    step = max(1, round(period * RATE / 22050))  # keep the timbre if RATE changes
    buf = array("h", bytes(2 * CHANNELS * n))
    reg, level = 0x7FFF, 1
    for i in range(n):
        if i % step == 0:
            bit = (reg ^ (reg >> 1)) & 1
            reg = (reg >> 1) | (bit << 14)
            level = 1 if reg & 1 else -1
        env = min(1.0, i / fade) * ((1.0 - i / n) if decay else 1.0)
        v = int(32767 * MASTER * vol * env * level)
        buf[i * CHANNELS] = buf[i * CHANNELS + 1] = v
    return buf


def _arp(freqs, ms, vol=0.22, duty=0.25):
    notes = [_tone(f, ms, vol, duty, decay=False) for f in freqs[:-1]]
    return sum(notes, array("h")) + _tone(freqs[-1], ms, vol, duty)


def _mix(a, b):
    n = max(len(a), len(b))
    out = array("h", bytes(2 * n))
    for i in range(n):
        s = (a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0)
        out[i] = max(-32768, min(32767, s))
    return out


def voices():
    return {
        "cursor":    _tone(880, 35, 0.18, duty=0.25),
        "confirm":   _tone(660, 35, 0.20, duty=0.25) + _tone(990, 60, 0.20, duty=0.25),
        "cancel":    _tone(440, 40, 0.18) + _tone(294, 70, 0.18),
        "place":     _tone(523, 90, 0.20, duty=0.25) + _tone(784, 170, 0.20, duty=0.25),
        "encounter": _arp([196, 262, 330], 60, 0.28, duty=0.125) + _noise(130, 0.22, period=10),
        "attack":    _noise(70, 0.30, period=3),
        "hit_foe":   _noise(140, 0.32, period=6) + _tone(147, 60, 0.20),
        "crit":      _noise(60, 0.35, period=2) + _noise(180, 0.35, period=5)
                     + _tone(1047, 90, 0.25, duty=0.25),
        "miss":      _noise(90, 0.12, period=16),
        "hurt":      _mix(_noise(220, 0.28, period=9), _tone(140, 240, 0.24, to=90)),
        "fire":      _noise(400, 0.30, period=14),
        "spell":     _tone(300, 240, 0.22, duty=0.125, to=1400),
        "heal":      _arp([523, 659, 784, 1047], 55),
        "sleep":     _tone(900, 420, 0.20, duty=0.25, to=180),
        "run":       _arp([784, 659, 523, 392], 45, 0.20),
        "victory":   _arp([523, 659, 784], 90, 0.25) + _tone(1047, 420, 0.25, duty=0.25),
        "levelup":   _arp([659, 784, 988], 80, 0.25) + _tone(1319, 520, 0.25, duty=0.25),
        "death":     _tone(392, 900, 0.25, to=60),
    }


# ------------------------------------------------------------------ playback

def init():
    """Build every effect once. Silent (and harmless) if there is no audio device.

    A file at audio/<name>.wav|.ogg wins over the synthesised version, so a
    downloaded pack (Pixabay and friends) drops in without touching this code.
    """
    global _playing
    if SOUNDS:
        return
    try:
        if pygame.mixer.get_init() != (RATE, -16, CHANNELS):
            pygame.mixer.quit()                  # whatever pygame.init() opened
            pygame.mixer.init(RATE, -16, CHANNELS, 512)
    except pygame.error:
        return                                   # headless or muted: stay a no-op
    _playing = None
    folder = Path(__file__).parent / "audio"
    for name, buf in voices().items():
        override = next((p for ext in (".wav", ".ogg")
                         if (p := folder / (name + ext)).exists()), None)
        try:
            SOUNDS[name] = (pygame.mixer.Sound(str(override)) if override
                            else pygame.mixer.Sound(buffer=buf))
        except pygame.error:                     # unreadable file: keep the blip
            SOUNDS[name] = pygame.mixer.Sound(buffer=buf)


def play(name):
    sound = SOUNDS.get(name)
    if sound is None:
        return                                   # not built, or no audio device
    try:
        sound.play()
    except pygame.error:
        pass


def set_volume(music=None, sfx=None):
    """Live volume, 0.0 to 1.0. Either knob may be left alone. Safe without audio."""
    global MUSIC_VOLUME, SFX_VOLUME
    if music is not None:
        MUSIC_VOLUME = music
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(MUSIC_VOLUME)
    if sfx is not None:
        SFX_VOLUME = sfx
        for sound in SOUNDS.values():
            sound.set_volume(SFX_VOLUME)


def music(track):
    """Loop a track from TRACKS, or None for silence.

    Asking for what is already playing does nothing, so a state can simply say what
    it wants every frame and the scene change takes care of itself.
    """
    global _playing
    if track == _playing:
        return
    _playing = track                             # set even on failure, or we retry 60x/s
    if not pygame.mixer.get_init():
        return
    pygame.mixer.music.stop()
    if track is None:
        return
    path = Path(__file__).parent / "data" / TRACKS[track]
    if not path.exists():
        return                                   # no soundtrack shipped: stay quiet
    try:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
        pygame.mixer.music.play(-1)              # -1 loops forever
    except pygame.error:
        pass


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")     # test in silence

    bank = voices()
    assert set(bank) >= {"cursor", "attack", "hurt", "victory", "death"}
    for name, buf in bank.items():
        assert buf.typecode == "h", name
        assert len(buf) % CHANNELS == 0, f"{name} is not whole frames"
        seconds = len(buf) / (RATE * CHANNELS)
        assert 0.02 < seconds < 1.5, f"{name} is {seconds:.2f}s"
        assert max(buf) > 1000 and min(buf) < -1000, f"{name} is silent"
        assert abs(buf[0]) < 3000 and abs(buf[-1]) < 3000, f"{name} clicks at an edge"
        assert all(-32768 <= s <= 32767 for s in buf), f"{name} clips the 16-bit range"
    # init() must never raise, and play() on a dead mixer must be a no-op
    pygame.mixer.quit()
    SOUNDS.clear()
    play("cursor")
    pygame.init()                                # opens the mixer at 44100 stereo...
    init()                                       # ...which init() must take back over
    play("nonexistent-effect")
    if pygame.mixer.get_init():                  # skipped on a machine with no device
        assert pygame.mixer.get_init() == (RATE, -16, CHANNELS), pygame.mixer.get_init()
        played = SOUNDS["victory"].get_length()
        built = len(bank["victory"]) / (RATE * CHANNELS)
        assert abs(played - built) < 0.02, f"mixer plays it at {played / built:.1f}x speed"

        # music: the tracks load and loop, repeating a request is a no-op, and a
        # missing file leaves the game silent instead of throwing every frame
        for track in TRACKS:
            music(track)
            assert _playing == track and pygame.mixer.music.get_busy(), track
        here = _playing
        music(here)
        assert pygame.mixer.music.get_busy()
        music(None)
        assert _playing is None and not pygame.mixer.music.get_busy()
        TRACKS["field"] = "no-such-track.mp3"
        music("field")
        assert _playing == "field" and not pygame.mixer.music.get_busy()
        TRACKS["field"] = "fantasy-medieval-rpg-music.mp3"
        music(None)
    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:                                        # play them all, once each
        pygame.init()
        init()
        for name in voices():
            print(name)
            play(name)
            pygame.time.wait(700)
        for track in TRACKS:
            print(f"music: {track}")
            music(track)
            pygame.time.wait(8000)
        music(None)
