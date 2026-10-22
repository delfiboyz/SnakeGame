import random

import pytest

from snakegame.logic import (
    BONUS_EVERY,
    COMBO_WINDOW,
    DIFFICULTIES,
    Direction,
    EventKind,
    Game,
    Mode,
    build_maze,
)


def make_game(mode=Mode.CLASSIC, cols=10, rows=10):
    game = Game(cols, rows, mode, DIFFICULTIES[1], rng=random.Random(1))
    game.food = (0, 0)  # jauhkan makanan agar tidak mengganggu test
    return game


def test_initial_state():
    game = make_game()
    assert game.head == (5, 5)
    assert len(game.snake) == 3
    assert game.alive and game.score == 0


def test_moves_forward():
    game = make_game()
    game.step()
    assert game.head == (6, 5)
    assert len(game.snake) == 3
    assert game.previous[0] == (5, 5)


def test_cannot_reverse_and_buffers_turns():
    game = make_game()
    assert not game.turn(Direction.LEFT)  # berbalik arah ditolak
    assert game.turn(Direction.UP)
    assert game.turn(Direction.LEFT)  # belokan kedua dibuffer
    assert not game.turn(Direction.DOWN)  # antrean penuh
    game.step()
    assert game.head == (5, 4)
    game.step()
    assert game.head == (4, 4)


def test_wall_kills_in_classic():
    game = make_game()
    events = []
    for _ in range(10):
        events += game.step()
    assert not game.alive
    assert events[-1].kind is EventKind.DIE


def test_portal_wraps():
    game = make_game(Mode.PORTAL)
    for _ in range(5):
        game.step()
    assert game.alive
    assert game.head == (0, 5)


def test_eating_grows_and_scores():
    game = make_game()
    game.food = (6, 5)
    events = game.step()
    assert [e.kind for e in events] == [EventKind.EAT]
    assert len(game.snake) == 4
    assert game.score == 1
    assert game.food not in game.snake


def test_combo_multiplies_points():
    game = make_game()
    game.food = (6, 5)
    game.step()
    game.food = (7, 5)
    event = game.step()[0]
    assert event.combo == 2 and event.points == 2
    assert game.score == 3


def test_combo_resets_after_window():
    game = make_game()
    game.food = (6, 5)
    game.step()
    game._since_eat = COMBO_WINDOW + 0.1
    game.food = (7, 5)
    assert game.step()[0].combo == 1


def test_self_collision():
    game = make_game()
    game.snake.extend([(2, 5), (1, 5)])
    for d in (Direction.UP, Direction.LEFT, Direction.DOWN):
        game.turn(d)
        game.step()
    assert not game.alive


def test_moving_into_tail_cell_is_safe():
    game = Game(4, 4, rng=random.Random(0))
    game.snake.clear()
    game.snake.extend([(1, 1), (1, 2), (2, 2), (2, 1)])
    game.direction = Direction.UP
    game.food = (3, 3)
    game.turn(Direction.RIGHT)
    game.step()
    assert game.alive and game.head == (2, 1)


def test_speed_increases_and_is_capped():
    game = make_game()
    start = game.speed
    game.eaten = 5
    assert game.speed > start
    game.eaten = 10_000
    assert game.speed == DIFFICULTIES[1].max_speed


def test_update_uses_fixed_timestep():
    game = make_game()
    game.update(2.5 / game.speed)
    assert game.head == (7, 5)
    assert 0.4 < game.progress < 0.6


def test_bonus_spawns_and_expires():
    game = make_game(cols=30, rows=10)
    game.eaten = BONUS_EVERY - 1
    game.food = (16, 5)
    events = game.step()
    assert EventKind.BONUS_SPAWN in [e.kind for e in events]
    assert game.bonus is not None
    game.bonus.ttl = 0.01
    game._accumulator = -10  # cegah ular bergerak
    events = game.update(0.02)
    assert [e.kind for e in events] == [EventKind.BONUS_EXPIRED]
    assert game.bonus is None


def test_eating_bonus():
    game = make_game()
    game.eaten = BONUS_EVERY - 1
    game.food = (6, 5)
    game.step()
    game.bonus.cell = (7, 5)
    event = game.step()[0]
    assert event.kind is EventKind.BONUS_EAT
    assert event.points == 5 * 2  # combo x2
    assert game.bonus is None


def test_win_when_board_full():
    game = Game(4, 1, rng=random.Random(0))
    game.snake.clear()
    game.snake.extend([(2, 0), (1, 0), (0, 0)])
    game.food = (3, 0)
    events = game.step()
    assert game.won and not game.alive
    assert events[-1].kind is EventKind.WIN


@pytest.mark.parametrize("cols,rows", [(30, 20), (20, 14), (40, 30)])
def test_maze_leaves_start_clear(cols, rows):
    game = Game(cols, rows, Mode.MAZE, rng=random.Random(0))
    maze = build_maze(cols, rows)
    assert maze
    assert not maze & set(game.snake)
    assert game.food not in maze
    # beberapa langkah pertama ke kanan harus aman
    for _ in range(3):
        game.step()
    assert game.alive
