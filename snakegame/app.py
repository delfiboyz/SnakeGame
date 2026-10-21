"""Lapisan presentasi: state machine, input, rendering, dan efek."""

from __future__ import annotations

import asyncio
import math
import random
import sys
from dataclasses import dataclass
from enum import Enum, auto

import pygame

from snakegame import config as C
from snakegame.audio import SoundBank
from snakegame.logic import DIFFICULTIES, Direction, EventKind, Game, Mode
from snakegame.storage import ScoreEntry, Store

MODES = list(Mode)

DIRECTION_KEYS = {
    pygame.K_UP: Direction.UP,
    pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
    pygame.K_d: Direction.RIGHT,
}
CONFIRM_KEYS = {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE}
SWIPE_MIN_DISTANCE = 30


class State(Enum):
    MENU = auto()
    COUNTDOWN = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class Action(Enum):
    CONFIRM = auto()
    BACK = auto()
    PAUSE = auto()
    MENU = auto()


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    size: float


@dataclass
class FloatingText:
    surface: pygame.Surface
    x: float
    y: float
    life: float
    max_life: float = 1.0


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(a, b, t):
    return tuple(int(lerp(x, y, t)) for x, y in zip(a, b, strict=True))


def make_glow(radius: int, color: tuple[int, int, int], strength: int = 110) -> pygame.Surface:
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(strength * (1 - r / radius) ** 2)
        pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
    return surf


def blur(surface: pygame.Surface, radius: int) -> pygame.Surface:
    # gaussian_blur tersedia di pygame-ce >= 2.2; fallback untuk versi lama
    if hasattr(pygame.transform, "gaussian_blur"):
        return pygame.transform.gaussian_blur(surface, radius)
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // 4), max(1, h // 4)))
    return pygame.transform.smoothscale(small, (w, h))


class App:
    def __init__(self, store: Store | None = None) -> None:
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(C.TITLE)
        self.screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.store = store or Store()
        self.sounds = SoundBank(muted=self.store.settings.muted)
        self.mode_index = self._index_of([m.value for m in MODES], self.store.settings.mode)
        self.diff_index = self._index_of([d.name for d in DIFFICULTIES], self.store.settings.difficulty)

        self.font_huge = pygame.font.Font(None, 120)
        self.font_big = pygame.font.Font(None, 64)
        self.font = pygame.font.Font(None, 34)
        self.font_small = pygame.font.Font(None, 24)

        self.state = State.MENU
        self.game: Game | None = None
        self.menu_row = 0
        self.countdown = 0.0
        self.state_time = 0.0
        self.time = 0.0
        self.rank: int | None = None
        self.particles: list[Particle] = []
        self.texts: list[FloatingText] = []
        self.shake = 0.0
        self.swipe_start: tuple[int, int] | None = None
        self.joysticks: dict[int, pygame.joystick.JoystickType] = {}
        self.running = True

        self.background = self._make_background()
        self.field_bg = self._make_field_background()
        self.field = pygame.Surface((C.FIELD_WIDTH, C.FIELD_HEIGHT))
        self.food_glow = make_glow(C.CELL, C.FOOD)
        self.bonus_glow = make_glow(int(C.CELL * 1.3), C.BONUS, 140)
        self.head_glow = make_glow(C.CELL, C.SNAKE_HEAD, 80)
        self.title = self._make_title()
        self.overlay = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        self.overlay.fill((4, 6, 14, 170))

    # ------------------------------------------------------------------ setup

    @staticmethod
    def _index_of(names: list[str], name: str) -> int:
        return names.index(name) if name in names else min(1, len(names) - 1)

    def _make_background(self) -> pygame.Surface:
        surf = pygame.Surface((C.WIDTH, C.HEIGHT))
        for y in range(C.HEIGHT):
            pygame.draw.line(surf, lerp_color(C.BG_TOP, C.BG_BOTTOM, y / C.HEIGHT), (0, y), (C.WIDTH, y))
        return surf

    def _make_field_background(self) -> pygame.Surface:
        surf = pygame.Surface((C.FIELD_WIDTH, C.FIELD_HEIGHT))
        for y in range(C.ROWS):
            for x in range(C.COLS):
                color = C.FIELD_A if (x + y) % 2 == 0 else C.FIELD_B
                surf.fill(color, (x * C.CELL, y * C.CELL, C.CELL, C.CELL))
        return surf

    def _make_title(self) -> pygame.Surface:
        text = self.font_huge.render("SNAKE", True, C.ACCENT)
        pad = 40
        surf = pygame.Surface((text.get_width() + pad * 2, text.get_height() + pad * 2), pygame.SRCALPHA)
        surf.blit(text, (pad, pad))
        glow = blur(surf, 14)
        result = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        result.blit(glow, (0, 0))
        result.blit(glow, (0, 0))
        result.blit(self.font_huge.render("SNAKE", True, C.TEXT), (pad, pad))
        return result

    @property
    def mode(self) -> Mode:
        return MODES[self.mode_index]

    @property
    def difficulty(self):
        return DIFFICULTIES[self.diff_index]

    @property
    def score_key(self) -> str:
        return f"{self.mode.value}/{self.difficulty.name}"

    # ------------------------------------------------------------- lifecycle

    def set_state(self, state: State) -> None:
        self.state = state
        self.state_time = 0.0

    def start_game(self) -> None:
        self.store.settings.mode = self.mode.value
        self.store.settings.difficulty = self.difficulty.name
        self.store.save()
        self.game = Game(C.COLS, C.ROWS, self.mode, self.difficulty)
        self.particles.clear()
        self.texts.clear()
        self.rank = None
        self.countdown = float(C.COUNTDOWN_SECONDS)
        self.set_state(State.COUNTDOWN)
        self.sounds.play("tick")

    def finish_game(self) -> None:
        assert self.game is not None
        entry = ScoreEntry(self.game.score, len(self.game.snake), round(self.game.elapsed, 1))
        self.rank = self.store.submit(self.score_key, entry)
        self.store.save()
        self.set_state(State.GAME_OVER)
        if self.rank == 0:
            self.sounds.play("record")

    # ----------------------------------------------------------------- input

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)
        elif event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self.joysticks[joy.get_instance_id()] = joy
        elif event.type == pygame.JOYDEVICEREMOVED:
            self.joysticks.pop(event.instance_id, None)
        elif event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if (x, y) in ((0, 1), (0, -1), (-1, 0), (1, 0)):
                self.on_direction(Direction((x, -y)))
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:
                self.on_action(Action.CONFIRM)
            elif event.button == 1:
                self.on_action(Action.BACK)
            elif event.button in (6, 7):
                self.on_action(Action.PAUSE)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.swipe_start = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.swipe_start:
            dx = event.pos[0] - self.swipe_start[0]
            dy = event.pos[1] - self.swipe_start[1]
            self.swipe_start = None
            if max(abs(dx), abs(dy)) < SWIPE_MIN_DISTANCE:
                if self.state is not State.PLAYING:
                    self.on_action(Action.CONFIRM)
            elif abs(dx) > abs(dy):
                self.on_direction(Direction.RIGHT if dx > 0 else Direction.LEFT)
            else:
                self.on_direction(Direction.DOWN if dy > 0 else Direction.UP)

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        elif key == pygame.K_m:
            self.store.settings.muted = self.sounds.toggle_mute()
            self.store.save()
        elif key in DIRECTION_KEYS:
            self.on_direction(DIRECTION_KEYS[key])
        elif key in CONFIRM_KEYS:
            self.on_action(Action.CONFIRM)
        elif key == pygame.K_ESCAPE:
            self.on_action(Action.BACK)
        elif key == pygame.K_p:
            self.on_action(Action.PAUSE)
        elif key == pygame.K_q:
            self.on_action(Action.MENU)

    def on_direction(self, direction: Direction) -> None:
        if self.state is State.MENU:
            if direction in (Direction.UP, Direction.DOWN):
                self.menu_row = (self.menu_row + direction.dy) % 3
            elif self.menu_row == 0:
                self.mode_index = (self.mode_index + direction.dx) % len(MODES)
            elif self.menu_row == 1:
                self.diff_index = (self.diff_index + direction.dx) % len(DIFFICULTIES)
            self.sounds.play("click")
        elif self.state in (State.PLAYING, State.COUNTDOWN) and self.game:
            self.game.turn(direction)

    def on_action(self, action: Action) -> None:
        state = self.state
        if state is State.MENU:
            if action is Action.CONFIRM:
                self.start_game()
            elif action is Action.BACK and sys.platform != "emscripten":
                self.running = False
        elif state in (State.PLAYING, State.COUNTDOWN):
            if action in (Action.PAUSE, Action.BACK):
                self.set_state(State.PAUSED)
        elif state is State.PAUSED:
            if action is Action.MENU:
                self.set_state(State.MENU)
            elif action in (Action.CONFIRM, Action.PAUSE, Action.BACK):
                self.set_state(State.COUNTDOWN if self.countdown > 0 else State.PLAYING)
        elif state is State.GAME_OVER and self.state_time >= C.GAME_OVER_INPUT_DELAY:
            if action is Action.CONFIRM:
                self.start_game()
            elif action in (Action.BACK, Action.MENU):
                self.set_state(State.MENU)

    # ---------------------------------------------------------------- update

    def update(self, dt: float) -> None:
        self.time += dt
        self.state_time += dt
        self.shake = max(0.0, self.shake - dt * 2.5)
        self._update_effects(dt)

        if self.state is State.COUNTDOWN:
            before = math.ceil(self.countdown)
            self.countdown -= dt
            if self.countdown <= 0:
                self.countdown = 0.0
                self.set_state(State.PLAYING)
                self.sounds.play("go")
            elif math.ceil(self.countdown) != before:
                self.sounds.play("tick")
        elif self.state is State.PLAYING and self.game:
            for event in self.game.update(dt):
                self._on_game_event(event)
            if not self.game.alive:
                self.finish_game()

    def _on_game_event(self, event) -> None:
        x, y = self.cell_center(event.cell)
        if event.kind is EventKind.EAT:
            self.sounds.play(f"eat{event.combo}")
            self.burst(x, y, C.FOOD, 14)
            label = f"+{event.points}" + (f"  x{event.combo}" if event.combo > 1 else "")
            self.float_text(label, x, y, C.TEXT)
        elif event.kind is EventKind.BONUS_EAT:
            self.sounds.play("bonus")
            self.burst(x, y, C.BONUS, 30, speed=220)
            self.float_text(f"+{event.points}", x, y, C.BONUS)
        elif event.kind is EventKind.BONUS_SPAWN:
            self.sounds.play("spawn")
            self.burst(x, y, C.BONUS, 10, speed=80)
        elif event.kind is EventKind.BONUS_EXPIRED:
            self.sounds.play("expire")
            self.burst(x, y, C.TEXT_DIM, 10, speed=60)
        elif event.kind is EventKind.DIE:
            self.sounds.play("die")
            self.shake = 1.0
            assert self.game is not None
            for cell in self.game.snake:
                cx, cy = self.cell_center(cell)
                self.burst(cx, cy, C.SNAKE_HEAD, 3, speed=160)
        elif event.kind is EventKind.WIN:
            self.sounds.play("record")
            self.float_text("PERFECT!", x, y, C.BONUS)

    def burst(self, x, y, color, count, speed=140.0) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            v = random.uniform(0.3, 1.0) * speed
            life = random.uniform(0.35, 0.8)
            self.particles.append(
                Particle(x, y, math.cos(angle) * v, math.sin(angle) * v, life, life, color, random.uniform(2, 5))
            )

    def float_text(self, text, x, y, color) -> None:
        self.texts.append(FloatingText(self.font.render(text, True, color), x, y, 1.0))

    def _update_effects(self, dt: float) -> None:
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.92
            p.vy *= 0.92
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for t in self.texts:
            t.y -= 40 * dt
            t.life -= dt
        self.texts = [t for t in self.texts if t.life > 0]

    # ------------------------------------------------------------------ draw

    @staticmethod
    def cell_center(cell) -> tuple[float, float]:
        return cell[0] * C.CELL + C.CELL / 2, cell[1] * C.CELL + C.CELL / 2

    def draw(self) -> None:
        self.screen.blit(self.background, (0, 0))
        if self.state is State.MENU:
            self.draw_menu()
        else:
            self.draw_field()
            self.draw_hud()
            if self.state is State.COUNTDOWN:
                self.draw_countdown()
            elif self.state is State.PAUSED:
                self.draw_paused()
            elif self.state is State.GAME_OVER:
                self.draw_game_over()
        pygame.display.flip()

    def draw_field(self) -> None:
        assert self.game is not None
        game = self.game
        field = self.field
        field.blit(self.field_bg, (0, 0))

        for ox, oy in game.obstacles:
            rect = pygame.Rect(ox * C.CELL + 1, oy * C.CELL + 1, C.CELL - 2, C.CELL - 2)
            pygame.draw.rect(field, C.OBSTACLE, rect, border_radius=5)
            pygame.draw.rect(field, C.OBSTACLE_EDGE, rect, 2, border_radius=5)

        # Makanan berdenyut
        fx, fy = self.cell_center(game.food)
        pulse = 1 + 0.12 * math.sin(self.time * 6)
        field.blit(self.food_glow, self.food_glow.get_rect(center=(fx, fy)))
        pygame.draw.circle(field, C.FOOD, (fx, fy), C.CELL * 0.36 * pulse)
        pygame.draw.circle(field, (255, 170, 190), (fx - 3, fy - 3), C.CELL * 0.1)
        pygame.draw.ellipse(field, C.LEAF, (fx, fy - C.CELL * 0.55, 8, 5))

        # Bonus emas dengan cincin sisa waktu
        if game.bonus and (game.bonus.ttl > 2 or int(self.time * 8) % 2 == 0):
            bx, by = self.cell_center(game.bonus.cell)
            field.blit(self.bonus_glow, self.bonus_glow.get_rect(center=(bx, by)))
            r = C.CELL * 0.42
            angle = self.time * 3
            points = [
                (bx + math.cos(angle + i * math.pi / 2) * r, by + math.sin(angle + i * math.pi / 2) * r)
                for i in range(4)
            ]
            pygame.draw.polygon(field, C.BONUS, points)
            ring = pygame.Rect(0, 0, C.CELL * 1.5, C.CELL * 1.5)
            ring.center = (bx, by)
            frac = game.bonus.ttl / game.bonus.duration
            pygame.draw.arc(field, C.BONUS, ring, math.pi / 2, math.pi / 2 + math.tau * frac, 2)

        self.draw_snake(field, game)

        for p in self.particles:
            t = p.life / p.max_life
            pygame.draw.circle(field, lerp_color(C.FIELD_A, p.color, t), (p.x, p.y), p.size * t)
        for t in self.texts:
            t.surface.set_alpha(int(255 * min(1.0, t.life / t.max_life * 1.5)))
            field.blit(t.surface, t.surface.get_rect(center=(t.x, t.y)))

        sx = sy = 0
        if self.shake > 0:
            amp = 10 * self.shake**2
            sx, sy = random.uniform(-amp, amp), random.uniform(-amp, amp)
        self.screen.blit(field, (sx, C.HUD_HEIGHT + sy))
        pygame.draw.rect(
            self.screen,
            C.DANGER if self.state is State.GAME_OVER else C.PANEL_EDGE,
            (0, C.HUD_HEIGHT, C.FIELD_WIDTH, C.FIELD_HEIGHT),
            2,
        )

    def draw_snake(self, surface: pygame.Surface, game: Game) -> None:
        alpha = game.progress if game.alive and self.state is State.PLAYING else 1.0
        positions: list[tuple[float, float]] = []
        for i, cell in enumerate(game.snake):
            prev = game.previous[i] if i < len(game.previous) else cell
            if abs(prev[0] - cell[0]) + abs(prev[1] - cell[1]) > 1:
                prev = cell  # lompatan portal: jangan diinterpolasi
            x = lerp(prev[0], cell[0], alpha)
            y = lerp(prev[1], cell[1], alpha)
            positions.append(((x + 0.5) * C.CELL, (y + 0.5) * C.CELL))

        n = len(positions)
        base_r = C.CELL * 0.46
        for i in range(n - 1, -1, -1):
            t = i / max(1, n - 1)
            color = lerp_color(C.SNAKE_HEAD, C.SNAKE_TAIL, t)
            if not game.alive:
                color = lerp_color(color, (70, 70, 90), 0.6)
            radius = base_r * (1 - 0.35 * t)
            pos = positions[i]
            if i < n - 1:
                nxt = positions[i + 1]
                if abs(nxt[0] - pos[0]) + abs(nxt[1] - pos[1]) <= C.CELL * 1.5:
                    mid = ((pos[0] + nxt[0]) / 2, (pos[1] + nxt[1]) / 2)
                    pygame.draw.circle(surface, color, mid, radius)
            pygame.draw.circle(surface, color, pos, radius)

        hx, hy = positions[0]
        if game.alive:
            surface.blit(self.head_glow, self.head_glow.get_rect(center=(hx, hy)))
        d = game.direction
        px, py = -d.dy, d.dx  # vektor tegak lurus arah gerak
        for side in (-1, 1):
            ex = hx + d.dx * 4 + px * 6 * side
            ey = hy + d.dy * 4 + py * 6 * side
            pygame.draw.circle(surface, (255, 255, 255), (ex, ey), 4)
            if game.alive:
                pygame.draw.circle(surface, (10, 12, 24), (ex + d.dx * 1.5, ey + d.dy * 1.5), 2)
            else:
                pygame.draw.line(surface, (10, 12, 24), (ex - 2, ey - 2), (ex + 2, ey + 2), 2)
                pygame.draw.line(surface, (10, 12, 24), (ex - 2, ey + 2), (ex + 2, ey - 2), 2)

    def draw_hud(self) -> None:
        assert self.game is not None
        game = self.game
        best = max(self.store.best(self.score_key), game.score)
        self.blit_text(f"SCORE {game.score}", self.font, C.TEXT, (16, 10))
        self.blit_text(f"BEST {best}", self.font_small, C.TEXT_DIM, (16, 46), anchor="midleft")

        minutes, seconds = divmod(int(game.elapsed), 60)
        right = C.WIDTH - 16
        self.blit_text(f"{minutes:02d}:{seconds:02d}", self.font, C.TEXT, (right, 10), anchor="topright")
        info = f"{self.mode.value} · {self.difficulty.name} · {game.speed:.1f} spd"
        if self.sounds.muted:
            info += " · MUTE"
        self.blit_text(info, self.font_small, C.TEXT_DIM, (right, 46), anchor="midright")

        if game.alive and game.combo > 1 and game.combo_time_left > 0:
            cx = C.WIDTH // 2
            self.blit_text(f"COMBO x{game.combo}", self.font, C.BONUS, (cx, 22), anchor="center")
            width = 120 * game.combo_time_left / 2.5
            pygame.draw.rect(self.screen, C.BONUS, (cx - width / 2, 40, width, 4), border_radius=2)
        else:
            self.blit_text(f"LENGTH {len(game.snake)}", self.font_small, C.TEXT_DIM, (C.WIDTH // 2, 32), "center")

    def draw_panel(self, height: int) -> pygame.Rect:
        self.screen.blit(self.overlay, (0, 0))
        rect = pygame.Rect(0, 0, 440, height)
        rect.center = (C.WIDTH // 2, C.HEIGHT // 2 + C.HUD_HEIGHT // 2)
        pygame.draw.rect(self.screen, C.PANEL, rect, border_radius=18)
        pygame.draw.rect(self.screen, C.PANEL_EDGE, rect, 2, border_radius=18)
        return rect

    def draw_countdown(self) -> None:
        n = max(1, math.ceil(self.countdown))
        frac = self.countdown - (n - 1)
        surf = self.font_huge.render(str(n), True, C.ACCENT)
        scale = 0.8 + 0.6 * frac
        surf = pygame.transform.smoothscale_by(surf, scale)
        surf.set_alpha(int(255 * min(1.0, frac * 2)))
        center = (C.WIDTH // 2, C.HUD_HEIGHT + C.FIELD_HEIGHT // 2)
        self.screen.blit(surf, surf.get_rect(center=center))
        self.blit_text("Siap-siap!", self.font_small, C.TEXT_DIM, (center[0], center[1] + 70), "center")

    def draw_paused(self) -> None:
        rect = self.draw_panel(200)
        self.blit_text("PAUSED", self.font_big, C.TEXT, (rect.centerx, rect.top + 50), "center")
        self.blit_text("Enter / P — Lanjutkan", self.font_small, C.TEXT_DIM, (rect.centerx, rect.top + 110), "center")
        self.blit_text("Q — Kembali ke menu", self.font_small, C.TEXT_DIM, (rect.centerx, rect.top + 140), "center")

    def draw_game_over(self) -> None:
        assert self.game is not None
        game = self.game
        rect = self.draw_panel(320)
        title, color = ("YOU WIN!", C.BONUS) if game.won else ("GAME OVER", C.DANGER)
        self.blit_text(title, self.font_big, color, (rect.centerx, rect.top + 50), "center")

        if self.rank == 0:
            if int(self.time * 3) % 2 == 0:
                self.blit_text("* REKOR BARU! *", self.font, C.BONUS, (rect.centerx, rect.top + 95), "center")
        elif self.rank is not None:
            self.blit_text(
                f"Masuk Top 5 — peringkat #{self.rank + 1}",
                self.font_small,
                C.ACCENT,
                (rect.centerx, rect.top + 95),
                "center",
            )

        minutes, seconds = divmod(int(game.elapsed), 60)
        stats = [
            ("Skor", str(game.score)),
            ("Terbaik", str(self.store.best(self.score_key))),
            ("Panjang", str(len(game.snake))),
            ("Waktu", f"{minutes:02d}:{seconds:02d}"),
        ]
        for i, (label, value) in enumerate(stats):
            y = rect.top + 135 + i * 30
            self.blit_text(label, self.font_small, C.TEXT_DIM, (rect.left + 90, y), "midleft")
            self.blit_text(value, self.font, C.TEXT, (rect.right - 90, y), "midright")

        if self.state_time >= C.GAME_OVER_INPUT_DELAY:
            self.blit_text(
                "Enter / Space — Main lagi   ·   Esc — Menu",
                self.font_small,
                C.TEXT_DIM,
                (rect.centerx, rect.bottom - 30),
                "center",
            )

    def draw_menu(self) -> None:
        # Ular dekoratif yang bergelombang di belakang judul
        for i in range(28):
            t = i / 27
            x = C.WIDTH * 0.12 + i * (C.WIDTH * 0.76 / 27)
            y = 150 + math.sin(self.time * 2.5 - i * 0.35) * 26
            pygame.draw.circle(self.screen, lerp_color(C.SNAKE_TAIL, C.SNAKE_HEAD, t), (x, y), 12 - 4 * (1 - t))
        self.screen.blit(self.title, self.title.get_rect(center=(C.WIDTH // 2, 120)))

        rows = [
            ("Mode", self.mode.value, self.mode.description),
            ("Kesulitan", self.difficulty.name, f"Kecepatan awal {self.difficulty.start_speed:g} langkah/detik"),
        ]
        top = 240
        for i, (label, value, hint) in enumerate(rows):
            selected = self.menu_row == i
            y = top + i * 64
            box = pygame.Rect(C.WIDTH // 2 - 220, y - 22, 440, 52)
            pygame.draw.rect(self.screen, C.PANEL, box, border_radius=12)
            pygame.draw.rect(self.screen, C.ACCENT if selected else C.PANEL_EDGE, box, 2, border_radius=12)
            self.blit_text(label, self.font_small, C.TEXT_DIM, (box.left + 18, y - 2), "midleft")
            arrows = f"<  {value}  >" if selected else value
            self.blit_text(arrows, self.font, C.TEXT, (box.right - 18, y - 4), "midright")
            self.blit_text(hint, self.font_small, C.TEXT_DIM, (box.centerx, y + 18), "center")

        play_selected = self.menu_row == 2
        play = pygame.Rect(0, 0, 220, 50)
        play.center = (C.WIDTH // 2, top + 2 * 64 + 6)
        pulse = 1 + 0.04 * math.sin(self.time * 5) if play_selected else 1
        play = play.scale_by(pulse)
        pygame.draw.rect(self.screen, C.ACCENT if play_selected else C.PANEL, play, border_radius=25)
        pygame.draw.rect(self.screen, C.ACCENT, play, 2, border_radius=25)
        self.blit_text("MAIN", self.font, C.BG_BOTTOM if play_selected else C.ACCENT, play.center, "center")

        board = self.store.leaderboard(self.score_key)
        y = top + 3 * 64
        self.blit_text(f"Top 5 · {self.score_key}", self.font_small, C.ACCENT, (C.WIDTH // 2, y), "center")
        if not board:
            self.blit_text(
                "Belum ada skor — jadilah yang pertama!", self.font_small, C.TEXT_DIM, (C.WIDTH // 2, y + 26), "center"
            )
        for i, entry in enumerate(board):
            line = f"{i + 1}.  {entry.score:>4}   panjang {entry.length:<3}  {entry.date}"
            self.blit_text(
                line, self.font_small, C.TEXT if i == 0 else C.TEXT_DIM, (C.WIDTH // 2, y + 26 + i * 22), "center"
            )

        self.blit_text(
            "Panah/WASD — gerak · Enter — mulai · P — pause · M — suara · F11 — layar penuh",
            self.font_small,
            C.TEXT_DIM,
            (C.WIDTH // 2, C.HEIGHT - 20),
            "center",
        )

    def blit_text(self, text, font, color, pos, anchor: str = "topleft") -> None:
        surf = font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(**{anchor: pos}))

    # ------------------------------------------------------------------ loop

    def frame(self, dt: float) -> None:
        for event in pygame.event.get():
            self.handle_event(event)
        self.update(min(dt, C.MAX_DT))
        self.draw()

    async def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000
            self.frame(dt)
            # Menyerahkan kontrol ke event loop — wajib agar bisa jalan di browser (pygbag)
            await asyncio.sleep(0)
        pygame.quit()


async def run() -> None:
    await App().run()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
