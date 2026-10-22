"""Konstanta tampilan dan palet warna."""

TITLE = "Snake Game"

# Grid permainan
CELL = 24
COLS = 30
ROWS = 20
HUD_HEIGHT = 64

FIELD_WIDTH = COLS * CELL
FIELD_HEIGHT = ROWS * CELL
WIDTH = FIELD_WIDTH
HEIGHT = FIELD_HEIGHT + HUD_HEIGHT

FPS = 120
# Batas delta-time agar lag sesaat tidak membuat ular "melompat" jauh
MAX_DT = 0.1

COUNTDOWN_SECONDS = 3
GAME_OVER_INPUT_DELAY = 0.6

# Palet warna (tema neon gelap)
BG_TOP = (14, 17, 33)
BG_BOTTOM = (6, 8, 18)
FIELD_A = (20, 24, 44)
FIELD_B = (23, 28, 50)
GRID_LINE = (30, 36, 62)
TEXT = (232, 236, 255)
TEXT_DIM = (128, 136, 172)
ACCENT = (0, 230, 180)
SNAKE_HEAD = (0, 245, 190)
SNAKE_TAIL = (0, 110, 200)
FOOD = (255, 72, 110)
LEAF = (90, 220, 120)
BONUS = (255, 200, 40)
OBSTACLE = (78, 86, 130)
OBSTACLE_EDGE = (120, 130, 186)
DANGER = (255, 80, 90)
PANEL = (16, 20, 40)
PANEL_EDGE = (60, 70, 120)
