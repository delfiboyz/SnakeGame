"""Titik masuk permainan (juga dipakai pygbag untuk build versi web)."""

import asyncio

# pygbag hanya mengunduh paket yang di-import langsung di sini; tanpa baris ini
# pygame-ce tidak ikut terpasang di versi web.
import pygame  # noqa: F401

from snakegame.app import run

asyncio.run(run())
