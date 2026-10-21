import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from snakegame.app import App, State  # noqa: E402
from snakegame.storage import Store  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = App(Store(tmp_path / "data.json"))
    yield app
    pygame.quit()


def press(app, key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.frame(1 / 60)


def test_full_flow(app):
    app.frame(1 / 60)
    assert app.state is State.MENU
    press(app, pygame.K_RIGHT)  # ganti mode
    press(app, pygame.K_RETURN)
    assert app.state is State.COUNTDOWN
    for _ in range(200):
        app.frame(1 / 60)
    assert app.state is State.PLAYING
    press(app, pygame.K_p)
    assert app.state is State.PAUSED
    press(app, pygame.K_p)
    assert app.state is State.PLAYING
    # biarkan ular menabrak tembok (atau berputar di mode portal) hingga selesai
    press(app, pygame.K_UP)
    for _ in range(3000):
        app.frame(1 / 30)
        if app.state is State.GAME_OVER:
            break
    else:
        app.game.alive = False
        app.update(0)
    assert app.state is State.GAME_OVER
    for _ in range(60):
        app.frame(1 / 60)
    press(app, pygame.K_ESCAPE)
    assert app.state is State.MENU


def test_swipe_controls(app):
    press(app, pygame.K_RETURN)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(300, 300)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(300, 200)))
    app.frame(1 / 60)
    assert list(app.game._turns)[-1].name == "UP"
