"""Efek suara yang disintesis secara prosedural — tanpa berkas aset."""

from __future__ import annotations

import array
import math
import random

import pygame

SAMPLE_RATE = 22050


def _synth(
    rate: int,
    f0: float,
    f1: float,
    duration: float,
    wave: str = "square",
    volume: float = 0.3,
) -> array.array:
    n = int(rate * duration)
    out = array.array("h")
    phase = 0.0
    attack = max(1, int(rate * 0.005))
    for i in range(n):
        t = i / n
        phase += (f0 + (f1 - f0) * t) / rate
        p = phase % 1.0
        if wave == "square":
            s = 1.0 if p < 0.5 else -1.0
        elif wave == "triangle":
            s = 4.0 * abs(p - 0.5) - 1.0
        elif wave == "noise":
            s = random.uniform(-1.0, 1.0)
        else:
            s = math.sin(2 * math.pi * p)
        env = min(1.0, i / attack) * (1.0 - t) ** 2
        out.append(int(s * env * volume * 32767))
    return out


def _concat(*parts: array.array) -> array.array:
    out = array.array("h")
    for part in parts:
        out.extend(part)
    return out


class SoundBank:
    def __init__(self, muted: bool = False) -> None:
        self.muted = muted
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            rate, _, channels = pygame.mixer.get_init()
            self._build(rate, channels)
        except (pygame.error, TypeError):
            self.sounds = {}  # tanpa perangkat audio: permainan tetap berjalan tanpa suara

    def _build(self, rate: int, channels: int) -> None:
        def sound(samples: array.array) -> pygame.mixer.Sound:
            if channels > 1:
                samples = array.array("h", (s for s in samples for _ in range(channels)))
            return pygame.mixer.Sound(buffer=samples.tobytes())

        s = lambda *a, **k: _synth(rate, *a, **k)  # noqa: E731
        for combo in range(1, 6):
            base = 520 * 2 ** ((combo - 1) / 12 * 2)
            self.sounds[f"eat{combo}"] = sound(s(base, base * 1.7, 0.09, "sine", 0.45))
        self.sounds["bonus"] = sound(_concat(*(s(f, f, 0.07, "triangle", 0.4) for f in (660, 830, 990, 1320))))
        self.sounds["spawn"] = sound(s(880, 1400, 0.12, "sine", 0.2))
        self.sounds["expire"] = sound(s(500, 250, 0.15, "triangle", 0.2))
        self.sounds["die"] = sound(_concat(s(320, 60, 0.45, "square", 0.25), s(0, 0, 0.2, "noise", 0.15)))
        self.sounds["tick"] = sound(s(660, 660, 0.07, "square", 0.15))
        self.sounds["go"] = sound(s(990, 990, 0.18, "square", 0.18))
        self.sounds["click"] = sound(s(700, 900, 0.03, "sine", 0.25))
        self.sounds["record"] = sound(_concat(*(s(f, f, 0.09, "square", 0.15) for f in (523, 659, 784, 1047, 1319))))

    def play(self, name: str) -> None:
        if not self.muted and (snd := self.sounds.get(name)):
            snd.play()

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted
