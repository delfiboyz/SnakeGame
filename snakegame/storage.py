"""Penyimpanan pengaturan dan papan skor (leaderboard) dalam JSON.

Di desktop data disimpan sebagai berkas; di browser (pygbag) memakai ``localStorage``.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

LEADERBOARD_SIZE = 5
LOCAL_STORAGE_KEY = "snakegame"


def default_path() -> Path:
    if override := os.environ.get("SNAKEGAME_DATA"):
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "snakegame" / "data.json"


def browser_storage():
    """``window.localStorage`` saat berjalan di browser via pygbag, selain itu None."""
    if sys.platform != "emscripten":
        return None
    try:
        import platform

        return platform.window.localStorage
    except Exception:
        return None


@dataclass
class ScoreEntry:
    score: int
    length: int
    time: float
    date: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class Settings:
    mode: str = "Classic"
    difficulty: str = "Normal"
    muted: bool = False


class Store:
    def __init__(self, path: Path | None = None, local_storage=None) -> None:
        self.path = path or default_path()
        self.local_storage = local_storage if local_storage is not None else (None if path else browser_storage())
        self.settings = Settings()
        self.scores: dict[str, list[ScoreEntry]] = {}
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self._read())
            self.settings = Settings(**data.get("settings", {}))
            self.scores = {key: [ScoreEntry(**e) for e in entries] for key, entries in data.get("scores", {}).items()}
        except Exception:
            # Berkas belum ada atau rusak: mulai dari kondisi bersih
            self.settings = Settings()
            self.scores = {}

    def save(self) -> None:
        data = {
            "settings": asdict(self.settings),
            "scores": {k: [asdict(e) for e in v] for k, v in self.scores.items()},
        }
        try:
            self._write(json.dumps(data, indent=2))
        except Exception:
            pass  # penyimpanan gagal (mis. kuota browser penuh); permainan tetap jalan

    def _read(self) -> str:
        if self.local_storage is not None:
            return self.local_storage.getItem(LOCAL_STORAGE_KEY)
        return self.path.read_text(encoding="utf-8")

    def _write(self, text: str) -> None:
        if self.local_storage is not None:
            self.local_storage.setItem(LOCAL_STORAGE_KEY, text)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)

    def leaderboard(self, key: str) -> list[ScoreEntry]:
        return self.scores.get(key, [])

    def best(self, key: str) -> int:
        board = self.leaderboard(key)
        return board[0].score if board else 0

    def submit(self, key: str, entry: ScoreEntry) -> int | None:
        """Tambahkan skor; kembalikan peringkat (0 = terbaik) atau None jika tak masuk."""
        if entry.score <= 0:
            return None
        board = self.scores.setdefault(key, [])
        rank = next((i for i, e in enumerate(board) if entry.score > e.score), len(board))
        if rank >= LEADERBOARD_SIZE:
            return None
        board.insert(rank, entry)
        del board[LEADERBOARD_SIZE:]
        return rank
