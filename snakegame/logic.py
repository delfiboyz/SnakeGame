"""Logika inti permainan — murni Python tanpa pygame sehingga mudah diuji."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from enum import Enum

Cell = tuple[int, int]

COMBO_WINDOW = 2.5  # detik antar makanan agar combo berlanjut
MAX_COMBO = 5
BONUS_EVERY = 5  # bonus muncul setiap 5 makanan biasa
BONUS_POINTS = 5
BONUS_DURATION = 6.0
MAX_QUEUED_TURNS = 2


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    def is_opposite(self, other: Direction) -> bool:
        return self.dx == -other.dx and self.dy == -other.dy


class Mode(Enum):
    CLASSIC = "Classic"
    PORTAL = "Portal"
    MAZE = "Maze"

    @property
    def description(self) -> str:
        return {
            Mode.CLASSIC: "Tembok mematikan, mode klasik",
            Mode.PORTAL: "Tembus tembok ke sisi seberang",
            Mode.MAZE: "Rintangan di arena, tembok mematikan",
        }[self]


@dataclass(frozen=True)
class Difficulty:
    name: str
    start_speed: float  # langkah per detik
    max_speed: float
    speed_step: float  # tambahan kecepatan per makanan


DIFFICULTIES = (
    Difficulty("Easy", 7.0, 13.0, 0.2),
    Difficulty("Normal", 9.0, 17.0, 0.3),
    Difficulty("Hard", 12.0, 24.0, 0.45),
)


class EventKind(Enum):
    EAT = "eat"
    BONUS_EAT = "bonus_eat"
    BONUS_SPAWN = "bonus_spawn"
    BONUS_EXPIRED = "bonus_expired"
    DIE = "die"
    WIN = "win"


@dataclass(frozen=True)
class GameEvent:
    kind: EventKind
    cell: Cell
    points: int = 0
    combo: int = 0


@dataclass
class Bonus:
    cell: Cell
    ttl: float
    duration: float = BONUS_DURATION


def build_maze(cols: int, rows: int) -> set[Cell]:
    """Rintangan simetris yang menyisakan jalur aman di tengah arena."""
    cells: set[Cell] = set()
    cx, cy = cols // 2, rows // 2
    qx, qy = cols // 4, rows // 4
    for x in range(qx, cols - qx):
        if abs(x - cx) > 2:
            cells.add((x, qy))
            cells.add((x, rows - 1 - qy))
    for y in range(qy + 1, rows - qy - 1):
        if abs(y - cy) > 1:
            cells.add((2, y))
            cells.add((cols - 3, y))
    return cells


class Game:
    def __init__(
        self,
        cols: int,
        rows: int,
        mode: Mode = Mode.CLASSIC,
        difficulty: Difficulty = DIFFICULTIES[1],
        rng: random.Random | None = None,
    ) -> None:
        self.cols = cols
        self.rows = rows
        self.mode = mode
        self.difficulty = difficulty
        self.rng = rng or random.Random()
        self.obstacles = frozenset(build_maze(cols, rows) if mode is Mode.MAZE else ())

        cx, cy = cols // 2, rows // 2
        # Kepala ada di indeks 0
        self.snake: deque[Cell] = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
        self.previous: list[Cell] = list(self.snake)
        self.direction = Direction.RIGHT
        self._turns: deque[Direction] = deque()

        self.score = 0
        self.eaten = 0
        self.combo = 0
        self.elapsed = 0.0
        self.alive = True
        self.won = False
        self.bonus: Bonus | None = None
        self._since_eat = math.inf
        self._accumulator = 0.0
        self.food: Cell = self._free_cell() or (0, 0)

    @property
    def head(self) -> Cell:
        return self.snake[0]

    @property
    def speed(self) -> float:
        d = self.difficulty
        return min(d.max_speed, d.start_speed + self.eaten * d.speed_step)

    @property
    def progress(self) -> float:
        """Fraksi menuju langkah berikutnya (0..1), dipakai untuk animasi halus."""
        return max(0.0, min(1.0, self._accumulator * self.speed))

    @property
    def combo_time_left(self) -> float:
        return max(0.0, COMBO_WINDOW - self._since_eat)

    def turn(self, direction: Direction) -> bool:
        """Antrikan belokan. Mendukung input buffer agar belokan cepat tidak hilang."""
        last = self._turns[-1] if self._turns else self.direction
        if len(self._turns) >= MAX_QUEUED_TURNS or direction == last or direction.is_opposite(last):
            return False
        self._turns.append(direction)
        return True

    def update(self, dt: float) -> list[GameEvent]:
        """Majukan waktu permainan dengan fixed timestep."""
        if not self.alive:
            return []
        events: list[GameEvent] = []
        self.elapsed += dt
        self._since_eat += dt
        if self.bonus is not None:
            self.bonus.ttl -= dt
            if self.bonus.ttl <= 0:
                events.append(GameEvent(EventKind.BONUS_EXPIRED, self.bonus.cell))
                self.bonus = None

        self._accumulator += dt
        interval = 1.0 / self.speed
        while self.alive and self._accumulator >= interval:
            self._accumulator -= interval
            events.extend(self.step())
            interval = 1.0 / self.speed
        return events

    def step(self) -> list[GameEvent]:
        if not self.alive:
            return []
        if self._turns:
            self.direction = self._turns.popleft()
        self.previous = list(self.snake)

        hx, hy = self.head
        nx, ny = hx + self.direction.dx, hy + self.direction.dy
        if self.mode is Mode.PORTAL:
            nx %= self.cols
            ny %= self.rows
        elif not (0 <= nx < self.cols and 0 <= ny < self.rows):
            return self._die()
        new_head = (nx, ny)

        on_bonus = self.bonus is not None and new_head == self.bonus.cell
        grows = new_head == self.food or on_bonus
        body = list(self.snake) if grows else list(self.snake)[:-1]
        if new_head in self.obstacles or new_head in body:
            return self._die()

        self.snake.appendleft(new_head)
        if not grows:
            self.snake.pop()

        events: list[GameEvent] = []
        if new_head == self.food:
            self.eaten += 1
            events.append(self._score(EventKind.EAT, new_head, 1))
            food = self._free_cell()
            if food is None:
                self.alive = False
                self.won = True
                events.append(GameEvent(EventKind.WIN, new_head))
                return events
            self.food = food
            if self.eaten % BONUS_EVERY == 0 and self.bonus is None:
                cell = self._free_cell()
                if cell is not None:
                    self.bonus = Bonus(cell, BONUS_DURATION)
                    events.append(GameEvent(EventKind.BONUS_SPAWN, cell))
        elif on_bonus:
            self.bonus = None
            events.append(self._score(EventKind.BONUS_EAT, new_head, BONUS_POINTS))
        return events

    def _score(self, kind: EventKind, cell: Cell, base: int) -> GameEvent:
        self.combo = self.combo + 1 if self._since_eat <= COMBO_WINDOW else 1
        self.combo = min(self.combo, MAX_COMBO)
        self._since_eat = 0.0
        points = base * self.combo
        self.score += points
        return GameEvent(kind, cell, points, self.combo)

    def _die(self) -> list[GameEvent]:
        self.alive = False
        return [GameEvent(EventKind.DIE, self.head)]

    def _free_cell(self) -> Cell | None:
        occupied = set(self.snake) | self.obstacles
        if hasattr(self, "food"):
            occupied.add(self.food)
        if self.bonus is not None:
            occupied.add(self.bonus.cell)
        free = [(x, y) for y in range(self.rows) for x in range(self.cols) if (x, y) not in occupied]
        return self.rng.choice(free) if free else None
